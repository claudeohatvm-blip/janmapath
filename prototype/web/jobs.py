"""In-memory job store for the prototype.

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

_JOBS: dict[str, "Job"] = {}
_LOCK = threading.Lock()


@dataclass
class Job:
    id: str
    birth: BirthData
    events: queue.Queue = field(default_factory=queue.Queue)
    chart: dict[str, Any] | None = None
    error: str | None = None
    finished: threading.Event = field(default_factory=threading.Event)


def start(birth: BirthData) -> str:
    job = Job(id=uuid.uuid4().hex[:12], birth=birth)
    with _LOCK:
        _JOBS[job.id] = job

    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job.id


def get(job_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(job_id)


def _run(job: Job) -> None:
    def on_stage(stage: Stage, index: int, total: int) -> None:
        job.events.put({"type": "stage", "stage": stage.value, "index": index, "total": total})

    try:
        job.chart = compute_chart(job.birth, as_of=date.today(), on_stage=on_stage)
        job.events.put({"type": "done", "job_id": job.id})
    except Exception as exc:                      # noqa: BLE001 - surfaced to the UI
        job.error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        job.events.put({"type": "error", "message": job.error})
    finally:
        job.finished.set()
