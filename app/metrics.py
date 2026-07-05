"""Application metrics for JobFlow, exposed to Prometheus.

The API process exposes these on GET /metrics (see app.main). The Celery
worker records the same job metrics and exposes them on its own port via
start_worker_metrics_server() so Prometheus can scrape both.

Job counters/histograms are labelled by task_type so a dashboard can break
throughput and latency down per workload (echo / sleep / compute).
"""
import os
import time
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram, start_http_server

JOBS_SUBMITTED = Counter(
    "jobflow_jobs_submitted_total",
    "Jobs accepted by the API and enqueued.",
    ["task_type"],
)

JOBS_FINISHED = Counter(
    "jobflow_jobs_finished_total",
    "Jobs that finished, by terminal status.",
    ["task_type", "status"],  # status: completed | failed
)

JOB_DURATION = Histogram(
    "jobflow_job_duration_seconds",
    "Wall-clock time a job spent running in the worker.",
    ["task_type"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

JOBS_IN_PROGRESS = Gauge(
    "jobflow_jobs_in_progress",
    "Jobs currently executing in the worker.",
)


def record_submitted(task_type: str) -> None:
    JOBS_SUBMITTED.labels(task_type=task_type).inc()


@contextmanager
def track_job(task_type: str):
    """Time a job and record its outcome, in-progress count, and duration."""
    JOBS_IN_PROGRESS.inc()
    start = time.perf_counter()
    status = "completed"
    try:
        yield
    except Exception:
        status = "failed"
        raise
    finally:
        JOB_DURATION.labels(task_type=task_type).observe(time.perf_counter() - start)
        JOBS_FINISHED.labels(task_type=task_type, status=status).inc()
        JOBS_IN_PROGRESS.dec()


def start_worker_metrics_server() -> None:
    """Expose worker metrics on METRICS_PORT (default 9200) for Prometheus."""
    port = int(os.getenv("METRICS_PORT", "9200"))
    start_http_server(port)
