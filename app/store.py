"""Job persistence.

Two interchangeable backends:
  - RedisJobStore: durable, shared across the API and Celery worker processes.
  - InMemoryJobStore: process-local, used for tests and CI (no Redis needed).

The backend is chosen by the JOBFLOW_STORE env var ("redis" by default,
"memory" for tests). A module-level singleton keeps the same instance across
the API request handlers and (in eager mode) the Celery task.
"""
import json
import os
from typing import List, Optional


class JobStore:
    def create(self, job: dict) -> None:
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[dict]:
        raise NotImplementedError

    def update(self, job_id: str, **fields) -> None:
        raise NotImplementedError

    def list(self, status: Optional[str] = None) -> List[dict]:
        raise NotImplementedError

    def delete(self, job_id: str) -> bool:
        raise NotImplementedError


class InMemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}

    def create(self, job: dict) -> None:
        self._jobs[job["id"]] = dict(job)

    def get(self, job_id: str) -> Optional[dict]:
        job = self._jobs.get(job_id)
        return dict(job) if job else None

    def update(self, job_id: str, **fields) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].update(fields)

    def list(self, status: Optional[str] = None) -> List[dict]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return [dict(j) for j in jobs]

    def delete(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None


class RedisJobStore(JobStore):
    def __init__(self, url: str) -> None:
        import redis  # imported lazily so tests don't require the package

        self.r = redis.Redis.from_url(url, decode_responses=True)

    @staticmethod
    def _key(job_id: str) -> str:
        return f"job:{job_id}"

    def create(self, job: dict) -> None:
        self.r.set(self._key(job["id"]), json.dumps(job))
        self.r.sadd("jobs", job["id"])

    def get(self, job_id: str) -> Optional[dict]:
        raw = self.r.get(self._key(job_id))
        return json.loads(raw) if raw else None

    def update(self, job_id: str, **fields) -> None:
        raw = self.r.get(self._key(job_id))
        if not raw:
            return
        job = json.loads(raw)
        job.update(fields)
        self.r.set(self._key(job_id), json.dumps(job))

    def list(self, status: Optional[str] = None) -> List[dict]:
        out: List[dict] = []
        for job_id in self.r.smembers("jobs"):
            raw = self.r.get(self._key(job_id))
            if not raw:
                continue
            job = json.loads(raw)
            if status is None or job["status"] == status:
                out.append(job)
        return out

    def delete(self, job_id: str) -> bool:
        existed = self.r.delete(self._key(job_id))
        self.r.srem("jobs", job_id)
        return bool(existed)


_store_singleton: Optional[JobStore] = None


def get_store() -> JobStore:
    global _store_singleton
    if _store_singleton is None:
        backend = os.getenv("JOBFLOW_STORE", "redis")
        if backend == "memory":
            _store_singleton = InMemoryJobStore()
        else:
            _store_singleton = RedisJobStore(
                os.getenv("REDIS_URL", "redis://localhost:6379/0")
            )
    return _store_singleton
