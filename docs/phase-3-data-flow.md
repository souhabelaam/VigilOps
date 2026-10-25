# Phase 3: data flow

## What was built
Metrics now flow end to end in Docker Compose:

```
notes-api ─┐
           ├─ GET /metrics ─> collector ─> RabbitMQ (raw-metrics) ─> ingestion ─> PostgreSQL (metric_rates)
report-api ┘
```

| Service | Job | Limits |
|---|---|---|
| collector | every 5 s reads each app's `/metrics`, publishes the raw counters as JSON. The only service that talks to the apps | 128 MB, 0.25 cpu |
| rabbitmq | durable queue `raw-metrics` between collector and ingestion | 384 MB, 0.5 cpu |
| ingestion | consumes messages, turns counters into rates, stores them | 128 MB, 0.25 cpu |
| postgres | table `metric_rates` (created by `db/init.sql`), data kept in the volume `pgdata` | 256 MB, 0.5 cpu |

## Why
- The queue separates the services: if ingestion or the database is slow or down, the
  collector keeps working and messages wait (no data lost).
- The collector sends raw counters; only ingestion computes rates, so the rule lives in
  one place (`services/ingestion/app/services/rates.py`) and matches `ml/prepare_data.py`.

## Rules worth remembering
- An unreachable app is published as `up: false` (this is how a crash starts to show).
- A message is acknowledged only after the database insert worked (at-least-once delivery).
  `UNIQUE (app, ts)` + `ON CONFLICT DO NOTHING` make a redelivered message harmless.
- Rates: gap above 6 s is never subtracted; a counter that goes down is a reset
  (row stored with `reset = true` and empty rates); no requests means no latency.
- Difference from the offline script: live, the reset check runs before the gap rule, so a
  crash that leaves a gap is still flagged. Training tables flag fewer crashes (2 of 5 in
  faulty-3). Keep this in mind in Phase 4.
- Credentials are in the git-ignored `.env` (`.env.example` shows the names).

## How to run
```
docker compose up -d --build        # needs a filled .env
docker compose logs -f ingestion
docker exec vigilops-postgres-1 psql -U vigilops -d vigilops -c "select * from metric_rates order by ts desc limit 10"
```
RabbitMQ web page: http://127.0.0.1:15672 (user and password from `.env`).

## Verified
- collector: 4 tests; ingestion: 7 tests (including a crash that leaves a gap).
- End to end: 40 requests to notes-api showed as 7.8 req/s and 4.2% cpu; a crash fault on
  report-api produced a row with `reset = true`, and Compose restarted the container.

## Not done yet
Health endpoints for the collector and ingestion (needed for Kubernetes probes in Phase 7).
