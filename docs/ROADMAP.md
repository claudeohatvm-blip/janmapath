# JanmaPath — Build Roadmap

> Estimates assume one full-time developer. Phases are sequential; the exit
> criteria are what "done" means, not a suggestion.

---

## ⚠️ Start these now — they do not depend on code

Two external approvals have lead times that cannot be compressed by writing code
faster. Both are **launch blockers**. Begin them before Phase 0.

| Item | Lead time | Blocks |
|---|---|---|
| **TRAI DLT registration** — entity, header and SMS template registration with a telecom operator, via MSG91 / Kaleyra | ~1 week, sometimes longer | All OTP delivery → all registration and login |
| **WhatsApp Business — number verification, Meta Business verification, message template approval** | 1–3 weeks | The daily horoscope, i.e. the core subscription promise |

A third item needs a decision, not an application:

| Item | Deadline |
|---|---|
| **Swiss Ephemeris licence** — buy commercial, or migrate to Skyfield + JPL DE440 | Must be resolved **before Phase 1 exits**. See [`DECISIONS.md` ADR-004](DECISIONS.md). |

---

## Phase 0 — Foundation

**~2 weeks**

- Django 5.2 project, settings split (`base` / `dev` / `prod` / `test`)
- **Custom user model with `phone_e164` as `USERNAME_FIELD`** — in the very first migration
- Docker Compose: Postgres 16, MongoDB (replica set), Redis
- Database router directing models to the right store
- Celery + Beat wired and running
- Tailwind + HTMX + Alpine asset pipeline
- `ruff`, `mypy`, `pytest` and CI on every push
- Sentry, structured logging with PII masking
- Phone + OTP registration and login
- Google OAuth via `django-allauth`, with mandatory phone binding
- Rate limiting on all OTP paths
- Consent capture and the `consents` log
- Birth profile capture with place autocomplete, geocoding and historical timezone resolution

**Exit criteria**
A user can register by phone or Google, log in, and save a birth profile with a
correctly resolved historical UTC birth timestamp. CI is green.

---

## Phase 1 — The engine and the first rupee

**~4 weeks** · *the phase that decides whether the product is real*

- `apps/astro` as a pure module — ephemeris, panchang, D1/D9/D10, Vimshottari dasha, dosha detection
- **Reference chart test suite** validated against published panchangs and established software
- Chart generation as a Celery job with real staged progress
- SSE progress endpoint + the HTMX creation screen
- Chart persistence — Postgres pointer + MongoDB document, idempotent on `input_checksum`
- Free chart preview
- Paywall, value-forward framing, `is_free` section boundary
- Razorpay checkout, signature-verified webhooks, `webhook_events` idempotency
- Entitlements and feature quotas
- Full life report — assembly, LLM narration from structured findings, narrative cache
- PDF rendering via WeasyPrint to S3
- Django admin configured for support: user lookup, order history, manual entitlement grant

**Exit criteria**
A stranger can arrive at the landing page, register, generate a correct kundli,
pay, and read their full life report. Charts reproduce byte-identically on
recomputation. The webhook suite passes duplicate, out-of-order and
invalid-signature replay tests. **The ephemeris licence question is resolved.**

> Do not rush the reference chart suite. If the charts are wrong, nothing built
> on top of them matters.

---

## Phase 2 — The daily habit

**~3 weeks**

- Dashboard with all panels
- Transit engine — daily gochar against natal positions
- `panchang_daily` and `transits_daily` precompute at 02:00
- Narrative signature bucketing and `narrative_cache`
- WhatsApp Cloud API integration, template management, delivery status tracking
- The 06:00 fan-out pipeline, rate-limited
- Opt-in, opt-out, STOP handling
- Ashtakoota Guna Milan with the 30-match quota
- Match result presentation and narrative
- Detailed financial forecast section

**Exit criteria**
Subscribed users receive a genuinely personalized horoscope at 6:00 AM IST.
Delivery rate and cost per user are both measured. Matching enforces its quota
correctly at the boundary, including concurrent requests.

---

## Phase 3 — Remedies and physical fulfilment

**~3 weeks**

- Dosha → remedy content mapping
- Service catalogue, temples, deities
- Pooja booking with date selection and payment
- Evidence capture (photos / video) on completion
- Prasad parcel ordering
- Printed report flow — `awaiting_pooja` → `queued` → `printed` → `shipped`
- Address book
- Shiprocket integration, AWB tracking, status webhooks
- Ops back-office in Django admin: booking queue, print queue, dispatch queue

**Exit criteria**
A user with a detected dosha can book a pooja, receive evidence it was performed,
and receive prasad and a printed report by post — with operations able to run the
whole queue from Django admin without a developer.

---

## Phase 4 — Astrologer marketplace

**~5 weeks** · *effectively its own product*

- Astrologer onboarding and verification workflow
- Profiles — languages, specialities, rates, ratings
- Availability calendars and slot booking
- Wallet: top-up, append-only ledger, balance reconciliation
- Masked calling via Exotel (or in-app via 100ms / Agora)
- Per-minute billing against wallet, with pre-authorisation
- Post-call rating and review
- Astrologer payouts and reconciliation reporting

**Exit criteria**
A user can find a verified astrologer who speaks their language, book, talk, be
billed accurately per minute, and rate the session. Payouts reconcile against
the ledger to the paisa.

> This is the first module to extract from the monolith when it grows — real-time
> presence, telephony and per-minute billing have a different operational shape
> from the rest of the app.

---

## Cross-cutting, throughout

| Concern | Practice |
|---|---|
| **Accuracy** | Every engine change re-runs the reference chart suite. Charts are versioned; recomputation is a deliberate migration. |
| **DPDP** | Consent logged and versioned. Erasure path built in Phase 0 and tested every phase. Region locked to `ap-south-1`. |
| **Cost** | Narrative cache hit rate is a tracked metric from Phase 2. It is the dominant variable cost in the product. |
| **Ops** | Every new user-facing object gets a Django admin surface in the same PR. Ops should never need a developer for routine work. |
| **Languages** | Content and narration are multilingual from Phase 1. Retrofitting i18n is far more expensive than carrying it. |
| **Disclaimers** | "For guidance and entertainment purposes" visible on every report and horoscope surface. |

---

## Rough timeline

```
Week  0        DLT + WhatsApp applications submitted
Weeks 1–2      Phase 0  Foundation
Weeks 3–6      Phase 1  Engine, paywall, first revenue          ◀ launchable
Weeks 7–9      Phase 2  Daily WhatsApp, matching
Weeks 10–12    Phase 3  Remedies, poojas, fulfilment
Weeks 13–17    Phase 4  Astrologer marketplace
```

**Phase 1 is the minimum launchable product.** A correct kundli, a paid life
report, and a paywall that works is a real business. Phases 2–4 are what make it
a *companion* rather than a report generator — but they are additive, and each
can ship to real users the week it is done.
