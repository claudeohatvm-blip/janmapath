# JanmaPath — Architecture Decision Records

Each record states the decision, the alternatives that were genuinely considered,
and the reasoning. A decision that is later reversed is marked **Superseded**
rather than deleted — the reasoning stays useful.

---

## ADR-001 · Django modular monolith

**Status:** Accepted · 2026-09-14

**Decision.** A single Django 5.2 LTS project with hard module boundaries. Apps
do not import each other's models; cross-module access goes through a service
interface per app.

**Why.**

JanmaPath has an unusually large operations surface for an early-stage product:
poojas to fulfil, prasad parcels to dispatch, printed reports to post,
astrologers to verify and pay out, refunds, comps and support lookups. Django
admin delivers that back-office essentially free — an estimated 4–6 weeks of work
avoided compared with a framework that has no admin.

Django also keeps the stack in Python, so the astrology engine uses the mature
Python ephemeris ecosystem (`pyswisseph`, `skyfield`) natively rather than across
a network hop.

**Alternatives considered.**

*FastAPI monolith* — leaner and faster, but no admin. Given the ops surface, the
admin outweighs the framework overhead by a wide margin.

*Microservices from day one* — real operational cost, no benefit at current
scale. The modular monolith preserves extractability; §2 of `ARCHITECTURE.md`
names the astrologer marketplace as the first module to carve out.

*Node / NestJS backend + Python astrology service* — two deploys, two dependency
sets, a network hop on the hottest path, and no admin. Only justified if the team
could not write Python, which is not the case.

---

## ADR-002 · Server-rendered HTML, no SPA

**Status:** Accepted · 2026-09-14

**Decision.** Django templates + HTMX + Alpine.js + Tailwind CSS.

**Why.**

SEO is a genuine acquisition channel for an astrology product — the landing page
and future content marketing need server-rendered HTML, which an SPA would have
fought.

Development speed is roughly 2–3× that of a React frontend for this feature set:
no API contract to maintain, no contract drift, no CORS, no separate deploy, one
language.

HTMX covers every interaction the product actually needs, including the
chart-generation progress screen — its SSE extension is a direct fit for
server-pushed job stages.

**Alternatives considered.**

*Next.js frontend + Django API* — better for a highly interactive app; JanmaPath
is mostly forms, content and a dashboard. The cost is not repaid.

**Revisit if.** The astrologer consultation experience (live chat, presence,
video) turns out to need a genuinely app-like client. If so, build *that surface*
as an SPA island rather than converting the whole product.

---

## ADR-003 · Split datastore — Postgres + MongoDB

**Status:** Accepted · 2026-09-14

**Decision.** PostgreSQL for identity, money and fulfilment. MongoDB for
astrology documents. Routed by a Django `db_router`.

**Why.**

The original preference was MongoDB alone. Investigation found a documented
limitation that lands directly on the product's riskiest code path:

> `django-mongodb-backend` is generally available (v5.2, tracking Django 5.2 LTS)
> and is a genuine, MongoDB-supported product — it provides the ORM, the full
> admin and DRF support. However, **Django's native transaction API
> (`transaction.atomic()`) is not supported**; the backend ships its own
> transaction API with its own limitations. `QuerySet.delete()` and `update()`
> cannot span collections, and pattern-matching lookups do not work on non-string
> fields.

The Razorpay webhook handler must create the payment record, grant the
entitlement, initialise the feature quota and write the idempotency guard as one
unit or not at all. A half-commit means a user pays and receives nothing, or is
granted twice. The same exposure exists on the astrologer wallet ledger and on
pooja slot booking.

Beyond the transaction gap, any third-party Django package assuming `atomic()`
becomes a compatibility question.

Meanwhile MongoDB is genuinely the better store for the other half — chart
payloads, reports, narrative caches and daily horoscopes are deeply nested,
schema-evolving documents that would be actively harmed by rigid tables, and the
aggregation pipeline suits the daily-horoscope signature bucketing.

So the seam is drawn where each store's guarantees matter, rather than choosing
one store for the whole application.

**Alternatives considered.**

*MongoDB only* — one database, but custom idempotency and compensating-write
logic on exactly the paths where bugs cost money and trust.

*Postgres only with `JSONB`* — the simplest operational story, and `JSONB` is
genuinely indexed document storage. A legitimate choice; rejected only because
MongoDB's query surface and aggregation pipeline are preferred for the astrology
content, and the routing cost is modest.

**Consequences.**

- MongoDB must run as a **replica set** — transactions require it.
- Cross-store consistency is eventual. Postgres is always authoritative; a Mongo
  document is written first and the Postgres pointer row committed second, so a
  failure leaves an orphaned document (harmless, reapable) rather than a dangling
  pointer.
- Backups and the DPDP erasure path must cover both stores.

---

## ADR-004 · Ephemeris library — **OPEN**

**Status:** ⚠️ Open · must be resolved before Phase 1 exits

**The problem.** Swiss Ephemeris (`pyswisseph`) is dual-licensed **AGPL-3.0 or
paid commercial**. A closed-source SaaS built on it requires the commercial
licence; otherwise the AGPL obligation to publish the application's source
applies.

**Current position.** Prototyping on the AGPL build, decision deferred.

**Options.**

| Option | Cost | Effort | Risk |
|---|---|---|---|
| **Buy the commercial licence** | a few hundred CHF, one-time per developer | none | none — battle-tested accuracy from day one |
| **Skyfield + JPL DE440** | free (MIT code, public-domain data) | ~2 weeks to implement Lahiri ayanamsa and sidereal conversion, plus validation | correctness risk until validated against published panchangs |
| **Open-source JanmaPath** | free | none | gives away the engine, which is the moat |

**Recommendation.** Buy the commercial licence. The cost is trivial against a
funded product and it removes both a legal question and a correctness risk from
the critical path.

**Why it cannot drift.** The engine's public API will be shaped by whichever
library it is built on. Swapping after Phase 1 means rewriting and re-validating
the module that everything else depends on. Resolve it while `apps/astro` is
still small.

---

## ADR-005 · One-time payment for a fixed access period

**Status:** Accepted · 2026-09-14

**Decision.** The subscription is a single payment granting access for a fixed
period. It does not auto-renew.

**Why.**

This sidesteps the RBI e-mandate / Additional Factor of Authentication regime for
recurring auto-debit entirely — no mandate registration, no pre-debit
notification obligations, no card-on-file complexity, no failed-renewal dunning
flows.

It is also more honest, which suits a product asking for trust with intimate
personal data.

**Trade-off.** Lower lifetime value per user than auto-renewal, and renewal
becomes an active marketing job rather than a default.

**Revisit if.** Retention data shows renewal friction is costing more than the
compliance work would. UPI Autopay is the lighter path if so — considerably
simpler than card e-mandates.

---

## ADR-006 · Entitlements are a separate layer from payments

**Status:** Accepted · 2026-09-14

**Decision.** Payments *grant* entitlements. Every feature gate queries the
entitlement layer and never asks "did this user pay?".

```
payment (captured) ──▶ entitlement(user, plan, starts_at, ends_at)
                            └──▶ feature_quota(user, feature, limit, used)
```

**Why.**

Free credits, promotional grants, comped months, partial refunds, gifting, and
support making a customer whole all become entitlement operations rather than
payment fictions. Without this layer, every one of those needs a fake payment
record or a special case in the gate — and that is how billing systems become
unmaintainable.

The cost is one extra table and one indirection. The saving is a future rewrite.

---

## ADR-007 · Authentication flow adjustments

**Status:** Accepted · 2026-09-14

**Decision.**

1. Login requires **either** OTP **or** password — never both.
2. Google registration **requires phone verification** but makes the password
   optional.

**Why.**

*On (1):* requiring OTP *and* password at every login is unusual in the Indian
market and adds friction on the highest-traffic path in the product. The OTP
already proves possession of the phone; the password adds a step without adding
meaningful security.

*On (2):* the phone number is both the canonical identity and the WhatsApp
delivery channel — an account without one cannot receive the core product, so
verification is mandatory regardless of signup path. A password *after* Google is
redundant: Google already is the credential, and a second one is one more thing
to leak. Offered, not required.

**Original specification.** Login by phone + OTP + password together; mandatory
password after Google signup. Changed with the product owner's agreement.

---

## ADR-008 · The LLM narrates; it never calculates

**Status:** Accepted · 2026-09-14

**Decision.** The astrology engine produces structured findings. The LLM receives
those findings as strict JSON and converts them to prose in the user's language.
It never computes a placement, infers a dosha, or introduces a claim absent from
the findings.

**Why.**

Astrological calculation is deterministic arithmetic with correct answers. An LLM
asked to perform it will produce fluent, plausible, inconsistent output — the
same user could get different planetary positions on different days. That is
fatal for a product whose entire credibility rests on the chart being right.

Separating the two also makes narration **cacheable by finding-signature**, which
is what makes the daily horoscope economically viable at scale (see
`ARCHITECTURE.md` §9).

**Consequence.** Prompts are constrained and the finding schema is versioned.
Narrative cache keys include `content_version`, so a schema change invalidates
stale prose rather than silently mixing generations.

---

## ADR-009 · Value-forward paywall framing

**Status:** Accepted · 2026-09-14

**Decision.** The paywall is framed around what the user gains, never around fear
of an undiagnosed dosha. No countdown timers, no artificial scarcity, no
confirm-shaming decline copy.

**Why.**

India's CCPA Dark Patterns guidelines (2023) explicitly name *false urgency* and
*confirm shaming* as prohibited practices, and ASCI restricts absolute claims.
"Dosha found — pay to see what it means" sits directly on that line.

The paywall itself is entirely legitimate. Only the framing creates exposure, and
the compliant version converts comparably. A persistent "for guidance and
entertainment purposes" disclaimer accompanies every report and horoscope
surface.

This is a cheap decision now and an expensive one to retrofit under a complaint.

---

## ADR-010 · The astrology engine is a pure module

**Status:** Accepted · 2026-09-14

**Decision.** `apps/astro/` contains **no Django imports and performs no I/O**.
Birth data in, chart object out. Persistence, jobs and presentation all live in
`apps/kundli/`.

**Why.**

Determinism is a product requirement, not a style preference — the same birth
data must always produce the same chart, and users will compare against other
software. A pure module can be unit-tested exhaustively against reference charts
with no database, no fixtures and no framework setup.

It also insulates the one genuinely differentiating part of the codebase from
framework churn, and leaves it trivially extractable as a service or a licensed
library later.

**Consequence.** Every chart is stored with its `engine_version` and `ayanamsa`.
Improving the engine never silently mutates existing users' charts; recomputation
is a deliberate, auditable migration.
