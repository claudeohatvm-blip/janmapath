"""Prototype views: form, staged generation over SSE, and the chart result."""

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

from apps.astro.types import BirthData, TimeAccuracy

from . import jobs, places

# Each stage holds the screen for at least this long. The computation itself
# finishes in well under a second; the dwell gives the user time to read what
# is actually happening rather than watching six lines flash past.
STAGE_MIN_DWELL_SECONDS = 0.7


def form(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "web/form.html",
        {"places": places.PLACES, "today": date.today().isoformat()},
    )


def generate(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("form")

    data = request.POST
    accuracy = TimeAccuracy(data.get("time_accuracy", "exact"))

    birth_time = None
    if accuracy is not TimeAccuracy.UNKNOWN:
        raw = data.get("birth_time", "").strip()
        if not raw:
            return render(
                request,
                "web/form.html",
                {
                    "places": places.PLACES,
                    "today": date.today().isoformat(),
                    "error": "Birth time is required unless you select “I don’t know it”.",
                },
                status=400,
            )
        birth_time = time.fromisoformat(raw)

    place = places.lookup(data.get("place", ""))
    if place is None:
        return render(
            request,
            "web/form.html",
            {
                "places": places.PLACES,
                "today": date.today().isoformat(),
                "error": "Please choose a birth place from the list.",
            },
            status=400,
        )

    try:
        birth = BirthData(
            name=data.get("name", "").strip(),
            gender=data.get("gender", "").strip(),
            birth_date=datetime.strptime(data["birth_date"], "%Y-%m-%d").date(),
            birth_time=birth_time,
            time_accuracy=accuracy,
            latitude=place["lat"],
            longitude=place["lon"],
            tz_id=place["tz_id"],
        )
    except (KeyError, ValueError) as exc:
        return render(
            request,
            "web/form.html",
            {
                "places": places.PLACES,
                "today": date.today().isoformat(),
                "error": str(exc),
            },
            status=400,
        )

    return redirect("generating", job_id=jobs.start(birth))


def generating(request: HttpRequest, job_id: str) -> HttpResponse:
    if jobs.get(job_id) is None:
        raise Http404("No such job")
    return render(request, "web/generating.html", {"job_id": job_id})


def stream(request: HttpRequest, job_id: str) -> StreamingHttpResponse:
    """Server-sent events carrying real stage completions."""
    job = jobs.get(job_id)
    if job is None:
        raise Http404("No such job")

    def events():
        while True:
            event = job.events.get()
            # Hold each stage briefly so the sequence is readable.
            if event["type"] == "stage":
                time_module.sleep(STAGE_MIN_DWELL_SECONDS)
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in {"done", "error"}:
                return

    response = StreamingHttpResponse(events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def chart(request: HttpRequest, job_id: str) -> HttpResponse:
    job = jobs.get(job_id)
    if job is None:
        raise Http404("No such job")
    if job.error:
        return render(request, "web/error.html", {"error": job.error}, status=500)
    if job.chart is None:
        return redirect("generating", job_id=job_id)

    data = job.chart
    doshas_found = [d for d in data["analysis"]["doshas"] if d["present"]]

    return render(
        request,
        "web/chart.html",
        {
            "job_id": job_id,
            "chart": data,
            "doshas_found": doshas_found,
            "dosha_count": len(doshas_found),
            "suppressed": data["analysis"]["suppressed"],
            "current_dasha": data["dashas"]["vimshottari"]["current"],
            "grid": _chart_grid(data),
        },
    )


def chart_json(request: HttpRequest, job_id: str) -> JsonResponse:
    """The raw engine output, for inspection."""
    job = jobs.get(job_id)
    if job is None or job.chart is None:
        raise Http404("No chart")
    return JsonResponse(job.chart, json_dumps_params={"indent": 2})


_ABBREVIATIONS = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke",
}

# South Indian chart: the signs are fixed in place and the chart is read
# clockwise from whichever square holds the ascendant. Mapping is
# (row, column) -> sign index, on a 4x4 grid with a hollow 2x2 centre.
_SOUTH_INDIAN_GRID: tuple[tuple[int, int, int], ...] = (
    (1, 1, 11), (1, 2, 0), (1, 3, 1), (1, 4, 2),
    (2, 1, 10),                       (2, 4, 3),
    (3, 1, 9),                        (3, 4, 4),
    (4, 1, 8), (4, 2, 7), (4, 3, 6), (4, 4, 5),
)


def _chart_grid(data: dict) -> list[dict] | None:
    """Twelve fixed-sign squares with their occupants, for the diagram.

    Production draws this client-side as SVG from raw degrees, which keeps the
    payload small and lets the user switch North/South style without a round
    trip. The prototype groups server-side to keep the template dependency-free.
    """
    if not data["houses"]:
        return None

    asc_sign = data["ascendant"]["sign_index"]
    by_sign: dict[int, list[str]] = {}
    for planet in data["planets"]:
        by_sign.setdefault(planet["sign_index"], []).append(
            _ABBREVIATIONS[planet["body"]] + ("\u1d3f" if planet["retrograde"] else "")
        )

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
