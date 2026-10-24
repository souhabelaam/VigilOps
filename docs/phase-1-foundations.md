# Phase 1: Foundations

## What was built
Two small "target apps". They are the patients that VigilOps will monitor in later phases.

| App | Port | Purpose |
|---|---|---|
| `services/notes-api` | 8001 | Normal, calm app: create, list and delete notes. |
| `services/report-api` | 8002 | Stressable app: counts primes by slow trial division, so its CPU load and latency can be raised on demand. |

Both expose `GET /health` (is it alive) and `GET /metrics` (Prometheus format: `http_requests_total` and `http_request_duration_seconds`), plus a small web page at `/`.

## Why it exists
VigilOps learns what normal metrics look like and raises an alert when they turn abnormal. It needs apps to watch, and one of them must be breakable on purpose, so we know exactly when an incident starts and can measure detection delay.

## Layout (same in both apps)
`api/` routes, `schemas/` data shapes and validation, `services/` business rules, `repositories/` storage, `core/` metrics, `main.py` entry point and metrics middleware. Storage is in memory (lost on restart) until PostgreSQL arrives in Phase 2/3.

## How to run
Locally, from a service folder, with its own venv:
```
pip install -r requirements-dev.txt
python -m pytest -v
uvicorn app.main:app --port 8001      # 8002 for report-api
```
In Docker, from the repo root:
```
docker build -t vigilops/notes-api:dev services/notes-api
docker run -d -p 8001:8001 vigilops/notes-api:dev
curl http://127.0.0.1:8001/health
```
Use `127.0.0.1`, not `localhost`, on Windows: `localhost` may resolve to IPv6 and be cut by the WSL relay.

## Dockerfile choices
Two stages (install packages in a builder, copy only the result into the runtime image), `python:3.12-slim`, runs as non-root `appuser`, `.dockerignore` keeps `.venv` and tests out.

## Verification (real output, 2026-10-24)
- pytest: report-api 9 passed, notes-api 6 passed.
- Both containers started; `/health` returned `{"status":"ok"}`, `POST /reports {"limit":10000}` returned 1229 primes, `POST /notes` worked, `/metrics` showed `http_requests_total`. Container user: `uid=1000(appuser)`.

## Honest notes
- Claude wrote most of the code of both apps (and these tests/Dockerfiles) at the student's request. The spec says the student should write the first app's endpoints; the student should rewrite or extend part of notes-api in their own words as part of the explain-back.
- The small web pages are a custom frontend, which the spec lists as out of scope. The student chose to keep them; they are not needed by later phases.
- CPU/memory limits (rule 7) are set in Compose from Phase 3 on, not in the Dockerfiles.
