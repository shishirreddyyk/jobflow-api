"""Load test for JobFlow API.

Run the stack (docker compose up), then:
    locust -f loadtest/locustfile.py --host http://localhost:8000

Open http://localhost:8089, set users + spawn rate, and run. The Locust UI
reports requests/sec and p50/p95/p99 latency - use those REAL numbers on your
resume, not invented ones.
"""
from locust import HttpUser, between, task


class JobFlowUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(4)
    def submit_echo(self):
        self.client.post("/jobs", json={"task_type": "echo", "params": {"msg": "load"}})

    @task(1)
    def submit_compute(self):
        self.client.post(
            "/jobs", json={"task_type": "compute", "params": {"iterations": 20000}}
        )

    @task(2)
    def health(self):
        self.client.get("/health")
