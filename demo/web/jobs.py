"""In-memory job store for the demo.

Production runs chart generation as a Celery task and persists the result. This
module exists only so the browser can watch real stages complete over SSE
without standing up a broker and a database first.
"""

from __future__ import annotations

import queue
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from apps.astro.engine import compute_chart
from apps.astro.types import BirthData, Stage
from apps.reports.builder import build
from apps.reports.schema import Report

_JOBS: dict[str, "Job"] = {}
_LOCK = threading.Lock()
_MAX_JOBS = 200


@dataclass
class Job:
    id: str
    birth: BirthData
    use_ai: bool = False
    language: str = "en"
    events: queue.Queue = field(default_factory=queue.Queue)
    chart: dict[str, Any] | None = None
    report: Report | None = None
    error: str | None = None
    finished: threading.Event = field(default_factory=threading.Event)


def start(birth: BirthData, *, use_ai: bool = False, language: str = "en") -> str:
    job = Job(id=uuid.uuid4().hex[:12], birth=birth, use_ai=use_ai, language=language)
    with _LOCK:
        # Bounded so a long-running demo does not grow without limit.
        if len(_JOBS) >= _MAX_JOBS:
            for stale in list(_JOBS)[: _MAX_JOBS // 2]:
                _JOBS.pop(stale, None)
        _JOBS[job.id] = job

    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job.id


def get(job_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(job_id)


def _run(job: Job) -> None:
    total_extra = 1 if job.use_ai else 0

    def on_stage(stage: Stage, index: int, total: int) -> None:
        job.events.put(
            {
                "type": "stage",
                "stage": stage.value,
                "index": index,
                "total": total + total_extra,
            }
        )

    try:
        job.chart = compute_chart(job.birth, as_of=date.today(), on_stage=on_stage)

        job.report = build(job.chart, use_ai=job.use_ai, language=job.language)

        if job.use_ai:
            job.events.put(
                {
                    "type": "stage",
                    "stage": "Composing your reading",
                    "index": 10,
                    "total": 10,
                }
            )

        job.events.put({"type": "done", "job_id": job.id})
    except Exception as exc:                      # noqa: BLE001 - surfaced to the UI
        job.error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        job.events.put({"type": "error", "message": job.error})
    finally:
        job.finished.set()
