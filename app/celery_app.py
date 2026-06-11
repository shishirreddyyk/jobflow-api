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
)

# Register tasks defined in app/tasks.py with the worker.
celery_app.autodiscover_tasks(["app"])
