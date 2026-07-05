# JobFlow API

An async job-orchestration service: a **FastAPI** REST API accepts jobs, enqueues
them onto **Celery** (with a **Redis** broker), and a separate worker pool runs
them. Clients submit a job, get a job ID back immediately, and poll for status
and results. Containerized with Docker for deployment to AWS / Kubernetes.

This is the production-style sibling of my Node.js distributed job queue
(DistroQ), rebuilt on the Python async stack.

## Architecture

```
client ──HTTP──> FastAPI (app/main.py)
                    │  enqueue
                    ▼
                 Redis (broker + result/state store)
                    │  dequeue
                    ▼
                 Celery worker (app/tasks.py) ──updates──> Redis job store
```

- `app/main.py`     - REST endpoints (submit, get, list, delete, health)
- `app/tasks.py`    - Celery task that runs the job and records its lifecycle
- `app/store.py`    - job state store (Redis in prod, in-memory for tests)
- `app/celery_app.py` - Celery configuration
- `app/models.py`   - Pydantic request/response schemas

## Endpoints

| Method | Path             | Purpose                                  |
|--------|------------------|------------------------------------------|
| GET    | `/health`        | Liveness check                           |
| POST   | `/jobs`          | Submit a job, returns job ID + status    |
| GET    | `/jobs/{id}`     | Get a job's status and result            |
| GET    | `/jobs?status=`  | List jobs, optionally filtered by status |
| DELETE | `/jobs/{id}`     | Delete a job                             |

Interactive API docs (Swagger UI) are served at `/docs` once running.

Job types: `echo` (fast, I/O-free), `sleep` (I/O-bound), `compute` (CPU-bound).

## Run it (Docker)

```bash
docker compose up --build
```

This starts Redis, the API (http://localhost:8000), and a Celery worker.

```bash
# submit a job
curl -X POST localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"task_type": "compute", "params": {"iterations": 200000}}'

# poll for the result (use the id from the response above)
curl localhost:8000/jobs/<job_id>
```

## Run it (local, no Docker)

```bash
pip install -r requirements.txt
# terminal 1 - Redis must be running locally on :6379
# terminal 2 - worker
celery -A app.celery_app.celery_app worker --loglevel=info
# terminal 3 - API
uvicorn app.main:app --reload
```

## Tests

No Redis or worker required - the suite uses the in-memory store and runs
Celery tasks eagerly (the same way CI does):

```bash
JOBFLOW_STORE=memory CELERY_TASK_ALWAYS_EAGER=true pytest -q
```

CI runs on every push via `.github/workflows/ci.yml`.

## Load test (get your REAL numbers)

```bash
docker compose up --build           # start the stack first
locust -f loadtest/locustfile.py --host http://localhost:8000
```

Open http://localhost:8089, choose a user count and spawn rate, and run. The
Locust UI reports **requests/sec** and **p50/p95/p99 latency**. Put *those*
measured numbers on your resume - never invented ones.

## Deployment notes

The image is a single Dockerfile, so the API and worker deploy as separate
containers/pods sharing a managed Redis (e.g. AWS ElastiCache). On Kubernetes,
run the API and worker as two Deployments and scale the worker independently of
the API based on queue depth.

## Observability (Prometheus + Grafana)

The API and worker export Prometheus metrics, and `docker compose up` brings up
a Prometheus + Grafana stack with a pre-provisioned dashboard.

**Metrics exported**

- API (`GET /metrics`, via prometheus-fastapi-instrumentator): `http_requests_total`,
  `http_request_duration_seconds` (request rate, latency, status).
- Jobs (`app/metrics.py`, recorded in the worker and scraped on `:9200`):
  - `jobflow_jobs_submitted_total{task_type}`
  - `jobflow_jobs_finished_total{task_type,status}` (status = completed | failed)
  - `jobflow_job_duration_seconds{task_type}` (histogram)
  - `jobflow_jobs_in_progress` (gauge)

The worker runs with a threads pool so job metrics live in one process and are
scrapeable; `worker_ready` starts the metrics server (skipped in eager/test mode).

**Run it**

```
docker compose up --build
```

- API: http://localhost:8000  (metrics at `/metrics`)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000  (dashboard "JobFlow - API & Jobs", anonymous view enabled)

Generate some load to see the panels move:

```
pip install locust
locust -f loadtest/locustfile.py --host http://localhost:8000
```

**Dashboard panels:** API request rate, API p95 latency, job throughput by status,
job duration p95 by task type, jobs in progress, submitted and failed totals.

The job metrics are covered by tests (`tests/test_metrics.py`) that run in eager
mode in CI, so `/metrics` and the counters are verified on every push.
