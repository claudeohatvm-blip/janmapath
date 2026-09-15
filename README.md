# JanmaPath

**India's first personalized astrology companion.**

JanmaPath computes a user's Vedic kundli from their birth data, generates a
personalized life report, delivers a daily personalized horoscope over WhatsApp,
and connects users to real remedies — poojas, temple prasad, printed reports, and
live consultations with human astrologers.

---

## Status

Pre-implementation. This repository currently contains the agreed architecture
and build plan. No application code has been written yet.

## Documentation

| Document | What it covers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System topology, the four services, schema requirements, auth, async pipelines, security |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Full schema detail *(pending update to the single-Postgres stack)* |
| [`docs/USER_FLOWS.md`](docs/USER_FLOWS.md) | Canonical product flows — registration through fulfilment |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phased build plan with scope and exit criteria |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architecture decision records *(ADR-002 and ADR-003 superseded — pending update)* |

## Stack at a glance

| Layer | Choice |
|---|---|
| Client UI | `janmapath.com` — React + Vite SPA, marketing routes pre-rendered |
| Staff UI | `manage.janmapath.com` — React + Vite SPA, separate build |
| API | `api.janmapath.com` — Django REST Framework, JWT + RBAC |
| Styling | Tailwind CSS, Framer Motion |
| Database | PostgreSQL 16 — relational core + `JSONField` for chart payloads |
| Cache / broker | Redis — OTP TTL, rate limits, Celery |
| Async work | Celery + Celery Beat |
| Astrology engine | Pure Python module (`apps/astro`), run inside Celery workers |
| Payments | Razorpay |
| Messaging | MSG91 — WhatsApp + DLT-registered SMS |
| Deployment | Docker Compose behind Nginx, `asia-south1` (Mumbai) |

## Product surface

**Free tier** — Vedic kundli generation, basic chart summary, dosha detection headline.

**Subscription (one-time payment, fixed access period)**
- Full life report — current status, marital, financial forecast, doshas
- Daily personalized horoscope on WhatsApp, 6:00 AM IST
- Detailed financial forecast
- 30 horoscope (Guna Milan) matches
- Remedies and dosha guidance

**Paid add-ons**
- Additional matches beyond the 30 included
- Pooja / remedy performed on the user's behalf
- Temple prasad delivered by parcel
- Printed life report and horoscope, posted after the pooja
- Live consultation with a verified astrologer, in the user's language

## Local development

Not yet available — see [`docs/ROADMAP.md`](docs/ROADMAP.md) Phase 0.

## Licence

Proprietary. All rights reserved.
