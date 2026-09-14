# JanmaPath — Architecture

> Status: agreed design, pre-implementation.
> Companion documents: [`DATA_MODEL.md`](DATA_MODEL.md), [`USER_FLOWS.md`](USER_FLOWS.md),
> [`ROADMAP.md`](ROADMAP.md), [`DECISIONS.md`](DECISIONS.md).

---

## 1. System overview

```
                    ┌─────────────────────────────────────────┐
   Browser ────────▶│  Django 5.2 (modular monolith)          │
   (HTML + HTMX)    │                                         │
                    │  web       accounts    profiles         │
                    │  kundli    astro ◀── pure, no Django    │
                    │  reports   billing     matching         │
                    │  services  fulfilment  messaging        │
                    └───┬──────────┬──────────┬───────────────┘
                        │          │          │
          ┌─────────────┘          │          └──────────────┐
          ▼                        ▼                         ▼
  ┌───────────────┐      ┌──────────────────┐      ┌─────────────────┐
  │ PostgreSQL 16 │      │    MongoDB       │      │     Redis       │
  │ identity      │      │ charts           │      │ OTP, rate limit │
  │ money         │      │ reports          │      │ cache, locks    │
  │ orders        │      │ horoscope content│      │ Celery broker   │
  │ fulfilment    │      │ panchang/transits│      └─────────────────┘
  └───────────────┘      └──────────────────┘
                        │
                        ▼
          ┌─────────────────────────────────┐
          │  Celery workers + Celery Beat   │
          │  chart generation               │
          │  report generation + PDF        │
          │  02:00 transit precompute       │
          │  06:00 WhatsApp fan-out         │
          │  webhook processing             │
          └─────────────────────────────────┘
```

Everything runs in a single region, **`ap-south-1` (Mumbai)** — required for
latency to Indian users and for a defensible posture under the DPDP Act.

---

## 2. Why a modular monolith

One Django project, one deployable, with **hard module boundaries**: apps do not
import each other's models directly. Cross-module access goes through a thin
service interface exposed by each app (`apps/billing/services.py`, etc.).

This buys the extractability of microservices at a fraction of the operational
cost. When the astrologer-consultation marketplace outgrows the monolith — it
carries real-time presence, telephony and per-minute billing — it becomes the
first service carved out, and the boundary is already drawn.

**Why Django specifically:** JanmaPath has an unusually large operations surface
— poojas to fulfil, prasad parcels to dispatch, printed reports to post,
astrologers to verify and pay out, refunds, comps, support lookups. Django admin
delivers that back-office nearly free. Django also keeps the stack in Python, so
the astrology engine uses the mature Python ephemeris ecosystem natively rather
than through a network hop.

---

## 3. Frontend

**Django templates + HTMX + Alpine.js + Tailwind CSS.** No SPA.

| Need | How |
|---|---|
| Landing page SEO | Server-rendered HTML, no hydration cost |
| Dashboard panels | HTMX partial swaps |
| Chart-generation progress | HTMX SSE extension against a Django SSE view |
| Forms, paywall reveal | HTMX `hx-post` + partial responses |
| Dropdowns, modals, tabs | Alpine.js |
| Styling | Tailwind, single build step |

**Templates directory** is organised as `base.html` → `pages/` → `partials/`.
Every HTMX endpoint returns a `partials/` fragment; never a full page.

No `npm` build beyond Tailwind's CLI. No API-contract drift, no CORS, no separate
frontend deploy.

---

## 4. Application modules

```
janmapath/
├── config/
│   ├── settings/            base.py · dev.py · prod.py · test.py
│   ├── urls.py
│   ├── celery.py
│   └── db_router.py         routes models to postgres vs mongo
├── apps/
│   ├── core/                base models, mixins, audit log, utilities
│   ├── accounts/            User, OTP, Google OAuth, sessions, consent
│   ├── profiles/            BirthProfile, places, geocode + timezone
│   ├── astro/               ◀── PURE ENGINE. No Django imports. Ever.
│   ├── kundli/              Django models wrapping astro; generation jobs
│   ├── reports/             report assembly, LLM narration, PDF rendering
│   ├── billing/             Razorpay, orders, webhooks, entitlements, quotas
│   ├── matching/            Guna Milan; quota enforcement
│   ├── services/            pooja, remedies, astrologer consultations, wallet
│   ├── fulfilment/          addresses, shipments, Shiprocket
│   ├── messaging/           WhatsApp, SMS, notification preferences
│   └── web/                 views + templates (the HTML frontend)
├── templates/
├── static/
└── tasks/                   Celery tasks + Beat schedule
```

### The `astro` module is special

`apps/astro/` contains **no Django imports and performs no I/O**. It is a pure
function library: birth data in, chart object out.

```
astro/
├── ephemeris.py      sidereal planetary longitudes (Lahiri ayanamsa)
├── panchang.py       tithi, nakshatra, yoga, karana, vara
├── charts.py         D1 Rashi, D9 Navamsa, D10 Dashamsha
├── dasha.py          Vimshottari maha / antar / pratyantar
├── dosha.py          Mangal, Kaal Sarp, Pitru, Sade Sati, Shani Dhaiya
├── matching.py       Ashtakoota Guna Milan (36 points)
├── transits.py       daily gochar against natal positions
└── tests/
    └── fixtures/reference_charts/   known-good charts for regression
```

This discipline is the single most important one in the codebase. A pure module
is deterministic, unit-testable against reference charts, and free of the
framework churn that would otherwise make chart correctness hard to prove.

**If the charts are wrong, nothing else in the product matters.**

---

## 5. Data stores — and the seam between them

Django's multi-database support with a `db_router` sends each model to the right
store. The seam is drawn where each store's guarantees actually matter.

### PostgreSQL — identity, money, fulfilment

Anything where a half-written state causes a support incident or a financial
discrepancy: users, credentials, consent, orders, payments, refunds,
entitlements, quotas, wallet ledger, bookings, shipments, astrologers.

These paths need `transaction.atomic()`. A Razorpay webhook must create the
payment record, grant the entitlement, initialise the feature quota, and write
the idempotency guard **as one unit or not at all** — otherwise a user pays and
receives nothing, or is granted twice.

### MongoDB — astrology documents

Deeply nested, schema-evolving content that is written once and read many times:
computed charts, generated reports, narrative caches, daily horoscopes, panchang
and transit data.

These documents have no natural tabular shape, will gain fields as the engine
matures, and benefit from MongoDB's aggregation pipeline — particularly in the
daily-horoscope signature bucketing described in §9.

### The pointer pattern

Postgres rows hold **metadata and foreign keys**; MongoDB holds the **payload**.
A `charts` row in Postgres carries `birth_profile_id`, `engine_version`,
`ayanamsa`, `input_checksum` and `mongo_doc_id`. The nested planetary data lives
in Mongo under that id.

Queryable derived facts are denormalised back into Postgres. Dosha findings, for
example, get a `chart_doshas` table (`chart_id`, `dosha_code`, `severity`) so the
remedy-upsell and segmentation queries can join against users — while the full
explanatory text stays in the Mongo document.

### Redis

OTP challenges (hashed, TTL'd), rate-limit counters, session cache, distributed
locks, Celery broker and result backend, and the daily-dispatch working set.

---

## 6. The astrology engine

### Correctness requirements

**Timezone resolution.** Never assume `UTC+05:30`. Resolve the IANA zone from the
birth *place*, then apply it at the birth *date* — India observed DST in 1942–45
and used different local offsets before 1955. Getting this wrong silently
corrupts every chart for older users. Use `zoneinfo` with the historical
database, not a fixed offset.

**Geocoding.** Google Places or Mapbox resolves a place name to lat/lon;
`timezonefinder` resolves lat/lon to an IANA zone. Results are cached in the
`places` table — users overwhelmingly share a small set of birth cities.

**Snapshot the inputs.** `birth_profiles` stores its own `lat`, `lon` and `tz_id`
copied from the place at creation time. If a place record is later corrected, an
existing chart's inputs must not silently change underneath it.

**Unknown birth time.** Many users will not know it. `time_accuracy` is an
explicit enum — `exact` / `approximate` / `unknown`. When the time is unknown the
engine must **suppress house-dependent output** rather than emit confident
garbage: ascendant, house placements, and bhava-based dosha rules are withheld,
and the report says so plainly.

**Determinism and versioning.** Every chart is stored immutably with its
`engine_version` and `ayanamsa`. Identical input must always produce an identical
chart. `input_checksum` is unique per `(engine_version, ayanamsa)`, so recomputation
is idempotent and cached. When the engine improves, old reports remain
reproducible and recomputation becomes a deliberate, auditable migration.

### Ephemeris dependency — open decision

Swiss Ephemeris (`pyswisseph`) is dual-licensed **AGPL-3.0 or paid commercial**. A
closed-source SaaS built on it requires the commercial licence, otherwise the
AGPL obligation to publish source applies.

Decision deferred — prototyping on the AGPL build. See
[`DECISIONS.md` ADR-004](DECISIONS.md) for the options and the resolution
deadline. **This must be settled before Phase 1 exits.**

### The LLM never computes astrology

The engine produces **structured findings**. The LLM only turns findings into
readable prose in the user's language. It is fed a strict JSON of findings and
constrained to narrate only those — it never infers, calculates, or invents a
placement. Narratives are cached by finding-signature so the same analysis is not
re-generated per user.

---

## 7. Authentication

### Flows

**Register — phone**
`phone → OTP verify → set password + confirm`

**Register — Google**
`Google → verify phone via OTP → password optional`

Phone verification is mandatory even on the Google path: the phone number is the
canonical identity *and* the WhatsApp delivery channel. A password after Google
is redundant, so it is offered rather than required.

**Login**
OTP-only by default · "Use password instead" as a faster alternative · Google
one-tap. Never OTP *and* password together — that friction costs conversions and
buys nothing.

### Security specification

| Concern | Decision |
|---|---|
| User model | Custom `AbstractBaseUser`, `USERNAME_FIELD = "phone_e164"` — **must ship in the first migration** |
| Password hashing | Argon2id (`django.contrib.auth.hashers.Argon2PasswordHasher` first in the list) |
| OTP format | 6 digits, cryptographically random |
| OTP storage | SHA-256 hashed in Redis, 5-minute TTL, never logged |
| OTP attempts | Max 5 verifications per challenge, then invalidate |
| Resend backoff | 30s → 60s → 120s → 300s |
| Rate limiting | Per phone, per IP, per device fingerprint — **SMS pumping fraud is real and expensive** |
| Access token | 15-minute JWT |
| Refresh token | Rotating, `httpOnly` + `Secure` + `SameSite=Lax` cookie; reuse detection revokes the whole token family |
| Google | `django-allauth`; ID token verified server-side against Google's JWKS; matched on `sub`, never on bare email |
| Account linking | One canonical user keyed on verified phone; Google is a linked `auth_identities` row |
| SMS delivery | MSG91 or Kaleyra — **TRAI DLT registration mandatory**, ~1 week lead time |

---

## 8. Billing and entitlements

### Model: one-time payment for a fixed access period

Not auto-renewing. This is a deliberate advantage: it sidesteps the RBI
e-mandate / AFA regime for recurring auto-debit entirely — no pre-debit
notifications, no mandate registration, no card-on-file complexity. Revisit only
if retention data justifies the compliance cost.

### Entitlements are a separate layer from payments

```
payment (captured)
    └─▶ grants ──▶ entitlement(user, plan, starts_at, ends_at)
                        └─▶ feature_quota(user, "guna_matching", limit=30, used=7)
```

**Every feature gate asks the entitlement layer — never "did this user pay?".**

This is what makes free credits, promos, comped months, partial refunds, and
gifting possible without touching payment code. It is a small amount of extra
structure now that prevents a rewrite later.

### Webhook idempotency

Razorpay retries. Double-granting a subscription is a support nightmare.

1. Verify the webhook signature. Reject unsigned or mismatched payloads.
2. Insert into `webhook_events` with a **unique constraint on
   `(provider, provider_event_id)`**. A duplicate insert fails → already handled →
   return 200 and stop.
3. Process asynchronously via Celery, inside `transaction.atomic()`.
4. Record `processed_at` and outcome.

---

## 9. The 6:00 AM WhatsApp daily horoscope

*(Confirming the intent: 6:00 AM IST, each morning.)*

### The scaling insight

The naive implementation is `N users × (transit computation + LLM call)` in a
single burst. At 100k users that is both unaffordable and will not finish before
6 AM.

But **transits are identical for every user at a given moment.** Only the
comparison against natal positions differs. That asymmetry is the whole design.

### Pipeline

| Time (IST) | Stage |
|---|---|
| **02:00** | Compute global transits + panchang for the day. **Once**, for everyone. |
| **02:30** | Per-user natal-vs-transit diff. Pure arithmetic, cheap, embarrassingly parallel across workers. |
| **03:00** | Bucket users by **narrative signature**: `(moon nakshatra, current dasha lord, top-3 transit hits)`. 100k users collapse to a few thousand distinct signatures. |
| **03:30** | Generate narrative **per signature**, not per user. Cache in `narrative_cache` keyed by signature hash — most signatures are already cached from previous days. |
| **05:45** | Enqueue sends. Personalise at send time (name, one chart-specific line). Fan out across workers under provider rate limits. |
| **06:00** | Delivery. |

This is roughly a **50× reduction** in the largest recurring cost in the product.

### WhatsApp specifics

- Meta Cloud API, directly or via an Indian BSP (AiSensy, Gupshup) for easier onboarding.
- **Message templates require Meta pre-approval — begin this early, it is a launch blocker.**
- Marketing-category templates require explicit opt-in. Store timestamped consent per user in `consents`.
- Honour STOP / unsubscribe immediately and permanently.
- Persist `wamid` and delivery status per message for support and deliverability monitoring.

---

## 10. Chart generation UX — honest theatre

The chart-creation screen should feel substantial ("analyzing your planetary
positions…", "scanning for doshas…"). The real computation takes ~200 ms.

**Do not fake this with a random timer.** Build it as a real job with real stages:

```
locating birth coordinates
  → computing planetary longitudes
    → casting D1 and D9
      → running Vimshottari dasha
        → scanning for doshas
          → composing your report
```

The frontend subscribes over **SSE** (simpler than WebSocket for one-way
progress) and renders each stage as it genuinely completes, with a minimum dwell
time per stage for pacing. The user gets the ceremony, the progress is truthful,
and the same machinery becomes genuinely necessary once LLM report generation
actually takes 40 seconds.

---

## 11. External services

| Need | Choice | Notes |
|---|---|---|
| SMS OTP | MSG91 / Kaleyra | **TRAI DLT registration — start immediately, ~1 week** |
| WhatsApp | Meta Cloud API via AiSensy / Gupshup | **Template approval — start immediately** |
| Payments | Razorpay | UPI, cards, netbanking, wallets |
| Google auth | Google Identity Services via `django-allauth` | |
| Geocoding | Google Places / Mapbox | cached in `places` |
| Timezone | `timezonefinder` + `zoneinfo` | historical offsets matter |
| Shipping | Shiprocket | aggregator; prasad + printed reports |
| Astrologer calls | Exotel (number masking) or 100ms / Agora (in-app) | masking protects both parties |
| LLM narration | Claude (Opus 5 / Sonnet 5) | narration only, never calculation |
| PDF rendering | WeasyPrint | HTML → print-quality PDF |
| Object storage | S3 or Cloudflare R2 | PDFs, chart SVGs |
| Errors / APM | Sentry | |

**Two items have external lead times that cannot be compressed by writing code
faster — DLT registration and WhatsApp template approval. Start both before
development begins.**

---

## 12. Security, privacy and compliance

### DPDP Act 2023

Birth date, exact birth time, birth location and phone number together constitute
sensitive personal data.

- **Purpose-bound explicit consent** at signup, separately for processing and for
  marketing messages.
- **Consent log** — `consents` table records type, version, timestamp, IP and
  evidence. Consent is versioned; a policy change requires re-consent.
- **Deletion on request** — a documented, tested erasure path covering Postgres,
  MongoDB, Redis, S3 and third-party processors.
- **Data residency** — `ap-south-1`.
- **Breach notification readiness** — logging and detection sufficient to
  establish scope.

### Consumer protection — paywall framing

The CCPA Dark Patterns guidelines (2023) explicitly name *false urgency* and
*confirm shaming* (fear-based nudges) as prohibited practices. ASCI additionally
restricts absolute claims.

A paywall framed as *"Dosha found — pay to see what it means"* sits directly on
that line. The paywall itself is fine; the **framing** must be value-forward:

> *"Your full life report covers 12 life areas, including the 2 doshas found in
> your chart. Unlock for ₹X."*

Plus a persistent, visible *"for guidance and entertainment purposes"*
disclaimer. This costs nothing, converts comparably, and removes the exposure.

### Application security baseline

- All secrets from environment, never committed. `django-environ`.
- CSRF enabled everywhere; HTMX configured to send the token.
- `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` in production.
- Content Security Policy via `django-csp`.
- PII never written to application logs — phone numbers masked, OTPs never logged.
- `audit_log` for every admin mutation of user data, orders, entitlements and wallets.
- Wallet ledger is **append-only**; balance is derived, never edited in place.

---

## 13. Testing strategy

| Layer | Approach |
|---|---|
| `astro` engine | **Highest priority.** Reference charts with known-correct output, validated against published panchangs and established software. Property tests for determinism and dasha-period continuity. |
| Billing | Full webhook replay suite including duplicates, out-of-order delivery, and signature failures. Entitlement grant/expiry boundary tests. |
| Auth | OTP expiry, attempt exhaustion, rate limits, refresh-token reuse detection, account linking collisions. |
| Views | Django test client; HTMX partials asserted on fragment content. |
| Integration | Docker Compose with real Postgres, MongoDB and Redis. External providers stubbed at the HTTP boundary. |

CI runs lint (`ruff`), format check (`ruff format`), type check (`mypy` on
`apps/astro` at minimum), and the full test suite on every push.

---

## 14. Deployment

- **Containers** — one image; separate processes for web (`gunicorn`), Celery worker and Celery Beat.
- **Postgres** — managed (RDS or Neon), in `ap-south-1`, PITR enabled.
- **MongoDB** — Atlas, `ap-south-1`. A **replica set is required** for transactions.
- **Redis** — managed, with persistence enabled for the Celery broker.
- **Static/media** — S3 or R2 behind a CDN; `whitenoise` for static in early phases.
- **Migrations** — run as a release step, never on container boot.
- **Environments** — `dev` (Compose), `staging` (production-shaped, anonymised data), `production`.
