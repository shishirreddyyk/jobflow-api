"""API tests. Run with: pytest -q

These configure the in-memory store and eager Celery execution so the suite
runs with no Redis and no worker (same settings CI uses).
"""
import os

os.environ.setdefault("JOBFLOW_STORE", "memory")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_submit_runs_echo_job_to_completion():
    resp = client.post("/jobs", json={"task_type": "echo", "params": {"msg": "hi"}})
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    fetched = client.get(f"/jobs/{job_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "completed"
    assert body["result"] == {"echo": {"msg": "hi"}}
    assert body["finished_at"] is not None


def test_compute_job_returns_result():
    resp = client.post(
        "/jobs", json={"task_type": "compute", "params": {"iterations": 1000}}
    )
    job_id = resp.json()["id"]
    body = client.get(f"/jobs/{job_id}").json()
    assert body["status"] == "completed"
    assert body["result"]["iterations"] == 1000


def test_unknown_task_type_is_rejected_by_validation():
    resp = client.post("/jobs", json={"task_type": "not_a_real_type", "params": {}})
    assert resp.status_code == 422


def test_get_missing_job_returns_404():
    assert client.get("/jobs/doesnotexist").status_code == 404


def test_list_filters_by_status():
    client.post("/jobs", json={"task_type": "echo", "params": {}})
    resp = client.get("/jobs", params={"status": "completed"})
    assert resp.status_code == 200
    assert all(job["status"] == "completed" for job in resp.json())


def test_delete_removes_job():
    job_id = client.post("/jobs", json={"task_type": "echo", "params": {}}).json()["id"]
    assert client.delete(f"/jobs/{job_id}").status_code == 204
    assert client.get(f"/jobs/{job_id}").status_code == 404
