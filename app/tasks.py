"""Celery task that runs a queued job and records its lifecycle in the store."""
import hashlib
import time
from typing import Any

from app.celery_app import celery_app
from app.metrics import track_job
from app.store import get_store


@celery_app.task(name="jobflow.run_job", bind=True, max_retries=3)
def run_job(self, job_id: str, task_type: str, params: dict) -> Any:
    store = get_store()
    store.update(job_id, status="running", started_at=time.time())
    try:
        with track_job(task_type):
            result = _execute(task_type, params)
    except Exception as exc:  # noqa: BLE001 - record failure, then re-raise
        store.update(job_id, status="failed", error=str(exc), finished_at=time.time())
        raise
    store.update(job_id, status="completed", result=result, finished_at=time.time())
    return result


def _execute(task_type: str, params: dict) -> Any:
    """A small set of demo workloads.

    - echo:    returns the params (fast, I/O-free) - good for throughput tests
    - sleep:   simulates an I/O-bound job
    - compute: simulates a CPU-bound job (hash a configurable number of items)
    """
    if task_type == "echo":
        return {"echo": params}
    if task_type == "sleep":
        seconds = float(params.get("seconds", 1))
        time.sleep(seconds)
        return {"slept_seconds": seconds}
    if task_type == "compute":
        iterations = int(params.get("iterations", 100_000))
        digest = hashlib.sha256()
        for i in range(iterations):
            digest.update(str(i).encode())
        return {"iterations": iterations, "digest": digest.hexdigest()[:16]}
    raise ValueError(f"unknown task_type: {task_type}")
