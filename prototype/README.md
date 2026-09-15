# Engine prototype

A minimal Django app that drives `apps/astro` from a browser. No database, no
auth, no DRF - it exists to prove the engine and the staged-generation flow work
end to end.

## Run

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python prototype/manage.py runserver 8000
```

Open <http://127.0.0.1:8000>.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Birth-details form |
| `POST /generate` | Starts a background job, redirects to the progress screen |
| `GET /generating/<id>` | Progress screen, subscribes to the stream |
| `GET /stream/<id>` | **SSE** - emits each stage as it genuinely completes |
| `GET /chart/<id>` | Rendered chart |
| `GET /api/chart/<id>` | Raw engine output as JSON |

## What is deliberately not production

| Prototype | Production |
|---|---|
| In-memory job dict (`web/jobs.py`) | Celery task + `chart_jobs` row |
| Hardcoded place list (`web/places.py`) | Google Places / Mapbox + cached `places` table |
| Server-rendered Django templates | React SPA on DRF; chart drawn client-side as SVG |
| Chart discarded on restart | Persisted to `KundliProfile.planetary_data` |
| No auth | Phone OTP / Google, JWT, RBAC |

The engine itself (`apps/astro/`) **is** production code - no Django import, no
I/O - so it moves into the real app unchanged.

## Try the unknown-birth-time path

Select "I don't know it". The ascendant, houses and Navamsa are withheld and the
page says so plainly. Moon sign, nakshatra, dasha and the Moon-based dosha rules
still compute.

## Tests

```bash
.venv/bin/python -m pytest
```
