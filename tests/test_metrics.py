"""Metrics endpoint tests. In eager mode the task runs in-process, so the job
metrics register here too - which is what lets CI verify them with no worker."""
import os

os.environ.setdefault("JOBFLOW_STORE", "memory")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_metrics_endpoint_exposes_prometheus_text():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    # FastAPI request metrics from the instrumentator are present.
    assert "http_request" in resp.text


def test_job_metrics_increment_after_a_run():
    client.post("/jobs", json={"task_type": "echo", "params": {"msg": "hi"}})
    body = client.get("/metrics").text
    assert "jobflow_jobs_submitted_total" in body
    assert "jobflow_jobs_finished_total" in body
    assert "jobflow_job_duration_seconds" in body
    # the echo job we just submitted completed
    assert 'jobflow_jobs_finished_total{status="completed",task_type="echo"}' in body


def test_failed_job_is_counted_as_failed():
    # track_job records a failure and re-raises; assert the failed counter shows up.
    import pytest

    from app.metrics import track_job

    with pytest.raises(RuntimeError):
        with track_job("compute"):
            raise RuntimeError("boom")

    body = client.get("/metrics").text
    assert 'jobflow_jobs_finished_total{status="failed",task_type="compute"}' in body
