# JanmaPath — System Architecture

**India's first personalized astrology companion.**

> Status: agreed design, pre-implementation.
> Companion documents: [`DATA_MODEL.md`](DATA_MODEL.md), [`USER_FLOWS.md`](USER_FLOWS.md),
> [`ROADMAP.md`](ROADMAP.md), [`DECISIONS.md`](DECISIONS.md).

---

## 1. Topology

Four services in Docker containers on a Linux host, fronted by Nginx. Traffic is
separated at the DNS level so the public client and the internal staff console
never share a bundle, a token audience, or a permission surface.

```
                         Internet
                             │
                   ┌─────────┴─────────┐
                   │   Nginx (TLS)     │   reverse proxy · rate limit · gzip
                   └─────────┬─────────┘
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
  janmapath.com      manage.janmapath.com   api.janmapath.com
  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
  │  Client SPA  │   │  Staff SPA   │   │  Django REST         │
  │ React + Vite │   │ React + Vite │   │  Framework           │
  │ static build │   │ static build │   │  gunicorn            │
  └──────────────┘   └──────────────┘   └──────────┬───────────┘
                                                   │
                        ┌──────────────────────────┼─────────────────┐
                        ▼                          ▼                 ▼
              ┌───────────────────┐   ┌────────────────────┐  ┌────────────┐
              │  Celery workers   │   │   PostgreSQL 16    │  │   Redis    │
              │  + Celery Beat    │   │   relational +     │  │ OTP · TTL  │
              │  ─────────────    │   │   JSONField        │  │ cache      │
              │  imports astro/   │   │                    │  │ broker     │
              │  (Vedic engine)   │   │  no public port    │  │ no public  │
              └───────────────────┘   └────────────────────┘  │ port       │
                                                              └────────────┘
                        └──────── isolated Docker bridge network ────────┘
```

**Region:** `asia-south1` (Mumbai) — latency to Indian users, and a defensible
data-residency posture under the DPDP Act.

**Network isolation:** PostgreSQL and Redis expose no ports to the host or the
internet. They are reachable only from the API and worker containers on an
internal bridge network.

---

## 2. Frontend — two independent SPAs

Both are React + Vite, built and served as static assets by Nginx.

**Why two builds rather than one app with route guards:** a route guard hides a
screen; a separate build guarantees the staff code — endpoint paths, admin
component names, internal workflow logic — is never downloaded by a public
visitor. This is the correct boundary and it costs almost nothing, since the two
apps share a component library and Tailwind config through a workspace package.

| | Client (`janmapath.com`) | Staff (`manage.janmapath.com`) |
|---|---|---|
| Audience | Public + subscribers | Employees, astrologers, master admin |
| Auth | `IsClient` JWT | `IsEmployee` / `IsMasterAdmin` JWT |
| Rendering | **Marketing routes pre-rendered (SSG); app routes client-rendered** | Fully client-rendered |
| Indexed | Marketing routes only | `noindex`, plus Nginx IP allowlist if practical |

### Marketing routes must be pre-rendered

The dashboard behind login has no SEO requirement — a SPA is exactly right there.
The **public marketing surface is different**, and it is the one place where
client-side rendering has a real cost.

Organic search is a primary acquisition channel for this product. Queries like
*"manglik dosha remedy"*, *"kundli matching online"*, *"sade sati meaning"* are
high-intent and otherwise have to be bought. A client-rendered landing page
starts that fight at a disadvantage.

**Resolution:** `vite-plugin-ssg` pre-renders the landing page, pricing, and any
content/SEO routes to static HTML at build time. Same React components, same
Tailwind, one build pipeline. Everything behind `/app/*` stays a normal SPA.

### Stack

| Concern | Choice |
|---|---|
| Framework | React 19 + Vite |
| Styling | Tailwind CSS — deep blue / pure black dark base, neon red and blue accents |
| Animation | Framer Motion — looping hero sections, chart-generation overlay |
| Global state | React Context (auth, active entitlement, profile) |
| Server state | TanStack Query over Axios — caching, retries, invalidation |
| HTTP | Axios instance with `withCredentials: true` and a refresh interceptor |
| Charts | **Client-side SVG** — North and South Indian styles drawn from raw planetary degrees returned by the API |

**Client-side SVG chart rendering** is the right call: the API returns degrees,
not images, so the payload stays small, the chart is interactive (tap a planet
for detail), it scales crisply on any screen, and switching North ↔ South Indian
style needs no round trip.

**Animation performance:** looping hero animations must respect
`prefers-reduced-motion` and pause when scrolled off-screen. Continuous loops
otherwise cost mobile battery and damage LCP on the single page where LCP matters
most.

---

## 3. API Gateway — Django REST Framework

A pure JSON API. No server-rendered templates except Django admin, which is
retained as an engineering escape hatch — **not** as the staff console. Operations
staff use the Staff SPA, which talks to `/api/staff/` and is fully audited.

### Namespace routing

Permission classes bind to a URL prefix, so a new endpoint inherits the correct
gate by where it is mounted rather than by remembering a decorator.

| Namespace | Permission | Scope |
|---|---|---|
| `/api/auth/` | `AllowAny` (rate limited) | Google OAuth, phone OTP request/verify, token issue + refresh |
| `/api/client/` | `IsClient` | Kundli generation, reports, matching, payments, bookings, profile |
| `/api/staff/` | `IsEmployee` | Pooja fulfilment, support tickets, consultation scheduling, dispatch |
| `/api/admin/` | `IsMasterAdmin` | Workforce management, user suspension, system metrics, entitlement grants |

Every `/api/staff/` and `/api/admin/` handler that touches user data writes an
`AuditLog` row. See §9.

### Token handling

JWT via `djangorestframework-simplejwt`, with one non-obvious requirement.

> **Access tokens are held in memory only. Refresh tokens live in an
> `httpOnly; Secure; SameSite=Lax` cookie scoped to `api.janmapath.com`.**

Storing a JWT in `localStorage` means any XSS — including one introduced by a
transitive npm dependency — yields a valid token an attacker can exfiltrate and
replay. An `httpOnly` cookie cannot be read by JavaScript at all.

| Token | Lifetime | Storage |
|---|---|---|
| Access | 15 minutes | JS variable in the SPA; lost on refresh, re-obtained silently |
| Refresh | 14 days, rotating | `httpOnly` `Secure` `SameSite=Lax` cookie |

Refresh tokens rotate on every use and are tracked by `family_id`. Presentation
of an already-consumed token revokes the entire family — that pattern means the
token was stolen.

Requires `CORS_ALLOW_CREDENTIALS = True` on Django and `withCredentials: true` on
Axios. `CORS_ALLOWED_ORIGINS` is an exact whitelist of
`https://janmapath.com` and `https://manage.janmapath.com` — never a regex, never
a wildcard.

### Application layout

```
janmapath/
├── config/
│   ├── settings/          base · dev · prod · test
│   ├── urls.py            the four namespaces
│   └── celery.py
├── apps/
│   ├── core/              base models, AuditLog, mixins
│   ├── accounts/          CustomUser, OTP, Google OAuth, tokens, consent, RBAC
│   ├── astro/             ◀── PURE ENGINE. No Django imports. No I/O.
│   ├── kundli/            KundliProfile, chart jobs, persistence
│   ├── reports/           report assembly, narration, PDF
│   ├── billing/           Razorpay, webhooks, entitlements, quotas
│   ├── matching/          Guna Milan, quota enforcement
│   ├── services/          pooja orders, consultations, support tickets
│   ├── fulfilment/        addresses, shipments, tracking
│   └── messaging/         WhatsApp, SMS, notification preferences
└── tasks/                 Celery tasks + Beat schedule
```

---

## 4. The Vedic computation engine

### Module boundary, not a network boundary

`apps/astro/` contains **no Django imports and performs no I/O**. Birth data in,
chart dictionary out. Persistence, job orchestration and presentation all live in
`apps/kundli/`.

```
astro/
├── ephemeris.py      sidereal planetary longitudes (Lahiri ayanamsa)
├── panchang.py       tithi, nakshatra, yoga, karana, vara
├── charts.py         D1 Rashi, D9 Navamsa, D10 Dashamsha
├── dasha.py          Vimshottari maha / antar / pratyantar
├── dosha.py          Mangal, Kaal Sarp, Pitru, Sade Sati, Shani Dhaiya
├── matching.py       Ashtakoota Guna Milan (36 points)
├── transits.py       daily gochar against natal positions
└── tests/fixtures/reference_charts/
```

**Deployment: imported directly by Celery workers, not called over HTTP.**

The original specification isolated the engine behind an internal network
service. The instinct is right — CPU-bound work should not block the I/O-bound
web process — but the mechanism costs more than it returns at this scale:

- A Swiss Ephemeris chart computation is roughly **5–50 ms of CPU**. It is a fast
  pure function, not a heavy workload needing its own runtime.
- The engine returns a large structured payload. An HTTP hop means serializing
  and deserializing it on every single chart.
- A pure function cannot fail. A network call can time out, partially fail, and
  needs retry semantics — distributed failure modes bolted onto arithmetic.
- Testing gets harder: the engine can no longer be exercised from a Django test
  without standing up a second service.

Running the module **inside Celery workers** delivers the actual goal — the web
process never blocks on computation — with none of that cost. The valuable half
of the original design, the hard boundary, is fully preserved.

> **Extraction trigger.** Promote `astro/` to a standalone service when *either*
> chart computation demonstrably needs to scale independently of the rest of the
> worker pool, *or* it must be consumed by a non-Python runtime. Promoting a pure
> module to a service is roughly a day's work; reversing a premature split is not.

Note: a service boundary does **not** resolve the Swiss Ephemeris licensing
question. AGPL-3.0 §13 covers network interaction explicitly. See §12.

### Correctness requirements

**Timezone resolution.** Never assume `UTC+05:30`. Resolve the IANA zone from the
birth *place*, then apply it at the birth *date* — India observed DST in 1942–45
and used different local offsets before 1955. Getting this wrong silently
corrupts every chart for older users. Use `zoneinfo` against the historical
database.

**Snapshot the inputs.** `KundliProfile` stores its own `latitude`, `longitude`
and `tz_id`, copied from the geocoded place at creation. If a place record is
later corrected, an existing chart's inputs must not change beneath it.

**Unknown birth time.** Many users will not know it. `time_accuracy` is an
explicit enum — `exact` / `approximate` / `unknown`. When unknown, the engine
**suppresses house-dependent output** rather than emitting confident garbage:
ascendant, house placements and bhava-based dosha rules are withheld, recorded in
a `suppressed[]` list, and the report says so plainly.

**Determinism and versioning.** Every chart is stored with its `engine_version`
and `ayanamsa`. Identical input must always produce an identical chart —
`input_checksum` is unique per `(engine_version, ayanamsa)`, making recomputation
idempotent and free. Improving the engine never silently mutates existing users'
charts; recomputation becomes a deliberate, auditable migration.

**If the charts are wrong, nothing else in this product matters.** The reference
chart suite is the highest-priority test asset in the codebase.

---

## 5. Data layer

### PostgreSQL 16 — single source of truth

One database. Strict relational modelling for identity, money and fulfilment;
native `JSONField` for the engine's nested output.

```python
class KundliProfile(models.Model):
    user      = models.ForeignKey(User, on_delete=CASCADE,
                                  related_name="kundli_profiles")
    relation  = models.CharField(choices=Relation.choices)   # self|partner|child|other
    ...
    planetary_data = models.JSONField()     # engine output, indexed via GIN
    doshas_found   = models.JSONField()
```

`JSONField` on PostgreSQL is `jsonb` — indexed document storage. It gives the
schema flexibility the engine output needs without a second datastore, and keeps
`transaction.atomic()` available across *every* table in the system, including
the money paths. That last property is why this is a single-store architecture
and not a polyglot one.

### Redis

| Use | Detail |
|---|---|
| OTP challenges | SHA-256 hashed, strict 5-minute TTL, never logged |
| Rate limiting | Per phone, per IP, per device fingerprint |
| Celery broker | Task queue and result backend |
| Cache | Panchang, transits, session-scoped reads |

---

## 6. Core schema

Full detail in [`DATA_MODEL.md`](DATA_MODEL.md). Three structural requirements
are called out here because getting them wrong is expensive to correct once real
users and real money exist.

### `KundliProfile` is a ForeignKey, not OneToOne

Guna Milan requires **two** charts. A one-to-one relationship between user and
profile leaves nowhere to store a prospective partner's birth data, which makes
horoscope matching — a headline feature with a 30-match allowance — structurally
impossible.

```python
class Meta:
    constraints = [
        UniqueConstraint(fields=["user"], condition=Q(relation="self"),
                         name="one_self_profile_per_user"),
    ]
```

One `self` profile per user, enforced by a partial index; any number of others.

### Entitlements, not an `is_subscribed` boolean

A boolean cannot express when access expires, which plan was bought, how many of
the 30 matches remain, a comped month, a promotional grant, or a refund
reversal. Every one of those becomes a fabricated payment row, and revenue
reporting is wrong permanently.

```
Payment (captured)
    └─▶ Entitlement(user, plan_code, starts_at, ends_at, status, granted_reason)
            └─▶ FeatureQuota(entitlement, feature, limit_count, used_count)
                    unique(entitlement, feature)
```

**Every feature gate queries the entitlement layer. None asks "has this user
paid?"** `is_subscribed` survives only as a computed property for display.

Quota increments use a conditional update, never read-modify-write:

```python
FeatureQuota.objects.filter(
    id=quota_id, used_count__lt=F("limit_count")
).update(used_count=F("used_count") + 1)     # 0 rows → quota exhausted
```

### `WebhookEvent` for payment idempotency

Razorpay sends **multiple events per order** — `payment.authorized`,
`payment.captured`, `payment.failed` — and retries each until it receives a 200.
`razorpay_order_id` is therefore *not* a valid idempotency key; it is not unique
per event.

```python
class WebhookEvent(models.Model):
    provider           = models.CharField(max_length=20)
    provider_event_id  = models.CharField(max_length=255)
    event_type         = models.CharField(max_length=64)
    payload            = models.JSONField()
    signature_valid    = models.BooleanField()
    status             = models.CharField(max_length=20)   # received|processed|failed
    class Meta:
        constraints = [UniqueConstraint(fields=["provider", "provider_event_id"],
                                        name="uniq_provider_event")]
```

Handler order, strictly:

1. Verify the signature. Reject anything unsigned or mismatched.
2. `INSERT` the event. `IntegrityError` → already handled → return `200`, stop.
3. Process asynchronously inside `transaction.atomic()`.
4. Record `processed_at` and outcome.

Without step 2, a retried `payment.captured` grants the subscription twice.

### Model summary

| Model | Purpose |
|---|---|
| `CustomUser` | Identity — `phone_e164` (unique, `USERNAME_FIELD`), `role`, `preferred_language` |
| `StaffProfile` | Employee capabilities and spoken languages — decoupled from `role` |
| `AuthIdentity` | Linked Google credential, matched on `sub` |
| `RefreshToken` | Rotation, family tracking, reuse detection |
| `Consent` | Versioned DPDP + WhatsApp opt-in evidence |
| `KundliProfile` | **FK** to user · birth data · `planetary_data` / `doshas_found` JSON |
| `MatchRequest` | Two profile FKs · koota breakdown · total guna · quota or order link |
| `Entitlement` · `FeatureQuota` | Access period and the 30-match allowance |
| `PaymentTransaction` · `WebhookEvent` | Razorpay records and the idempotency guard |
| `PoojaOrder` | Deity, temple, schedule, evidence, delivery, tracking, assignee |
| `ConsultationBooking` | Scheduled time, requested language, assigned staff |
| `SupportTicket` | Escalation workflow, assignee, status |
| `NotificationPreference` | WhatsApp daily / marketing opt-in, send window |
| `AuditLog` | Every staff read or write of user data |

---

## 7. Authentication and roles

### Flows

**Register — phone:** `phone → OTP verify → set password + confirm`

**Register — Google:** `Google → verify phone via OTP → password optional`

Phone verification is mandatory on both paths: the number is the canonical
identity *and* the WhatsApp delivery channel. A password after Google is
redundant — Google already is the credential — so it is offered, not required.

**Login:** OTP by default · "Use password instead" as the faster alternative ·
Google one-tap. Never OTP *and* password together; the OTP already proves
possession of the phone.

### Specification

| Concern | Decision |
|---|---|
| User model | `AbstractBaseUser`, `USERNAME_FIELD = "phone_e164"` — **must ship in the first migration** |
| Password hashing | **Argon2id** (`django[argon2]`, `Argon2PasswordHasher` first) |
| OTP | 6 digits, SHA-256 hashed in Redis, 5-minute TTL, max 5 attempts |
| Resend backoff | 30s → 60s → 120s → 300s |
| Rate limiting | Per phone, per IP, per device — SMS pumping fraud is real and expensive |
| Google | ID token verified server-side against Google's JWKS; matched on `sub`, never bare email |
| Linking | One canonical user keyed on verified phone; Google is a linked `AuthIdentity` |

> **Argon2id, not bcrypt.** bcrypt silently truncates passwords past 72 bytes and
> is weaker against GPU attack. Django ships Argon2 support. Changing this later
> means rehashing every password on next login — it is free to do now.

### Roles

`CustomUser.role` (`USER` / `EMPLOYEE` / `ADMIN`) is the coarse gate that selects
the permission class. Capabilities live on `StaffProfile`:

```python
class StaffProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=CASCADE)
    capabilities = ArrayField(models.CharField(...))   # pooja_ops, support, astrologer
    languages    = ArrayField(models.CharField(...))   # hi, ta, te, ml, kn, bn, mr, en
```

A single `role` field breaks the first time someone is both an astrologer and a
support agent. It also matters functionally:
`ConsultationBooking.requested_language` is matched against
`StaffProfile.languages`, with a GIN index — *"book an astrologer who speaks
Malayalam"* is a core product promise and must be a query.

**Astrologers are staff, not a marketplace.** This is a deliberate v1
simplification: no payout rails, no onboarding funnel, no availability
marketplace. It caps supply at who can be hired, which is the right constraint to
accept while proving demand.

---

## 8. Asynchronous work

Celery over Redis. Beat holds the schedule.

| Task | Cadence |
|---|---|
| Chart generation | On demand, with staged progress |
| Report generation + PDF | On demand |
| Panchang + global transit precompute | Daily, well ahead of the send window |
| Per-user transit diff and signature bucketing | Daily, after precompute |
| Daily horoscope fan-out | 15 minutes before the send window |
| Razorpay webhook processing | On receipt |
| Shipment status polling | Hourly |

### The daily horoscope pipeline

The naive implementation is `N users × (transit computation + narration)` in one
burst. At scale that is unaffordable and will not finish inside the window.

But **transits are identical for every user at a given moment.** Only the
comparison against natal positions differs. That asymmetry is the entire design.

| Stage | Work |
|---|---|
| **Precompute** | Global transits + panchang for the day. **Once**, for everyone. |
| **Diff** | Per-user natal-vs-transit comparison. Pure arithmetic, cheap, parallel. |
| **Bucket** | Group users by **narrative signature** — `(moon nakshatra, current dasha lord, top-3 transit hits)`. A large user base collapses to a few thousand distinct signatures. |
| **Narrate** | Generate per **signature**, not per user. Cache by signature hash — most are already warm from previous days. |
| **Fan out** | `T-15min`: enqueue. Personalise at send time (name, one chart-specific line). Trickle under provider rate limits. |

This is roughly a **50× reduction** in the largest recurring cost in the product.

> **Messaging tier is a hard ceiling that trickling cannot solve.** Meta caps
> unique recipients per 24 hours by tier (1K → 10K → 100K → unlimited). Upgrades
> depend on quality rating and accrue over time. Plan the ramp; a tier cap is not
> a rate limit you can pace around.

---

## 9. Security and compliance

### Staff access to user data must be audited

This requirement is created by the staff layer. Employees can see birth times,
phone numbers and delivery addresses. Under the DPDP Act, who accessed what must
be answerable.

Every `/api/staff/` and `/api/admin/` handler touching user data writes:

```
AuditLog: actor_user, action, object_type, object_id, before, after, ip, created_at
```

Implemented as a DRF mixin on the staff viewsets so it cannot be forgotten on a
new endpoint.

### DPDP Act 2023

Birth date, exact birth time, birth location and phone number together constitute
sensitive personal data.

- **Purpose-bound explicit consent** at signup — separately for processing and
  for marketing messages.
- **Versioned consent log** (`Consent`) recording type, version, timestamp, IP and
  the copy shown. A policy change invalidates prior consent and requires
  re-consent at next login.
- **Erasure path** — documented and tested, spanning PostgreSQL, Redis, object
  storage and third-party processors. Financial records retained only as long as
  statutorily required, then anonymised.
- **Residency** — `asia-south1`.

### Consumer protection — paywall framing

The CCPA Dark Patterns guidelines (2023) explicitly name *false urgency* and
*confirm shaming* as prohibited. ASCI restricts absolute claims.

A paywall reading *"Dosha found — pay to see what it means"* sits directly on that
line. The paywall is legitimate; the **framing** must be value-forward:

> *"Your full life report covers 12 life areas, including the 2 doshas found in
> your chart. Unlock for ₹X."*

No countdown timers, no artificial scarcity, no shaming decline copy. A
persistent *"for guidance and entertainment purposes"* disclaimer accompanies
every report and horoscope surface. The compliant version converts comparably and
removes the exposure.

### Baseline

- Secrets from environment only, never committed (`django-environ`).
- `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE` in production.
- Nginx rate limits on `/api/auth/` independent of application-level limits.
- PII never written to application logs — phone numbers masked, OTPs never
  logged, birth data excluded from error payloads.
- DRF throttling per scope; `IsClient` endpoints scoped to the requesting user's
  own objects by queryset, never by a trusted request parameter.

---

## 10. External integrations

| Need | Provider | Notes |
|---|---|---|
| SMS OTP | Fast2SMS (dev) · MSG91 (prod) | **TRAI DLT registration mandatory** — entity, header and template, ~1 week lead |
| WhatsApp | MSG91 / Meta Cloud API | **Template pre-approval required** — launch blocker |
| Payments | Razorpay | UPI, cards, netbanking, wallets |
| Google auth | Google Identity Services | |
| Geocoding | Google Places / Mapbox | cached; `timezonefinder` for IANA zone |
| Ephemeris | `pyswisseph` (imports as `swisseph`) | Lahiri ayanamsa — **licence open, see §12** |
| Narration | LLM, structured findings only | never computes astrology |
| PDF | WeasyPrint | HTML → print-quality output |
| Shipping | Shiprocket | prasad parcels, printed reports |
| Errors | Sentry | both SPAs and the API |

**Two items have external lead times that writing code faster cannot compress —
DLT registration and WhatsApp template approval. Both should be in flight before
development starts.**

### Narration boundary

The engine produces **structured findings**. The LLM converts findings to prose in
the user's language, fed strict JSON and constrained to narrate only what it is
given. It never infers a placement, computes a dosha, or introduces a claim
absent from the findings.

Astrological calculation is deterministic arithmetic with correct answers. A
model asked to perform it produces fluent, plausible, *inconsistent* output — the
same user could receive different planetary positions on different days. That is
fatal for a product whose credibility rests on the chart being right.

Separating the two also makes narration cacheable by finding-signature, which is
what makes §8 economically viable.

---

## 11. Deployment and operations

| Concern | Approach |
|---|---|
| Runtime | Docker Compose on a single Linux host (v1) |
| Processes | `gunicorn` (API) · `celery worker` · `celery beat` — separate containers, one image |
| Frontends | Built to static assets, served directly by Nginx |
| TLS | Let's Encrypt via certbot, auto-renewed |
| Migrations | A release step, never on container boot |
| Environments | `dev` (Compose) · `staging` (production-shaped, anonymised) · `production` |

### Backups are not optional

A single host with Docker volumes and no off-host backup loses the business on
one disk failure.

**Before the first paying user:** automated `pg_dump` to off-host object storage,
encrypted, retained 30 days — **and a restore that has actually been performed
at least once.** An untested backup is not a backup.

### Known single points of failure (accepted for v1)

One host means one failure domain and deploy downtime unless blue/green is used.
This is a reasonable v1 trade. The first scaling step is moving PostgreSQL to a
managed instance with point-in-time recovery, which also removes the most
dangerous SPOF.

---

## 12. Open decisions

### Swiss Ephemeris licence — **must resolve before the engine is finished**

`pyswisseph` is dual-licensed **AGPL-3.0 or paid commercial**. A closed-source
SaaS requires the commercial licence; otherwise the obligation to publish source
applies.

Isolating the engine behind an internal network service does **not** avoid this —
AGPL §13 covers network interaction explicitly.

| Option | Cost | Effort |
|---|---|---|
| **Commercial licence** *(recommended)* | a few hundred CHF, one-time per developer | none |
| Skyfield + JPL DE440 | free (MIT code, public-domain data) | ~2 weeks to implement Lahiri ayanamsa and sidereal conversion, plus validation |
| Open-source JanmaPath | free | gives away the engine |

The engine's public API is shaped by whichever library it is built on. Swapping
later means rewriting and re-validating the module everything depends on.

### Daily send time

The specification states **6:00 PM IST** (transits pulled at 5:45 PM). Earlier
product notes said "every morning". Morning delivery is the stronger product —
a horoscope is read with chai, not at dinner — but the pipeline is identical
either way. **Confirm before Beat is configured.**

---

## 13. Testing

| Layer | Approach |
|---|---|
| `astro` engine | **Highest priority.** Reference charts with known-correct output, validated against published panchangs and established software. Property tests for determinism and dasha-period continuity. |
| Billing | Full webhook replay — duplicates, out-of-order delivery, signature failures. Entitlement grant and expiry boundaries. Concurrent quota increments. |
| Auth | OTP expiry, attempt exhaustion, rate limits, refresh-token reuse detection, account linking collisions. |
| RBAC | Every `/api/staff/` and `/api/admin/` endpoint asserted to reject a client token, and every `/api/client/` endpoint asserted to reject access to another user's objects. |
| Frontend | Vitest + Testing Library; Playwright for registration → chart → payment. |
| Integration | Docker Compose with real Postgres and Redis. External providers stubbed at the HTTP boundary. |

CI runs `ruff`, `mypy` (at minimum on `apps/astro`), `pytest`, and both frontend
builds on every push.
