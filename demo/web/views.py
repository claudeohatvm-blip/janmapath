"""Views for the JanmaPath demo.

Collects birth details, runs the engine with live staged progress, renders the
life report, and offers the whole report as a PDF.
"""

from __future__ import annotations

import json
import time as time_module
from datetime import date, datetime, time

from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from apps.astro.engine import stage_labels
from apps.astro.types import BirthData, TimeAccuracy
from apps.reports import narrator_ai, pdf
from apps.reports.builder import build

from . import jobs, places

# Each stage holds the screen for at least this long. The computation finishes
# in well under a second; the dwell gives the reader time to see what is
# actually happening rather than watching nine lines flash past.
STAGE_MIN_DWELL_SECONDS = 0.55


def _form_context(**extra) -> dict:
    return {
        "places": places.PLACES,
        "today": date.today().isoformat(),
        "languages": narrator_ai.LANGUAGES,
        "ai": narrator_ai.status(),
        **extra,
    }


def form(request: HttpRequest) -> HttpResponse:
    return render(request, "web/form.html", _form_context())


def generate(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("form")

    data = request.POST

    def fail(message: str) -> HttpResponse:
        return render(request, "web/form.html", _form_context(error=message), status=400)

    try:
        accuracy = TimeAccuracy(data.get("time_accuracy", "exact"))
    except ValueError:
        return fail("Please say how sure you are of the birth time.")

    birth_time = None
    if accuracy is not TimeAccuracy.UNKNOWN:
        raw = data.get("birth_time", "").strip()
        if not raw:
            return fail("Birth time is required unless you select “I don’t know it”.")
        try:
            birth_time = time.fromisoformat(raw)
        except ValueError:
            return fail("That birth time could not be read. Use HH:MM.")

    place = places.lookup(data.get("place", ""))
    if place is None:
        return fail("Please choose a birth place from the list.")

    try:
        birth = BirthData(
            name=data.get("name", "").strip() or "Friend",
            gender=data.get("gender", "").strip(),
            birth_date=datetime.strptime(data.get("birth_date", ""), "%Y-%m-%d").date(),
            birth_time=birth_time,
            time_accuracy=accuracy,
            latitude=place["lat"],
            longitude=place["lon"],
            tz_id=place["tz_id"],
            place_name=place["name"],
        )
    except (KeyError, ValueError) as exc:
        return fail(str(exc))

    if birth.birth_date > date.today():
        return fail("Birth date cannot be in the future.")

    use_ai = data.get("use_ai") == "on" and narrator_ai.is_configured()
    language = data.get("language", "en")

    return redirect("generating", job_id=jobs.start(birth, use_ai=use_ai, language=language))


def generating(request: HttpRequest, job_id: str) -> HttpResponse:
    job = jobs.get(job_id)
    if job is None:
        raise Http404("No such reading")
    labels = stage_labels()
    if job.use_ai:
        labels = [*labels, "Composing your reading"]
    return render(
        request,
        "web/generating.html",
        {"job_id": job_id, "stages": labels, "stage_json": json.dumps(labels)},
    )


def stream(request: HttpRequest, job_id: str) -> StreamingHttpResponse:
    """Server-sent events carrying real stage completions."""
    job = jobs.get(job_id)
    if job is None:
        raise Http404("No such reading")

    def events():
        while True:
            event = job.events.get()
            if event["type"] == "stage":
                time_module.sleep(STAGE_MIN_DWELL_SECONDS)
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in {"done", "error"}:
                return

    response = StreamingHttpResponse(events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _require_finished(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise Http404("No such reading")
    return job


def report(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _require_finished(job_id)
    if job.error:
        return render(request, "web/error.html", {"error": job.error}, status=500)
    if job.chart is None:
        return redirect("generating", job_id=job_id)

    return render(request, "web/report.html", _report_context(job, job_id))


def _report_context(job, job_id: str) -> dict:
    chart = job.chart
    doshas_found = [d for d in chart["analysis"]["doshas"] if d["present"]]
    return {
        "job_id": job_id,
        "chart": chart,
        "report": job.report,
        "sections": job.report.sections,
        "doshas_found": doshas_found,
        "dosha_count": len(doshas_found),
        "suppressed": chart["analysis"]["suppressed"],
        "current_dasha": chart["dashas"]["vimshottari"]["current"],
        "grid": _chart_grid(chart),
        "navamsa_grid": _varga_grid(chart, "D9"),
        "pdf_available": pdf.is_available(),
    }


def report_pdf(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _require_finished(job_id)
    if job.chart is None:
        return redirect("generating", job_id=job_id)

    context = _report_context(job, job_id)
    html = render_to_string("web/report_pdf.html", context, request=request)

    if not pdf.is_available():
        # Print-optimised HTML; the browser's own print dialogue saves it as PDF.
        response = HttpResponse(html)
        response["X-PDF-Fallback"] = "browser-print"
        return response

    name = (job.chart["input"]["name"] or "reading").replace(" ", "-").lower()
    response = HttpResponse(
        pdf.render(html, base_url=request.build_absolute_uri("/")),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="janmapath-{name}.pdf"'
    return response


def chart_json(request: HttpRequest, job_id: str) -> JsonResponse:
    """The raw engine output, for inspection."""
    job = _require_finished(job_id)
    if job.chart is None:
        raise Http404("No chart yet")
    return JsonResponse(job.chart, json_dumps_params={"indent": 2})


def setup_ai(request: HttpRequest) -> HttpResponse:
    """How to obtain and configure an API key, with a live status check.

    Passing ?models=1 additionally queries the provider for the model IDs this
    key can actually reach. That costs a network round trip, so it is opt-in
    rather than run on every page load.
    """
    ai = narrator_ai.status()
    models: list[dict] = []
    checked = request.GET.get("models") == "1"

    if checked:
        provider = narrator_ai.active_provider()
        lister = getattr(provider, "list_models", None) if provider else None
        if lister is not None:
            models = lister()

    return render(
        request,
        "web/setup_ai.html",
        {
            "ai": ai,
            "languages": narrator_ai.LANGUAGES,
            "pdf_available": pdf.is_available(),
            "pdf_reason": pdf.unavailable_reason(),
            "models": models,
            "models_checked": checked,
        },
    )


# --- Chart diagrams -----------------------------------------------------------

_ABBREVIATIONS = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke",
}

# South Indian chart: signs are fixed in place and the chart is read clockwise
# from whichever square holds the ascendant. (row, column) -> sign index, on a
# 4x4 grid with a hollow 2x2 centre.
_SOUTH_INDIAN_GRID: tuple[tuple[int, int, int], ...] = (
    (1, 1, 11), (1, 2, 0), (1, 3, 1), (1, 4, 2),
    (2, 1, 10),                       (2, 4, 3),
    (3, 1, 9),                        (3, 4, 4),
    (4, 1, 8), (4, 2, 7), (4, 3, 6), (4, 4, 5),
)


def _grid_from(asc_sign: int, by_sign: dict[int, list[str]]) -> list[dict]:
    from apps.astro.constants import SIGNS

    return [
        {
            "row": row,
            "col": col,
            "sign": SIGNS[sign_index],
            "house": ((sign_index - asc_sign) % 12) + 1,
            "is_ascendant": sign_index == asc_sign,
            "occupants": by_sign.get(sign_index, []),
        }
        for row, col, sign_index in _SOUTH_INDIAN_GRID
    ]


def _chart_grid(chart: dict) -> list[dict] | None:
    """D1 squares with their occupants.

    Production draws this client-side as SVG from raw degrees, which keeps the
    payload small and lets the reader switch North/South style without a round
    trip. The demo groups server-side to keep the template dependency-free.
    """
    if not chart["houses"]:
        return None
    by_sign: dict[int, list[str]] = {}
    for planet in chart["planets"]:
        by_sign.setdefault(planet["sign_index"], []).append(
            _ABBREVIATIONS[planet["body"]] + ("ᴿ" if planet["retrograde"] else "")
        )
    return _grid_from(chart["ascendant"]["sign_index"], by_sign)


def _varga_grid(chart: dict, name: str) -> list[dict] | None:
    varga = (chart.get("vargas") or {}).get(name)
    if not varga:
        return None
    by_sign: dict[int, list[str]] = {}
    for placement in varga["placements"]:
        by_sign.setdefault(placement["sign_index"], []).append(
            _ABBREVIATIONS[placement["body"]]
        )
    return _grid_from(varga["ascendant_sign_index"], by_sign)
