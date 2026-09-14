# JanmaPath — Product Flows

> The canonical description of how the product behaves. Where this document and
> an implementation disagree, this document is the specification.

---

## 1. Acquisition → account

```
Landing page
    │
    ├── "Get my free kundli"  ──▶  Register
    └── "Sign in"             ──▶  Login
```

### Register — phone

```
1. Enter phone number
2. Receive OTP by SMS            (6 digits, 5 min, max 5 attempts)
3. Verify OTP
4. Set password + confirm password
5. ─▶ First-run onboarding
```

### Register — Google

```
1. "Continue with Google"
2. Google consent → ID token verified server-side
3. Enter phone number                ← mandatory
4. Verify OTP                        ← mandatory
5. Set password (optional — "Skip for now")
6. ─▶ First-run onboarding
```

**Why phone is mandatory on the Google path:** the phone number is the canonical
identity *and* the WhatsApp delivery channel for the daily horoscope. An account
without a verified phone cannot receive the core product.

**Why the password is optional there:** Google already is the credential. Forcing
a second one adds a step and a credential to leak, for no security gain.

### Login

```
Phone → OTP                       ← default path
Phone → Password                  ← "Use password instead"
Continue with Google              ← one tap
```

Never OTP **and** password in the same login. That friction costs conversions and
buys nothing — the OTP already proves possession of the phone.

---

## 2. First-run — data verification and first kundli

A user who has never generated a chart lands here immediately after registration.

```
┌─ Step 1 · Confirm your details ────────────────────────┐
│  Full name          [ prefilled from registration ]    │
│  Gender             [ ]                                │
│  Date of birth      [ ]                                │
│  Time of birth      [ ]  ( ) I know it exactly         │
│                          ( ) Approximately             │
│                          ( ) I don't know it           │
│  Place of birth     [ autocomplete → lat/lon/tz ]      │
│                                                        │
│  ☐ I consent to JanmaPath processing this data to      │
│    generate my horoscope.              [DPDP consent]  │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Step 2 · Creating your kundli ────────────────────────┐
│                                                        │
│   ✓ Locating your birth coordinates                    │
│   ✓ Computing planetary longitudes                     │
│   ⟳ Casting your Rashi and Navamsa charts              │
│   · Running your Vimshottari dasha                     │
│   · Scanning for doshas                                │
│   · Composing your report                              │
│                                                        │
└────────────────────────────────────────────────────────┘
```

Each line is a **real stage of a real job**, streamed over SSE as it completes,
with a minimum dwell time for pacing. Not a fake timer.

If **"I don't know it"** was selected for birth time, the engine suppresses all
house-dependent output and the report states this plainly. It does not quietly
emit an ascendant it cannot know.

---

## 3. Free preview → paywall

After generation the user sees their chart, free:

```
  Your Kundli
  ├── Rashi chart (D1) — rendered
  ├── Ascendant, Moon sign, Nakshatra
  ├── Current Mahadasha
  └── Brief chart summary

  ── scroll ──

  ┌────────────────────────────────────────────────────┐
  │  Your full life report                             │
  │                                                    │
  │  Covers 12 life areas including the 2 doshas       │
  │  found in your chart:                              │
  │                                                    │
  │   · Your current life phase and what's ahead       │
  │   · Marriage and relationships                     │
  │   · Financial forecast                             │
  │   · Career direction                               │
  │   · Doshas found, and their remedies               │
  │                                                    │
  │  Plus, for your full access period:                │
  │   · A personal horoscope on WhatsApp every         │
  │     morning at 6 AM                                │
  │   · 30 horoscope matches                           │
  │   · Remedy guidance for every dosha found          │
  │                                                    │
  │            [ Unlock for ₹___ ]                     │
  │                                                    │
  │  One payment. No auto-renewal.                     │
  └────────────────────────────────────────────────────┘

  For guidance and entertainment purposes.
```

### Framing constraint — not optional

The paywall must be **value-forward**, never fear-forward.

| ✅ Use | ❌ Never |
|---|---|
| "Covers 12 life areas including the 2 doshas found in your chart" | "Dosha found! Pay now to see the danger" |
| "One payment. No auto-renewal." | "Only 3 slots left today" |
| "Unlock full report" | "No thanks, I'll risk it" |

India's CCPA Dark Patterns guidelines (2023) explicitly prohibit *false urgency*
and *confirm shaming*. The paywall itself is entirely fine; the framing is what
creates exposure. The compliant version converts comparably and costs nothing.

---

## 4. Payment → entitlement

```
[ Unlock ] ─▶ Razorpay checkout (UPI / card / netbanking / wallet)
                    │
                    ▼
         Razorpay webhook ──▶ signature verified
                          ──▶ webhook_events INSERT (unique event id)
                                  │ duplicate? ─▶ 200, stop
                                  ▼
                          transaction.atomic():
                            payment.captured
                            entitlement(plan, starts, ends)
                            feature_quota(guna_matching, limit=30)
                    │
                    ▼
              Full report generation queued
```

The user is not left staring at a spinner — the success page shows the report
being composed, again over SSE.

---

## 5. Home — the dashboard

Once the subscription is active:

| Panel | Contents |
|---|---|
| **Today** | Today's personalized horoscope, panchang, current dasha |
| **My Kundli** | Full chart, divisional charts, planetary table |
| **Life Report** | The full report — current status, marital, financial, career, doshas |
| **Doshas & Remedies** | Each dosha found, what it means, what can be done |
| **Horoscope Matching** | Guna Milan · `N of 30 matches used` |
| **Financial Forecast** | Detailed financial outlook |
| **Consult an Astrologer** | Browse by language and speciality, book a call |
| **My Orders** | Poojas, prasad parcels, printed reports, consultations |
| **Settings** | Profile, WhatsApp preferences, language, data & privacy |

---

## 6. Daily horoscope on WhatsApp

Every morning at **6:00 AM IST**, each subscribed user with `whatsapp_daily`
consent receives a personalized message on WhatsApp.

"Personalized" means computed against **their natal chart** — current transits
read against their own planetary positions and running dasha — not a generic
sun-sign column.

See [`ARCHITECTURE.md` §9](ARCHITECTURE.md) for the pipeline that makes this
affordable at scale.

Opt-out is honoured immediately and permanently, via STOP in WhatsApp or the
Settings panel.

---

## 7. Horoscope matching

```
Select two birth profiles (own + partner's, or two others)
        │
        ▼
Quota check ──▶ under 30?  ─ yes ─▶ free, increment used_count
             │
             └─ no ──────────────▶ pay per match ─▶ Razorpay
        │
        ▼
Ashtakoota Guna Milan — 36 points across 8 kootas
Mangal dosha compatibility
Narrative verdict and recommendation
```

The 30-match allowance belongs to the **access period**, tracked in
`feature_quotas`. Beyond it, each match is a small one-off payment.

---

## 8. Remedies, poojas and prasad

```
Dosha detected in chart
        │
        ▼
Remedy page — what this dosha means, what is traditionally done
        │
        ├─▶ Self-remedy guidance                          (included)
        │
        └─▶ "Have this pooja performed for you"           (paid)
                    │
                    ├── choose deity / temple
                    ├── choose date
                    ├── pay service fee
                    │
                    ▼
            Pooja performed  ──▶  evidence recorded (photos / video)
                    │
                    ├─▶ Prasad from the temple, by parcel     (+ delivery)
                    └─▶ Printed life report & horoscope,
                        posted after the pooja                (+ delivery)
```

The printed-report flow deliberately waits on the pooja — `report_prints.status`
begins at `awaiting_pooja` and only moves to `queued` once the booking is marked
`performed`. This is the emotional heart of the product and the sequencing
matters.

---

## 9. Astrologer consultation

```
Browse astrologers
  filter by language (Hindi, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, English)
  filter by speciality
        │
        ▼
Pick a slot from their availability
        │
        ▼
Top up wallet / pay for the session
        │
        ▼
Call connected through number masking
  — neither party ever sees the other's real number —
        │
        ▼
Per-minute billing against wallet ─▶ wallet_ledger (append-only)
        │
        ▼
Rate the consultation
```

Astrologers are **verified before listing** — `status` moves `pending` →
`verified` only after manual review in Django admin. The product's credibility
rests on this.

---

## 10. Account lifecycle

| Action | Behaviour |
|---|---|
| Change phone | Verify new number by OTP before switching; old number released |
| Revoke WhatsApp consent | Daily sends stop from the next cycle; existing data retained |
| Delete account | `status = deletion_requested`; documented erasure across Postgres, MongoDB, Redis, S3 and processors; financial records retained only as long as statutorily required, and anonymised |
| Policy version change | Existing consent invalidated; re-consent prompted at next login |
