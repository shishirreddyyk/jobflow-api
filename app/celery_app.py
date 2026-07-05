"""Celery application instance.

Broker and result backend default to Redis. Set CELERY_TASK_ALWAYS_EAGER=true
to run tasks synchronously in-process (used by the test suite and CI, so no
broker is required there).
"""
import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "jobflow",
    broker=os.getenv("CELERY_BROKER_URL", REDIS_URL),
    backend=os.getenv("CELERY_RESULT_BACKEND", REDIS_URL),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true",
    task_eager_propagates=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Register tasks defined in app/tasks.py with the worker.
celery_app.autodiscover_tasks(["app"])


# Expose worker-process metrics for Prometheus (skipped in eager/test mode).
from celery.signals import worker_ready  # noqa: E402


@worker_ready.connect
def _start_metrics_server(**_kwargs):
    if not celery_app.conf.task_always_eager:
        from app.metrics import start_worker_metrics_server

        start_worker_metrics_server()
