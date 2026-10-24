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

## Dataset collected (session 4)
All files are in `ml/data/<session>/` (git-ignored). Each session ran the apps in Docker
with 2 requests/s of generated traffic and a 5 s scrape.

| Session | Length | Content |
|---|---|---|
| `normal-1`, `normal-2` | 20 min each | healthy, clean |
| `normal-3` | 20 min | healthy, one 52 s gap at 2026-10-24T18:03:13Z |
| `normal-partial` | about 36 min | healthy, stopped early by memory pressure |
| `faulty-1` | 20 min | 7 incidents, 6 on notes-api and 1 on report-api (cpu, memory, latency) |
| `faulty-2` | 20 min | 6 incidents, all on report-api (cpu, memory, latency) |
| `faulty-3` | 20 min | 6 incidents: 5 crashes and 1 memory fault |
| `faulty-3-INVALID-generator-died` | | do not use (generator crashed, see below) |
| `rehearsal`, `normal-rehearsal` | | test runs, not part of the dataset |

Totals: about 96 min of normal data and 19 labeled incidents (cpu 4, memory 8, latency 3,
crash 5). The set is small and uneven, so results must be reported with that caveat.

### What the data shows
- Each fault has its own fingerprint: cpu fault takes CPU from about 1% to 50% (the
  container limit is half a core) with memory flat; memory fault grows memory by 30 to
  90 MB with CPU flat; latency fault raises latency to the chosen delay with CPU and memory
  flat.
- report-api latency is naturally noisy (17 to 41 ms) because report sizes are random.
- A crash is over in a few seconds, shorter than the scrape interval, so it often leaves
  0 or 1 `up=0` row. The reliable signal is a counter reset (CPU and request totals
  drop). Label windows for crashes are longer than the real downtime.

### Problems found and fixed
- report-api kept every report forever, which made normal data drift; now capped at 100.
- The load generator crashed when an app crashed; now it counts the error and continues.
- The 1-hour run was killed for low memory; sessions are now 20 minutes (see
  `docs/running-sessions.md`).

### Not done yet (next)
Data preparation: turn the raw counters into per-5-second rates, drop or split at gaps,
mark counter resets, join with the labels, and split by time (never randomly).
