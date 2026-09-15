# JanmaPath - demo

A complete, runnable slice of JanmaPath: collect birth details, compute a Vedic
kundli, and produce a life report covering marriage, finance, career and doshas,
downloadable as a PDF.

The astrology engine here (`apps/astro/`) is the real one. The Django layer is a
demo harness - no database, no accounts, no payments.

## Run

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python demo/manage.py runserver 8000
```

Open <http://127.0.0.1:8000>.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Birth details form |
| `POST /generate` | Starts the reading, redirects to the progress screen |
| `GET /generating/<id>` | Progress screen |
| `GET /stream/<id>` | **SSE** - each stage as it genuinely completes |
| `GET /report/<id>` | The full life report |
| `GET /report/<id>/pdf` | The same report as a PDF |
| `GET /api/chart/<id>` | Raw engine output as JSON |
| `GET /setup/ai` | How to obtain and configure an API key, with a live status check |

## Is there AI in this?

Not in any calculation. `apps/astro/` imports no network library at all - it
cannot reach a model even if asked to. Planetary positions, houses, divisional
charts, dasha, yogas, doshas and every score are deterministic arithmetic and
classical rule evaluation.

The report prose is written from rules and works with **no API key**. AI is an
optional rewrite for fluency and for languages other than English, and it may
not change a placement, score, band or conclusion. See `/setup/ai` in the running
app, or [`../docs/AI_SETUP.md`](../docs/AI_SETUP.md).

## What the report contains

| Section | Read from |
|---|---|
| Life reading | Lagna and its lord, Moon, Sun, running mahadasha, yogas |
| Marriage | 7th house and lord, partner karaka (Venus or Jupiter by gender), Navamsa 7th, Mangal dosha |
| Financial forecast | 2nd and 11th houses and lords, 9th, Jupiter, Dhana yogas, 12th |
| Career | 10th house and lord, Saturn, Sun, Dashamsha |
| Doshas | Mangal, Kaal Sarp, Sade Sati - with remedies where active |

Every section carries an evidence table listing the exact placements behind it,
so a reader can check the conclusion against the chart.

## What is deliberately not production

| Demo | Production |
|---|---|
| In-memory job dict (`web/jobs.py`) | Celery task + `chart_jobs` row |
| Hardcoded place list (`web/places.py`) | Google Places / Mapbox + cached `places` table |
| Server-rendered Django templates | React SPA on DRF; charts drawn client-side as SVG |
| Reading discarded on restart | Persisted to `KundliProfile.planetary_data` |
| No auth | Phone OTP / Google, JWT, RBAC |

## Try the unknown-birth-time path

Select "I don't know it". The ascendant, houses and divisional charts are
withheld and the report says so plainly - marriage, financial and career
readings are all house-based and are not produced. Moon sign, nakshatra, dasha
and the Moon-based dosha rules still compute.

## Tests

```bash
.venv/bin/python -m pytest
```
