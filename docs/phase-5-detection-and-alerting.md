# Phase 5: detection and alerting

## What was built
The trained models now run live, and a problem becomes an email:

```
ingestion ─> RabbitMQ (rates) ─> anomaly-detection ─> RabbitMQ (anomalies) ─> alerting ─> console + email
```

| Service | Job | Limits |
|---|---|---|
| ingestion (changed) | after storing a rate it also publishes it to the queue `rates` | 128 MB, 0.25 cpu |
| anomaly-detection | keeps a sliding window per app, rebuilds the model input exactly as `ml/windows.py`, scores it with a numpy forward pass (no torch in the container), applies the crash rule and the debounce, publishes an event | 160 MB, 0.25 cpu |
| alerting | one notification per incident, a `[RESOLVED]` message when it is over, sends it to the console and by email | 64 MB, 0.1 cpu |

Event on the queue `anomalies`: `{ts, app, kind (model | crash), score, threshold}`.
The system only **notifies**. It repairs nothing (Docker restarts a crashed container, that is not VigilOps).

## Why
- **numpy instead of torch** in the container: the image stays small and fits the 8 GB laptop.
  `ml/export_numpy.py` writes the weights to `services/anomaly-detection/models/{app}.json`;
  `ml/check_numpy.py` proves numpy gives the same scores as torch on faulty-7
  (167/216 windows flagged, max relative difference 3e-7, same windows).
- **Crash rule**: the autoencoder never flags crash windows (after a restart the metrics look healthy),
  so a counter reset (or `up = false`) is an alarm by itself.
- **Debounce `decide(scores, k, threshold)`**: an app is alarmed only after k alarms in a row.
  k = 2 for notes-api, 1 for report-api (chosen on faulty-1 and 6 by a rule fixed beforehand, see `ml/debounce.py`).
- **Cool-down** (alerting): the detector sends an event every 5 s while an app looks broken. Without
  a cool-down, one 2-minute fault would send 24 mails. An incident ends after 60 s without events.
  Cool-downs are per `(app, kind)`, so a stuck model alarm cannot hide a real crash.
- **Email** (`services/alerting/app/services/notifier.py`): `ConsoleNotifier`, `EmailNotifier`
  (SMTP, STARTTLS, port 587) and `MultiNotifier`. Any mail error is logged and swallowed, so alerting
  never stops because of a mail server. The password is never logged.
- **Templates** (`templates.py`): subject plus a short body: app, time in UTC, severity
  (score vs threshold), meaning, and where to look (`docker compose logs <app>`, the `/metrics` link).

## How to run
```
docker compose up -d --build
docker compose logs -f alerting
```
Email is optional. In the git-ignored `.env` at the repo root (`.env.example` shows the names):
```
NOTIFIER=email
SMTP_USER=you@gmail.com
SMTP_PASSWORD=<a Gmail app password, never the real one>
MAIL_TO=where-alerts-go@example.com
```
Gmail needs 2-step verification and an app password (https://myaccount.google.com/apppasswords).
With `NOTIFIER=console` (default), or if the credentials are empty, alerts only go to the log.

Try it: `docker compose restart notes-api` gives a crash alert after a few seconds.
Faults: `POST http://127.0.0.1:8001/faults/cpu`, then `DELETE` after 40 s (the load generator must run
first and the windows need about 2.5 min to fill).

## Live results (Docker Compose, this laptop)
| Test | Result |
|---|---|
| memory leak, notes-api | detected after about 12 s |
| CPU fault | detected after 5 s, score about 900 vs threshold 2.78, ONE alert per incident |
| crash (restart notes-api) | alert 4 to 10 s after the restart; one mail arrived (09:09:33 alert, 09:09:36 mail) |
| end of a fault | `[RESOLVED]` about 3 min after the fault ends |
| held-out faulty-7 (offline, same models) | notes-api F1 0.982, 10.6 false alarms/h; report-api F1 0.977, 7.1 false alarms/h |

Tests: ingestion 8, anomaly-detection 9, alerting 21.

## Bugs found live and fixed
1. A cool-down of 120 s hid a second fault that started 91 s after the first. Now 60 s.
2. A stuck false alarm of the model hid a real crash. Cool-downs are now per `(app, kind)`.
3. The model read the absolute memory level, but container memory differs between runs
   with no fault (23 to 53 MB, training mean 50.4, std 4.4), so it false-alarmed for 6 minutes.
   Fix: the model now gets memory **growth** in the window. On `ml/robustness.py`, a probe with a
   level 20 MB lower went from 100% to 0.5% false alarms on notes-api.

## Honest limits
- **The alarm lingers.** The window is 2 minutes, so the detector keeps alarming about 2 minutes
  after a fault ends. That is why `[RESOLVED]` comes late.
- **report-api false alarms when traffic returns after a long idle**: 25 of 49 windows on normal-7
  and 15 of 230 on normal-5. notes-api: 0 of 280 windows on unseen clean sessions.
- **WSL artifact**: with the 2 GB WSL cap, containers swap. A fresh container goes from 53 to 26 MB
  during idle, and the first request after a long idle takes about 325 ms. Not reproducible on demand,
  and specific to this laptop.
- **Not usable as healthy data**: normal-6 (the laptop slept). Training on the idle sessions was tried
  and rejected by a rule fixed beforehand (report-api F1 0.977 to 0.933, false alarms/h 7.1 to 14.1).
- **Small samples**: faulty-7 has 3 and 4 incidents per app; the numbers above are not a guarantee.
- **The email cannot name the faulty metric**: the autoencoder gives one overall score, not which of
  CPU, memory or latency is unusual.
- Collector and ingestion still have no health endpoints (needed for Kubernetes probes in Phase 7).

## Next
Phase 6: CI/CD with GitLab.
