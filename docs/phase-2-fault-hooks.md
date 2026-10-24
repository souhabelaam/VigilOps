# Phase 2 (part 1): fault hooks in the target apps

## Authorship
This code was written by Claude Code at the student's request, then explained
to the student file by file (the student did not write it). It is infrastructure
for producing labeled data, not the core ML work.

## What was built
Both apps (`notes-api`, `report-api`) can be broken on purpose through
`/faults` endpoints, so VigilOps can later learn what "broken" looks like.

| Endpoint | Effect | Metric fingerprint |
|---|---|---|
| `POST/DELETE /faults/cpu` | a thread burns CPU nonstop | CPU up, memory flat, latency slightly up |
| `POST/DELETE /faults/memory` | a thread keeps allocating 1 MB / 0.5 s (cap 200 MB) | memory climbs, CPU flat |
| `POST/DELETE /faults/latency?delay_ms=N` | middleware sleeps N ms on business requests | latency up, CPU and memory flat |
| `POST /faults/crash` | process exits 0.2 s after the response | target goes down |
| `GET /faults` | shows which faults are active | |

## Why it is built this way
- Files: `app/core/faults.py` (the machinery), `app/api/faults.py` (the endpoints),
  latency delay in the middleware in `app/main.py`, tests in `tests/test_faults.py`.
- Safety lock: endpoints answer 404 unless the environment variable
  `FAULTS_ENABLED=true`.
- `/faults`, `/metrics` and `/health` are exempt from the delay so a fault can
  always be turned off and scraping stays fast.
- Threads are stopped with a `threading.Event` flag (Python cannot kill a thread).
- Crash uses `os._exit(1)` from a timer so the HTTP response is sent first.
- There is deliberately NO "fault active" metric: it would leak the label to the
  model. The label will live in a separate file written by the fault injector.

## How to run
```
FAULTS_ENABLED=true uvicorn app.main:app --port 8002
curl -X POST http://127.0.0.1:8002/faults/cpu
curl -X DELETE http://127.0.0.1:8002/faults/cpu
```
Tests: `pytest` inside each service folder.

## Tools built after the hooks
Written by Claude Code at the student's request, explained afterward.
- `tools/load-generator/` sends steady fake traffic (the "normal" activity).
- `tools/fault-injector/` presses the fault buttons on a schedule and writes a label CSV
  (fault, target, start_utc, end_utc, detail). Labels are the answer sheet used to grade
  the detector; the model itself trains on healthy data only.
- `tools/metrics-recorder/` saves each app's `/metrics` to a CSV (raw running totals;
  rates are computed later by subtracting consecutive rows).
- `docker-compose.yml` starts both apps with CPU/memory limits and `FAULTS_ENABLED=true`.
- `report-api` keeps only the last 100 reports, so normal data does not drift.
- How to run sessions: `docs/running-sessions.md`.

Rehearsal (2 min, 3 incidents): memory fault raised report-api memory from 52 to about
102 MB and it returned to 53 MB when switched off, matching the label file.
