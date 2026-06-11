"""JobFlow API - submit, track, and manage async jobs over REST.

Jobs are accepted by the API, enqueued onto Celery (Redis broker), and
processed by a separate worker. Clients poll for status and results.
"""
import time
import uuid
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from app.models import Job, JobCreate
from app.store import JobStore, get_store
from app.tasks import run_job

app = FastAPI(
    title="JobFlow API",
    version="1.0.0",
    description="Async job orchestration API (FastAPI + Celery + Redis).",
)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs", response_model=Job, status_code=201, tags=["jobs"])
def submit_job(body: JobCreate, store: JobStore = Depends(get_store)) -> dict:
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "task_type": body.task_type,
        "status": "queued",
        "params": body.params,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
    }
    store.create(job)
    run_job.delay(job_id, body.task_type, body.params)
    # Return the freshest view (in eager mode the job may already be done).
    return store.get(job_id) or job


@app.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
def get_job(job_id: str, store: JobStore = Depends(get_store)) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/jobs", response_model=List[Job], tags=["jobs"])
def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    store: JobStore = Depends(get_store),
) -> List[dict]:
    return store.list(status=status)


@app.delete("/jobs/{job_id}", status_code=204, tags=["jobs"])
def delete_job(job_id: str, store: JobStore = Depends(get_store)) -> None:
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail="job not found")
