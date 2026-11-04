# Acceptance check (2026-11-04)

A full pass over the success criteria of `docs/PROJECT.md` section 13, run on the Kubernetes cluster (kind) after a cold boot of the laptop. All times are UTC. Numbers below were measured in this session; nothing was tuned to make them pass.

## Starting state

- Docker Desktop, the kind cluster `vigilops` and the CI runner were started after a reboot (node up 16 minutes).
- 10 pods Ready, all services on the image built from commit `62ea80ec`. RabbitMQ queues `raw-metrics`, `rates`, `anomalies`: 1 consumer each, 0 messages waiting.
- One load generator at 2 requests per second (25 minutes, 2771 requests, 0 errors).

## Results

| # | Check | Result |
|---|---|---|
| 1 | Normal metrics in Grafana | The dashboard "VigilOps target apps" showed CPU at 1 to 5 % of a core, flat memory (about 38 to 44 MiB) and steady traffic for both apps. |
| 2 | CPU fault on notes-api shows a rising score | Fault injected 10:47:57. First score 873.7 against threshold 2.78 at 10:48:03 (6 s). Scores kept rising to about 955. |
| 3a | Alert arrives | `[ALERT] notes-api` at 10:48:03, e-mail sent at 10:48:04 and received in Gmail. One alert for the incident. |
| 3b | Alert clears when the fault is removed | Fault removed 10:48:37. `[RESOLVED] notes-api` at 10:51:33, 2 min 56 s later. This is the 2-minute detection window plus the 60 s cool-down. |
| 4 | Kill a pod, Kubernetes restarts it | notes-api pod deleted at 10:56:58. New pod 1/1 Ready after 9 s, `/health` 200. Rows in Postgres 15403 before, 15420 about 45 s later, so data kept arriving. The crash rule raised `[ALERT] notes-api crashed and restarted` at 10:57:08 (10 s after the kill). |
| 5 | A fake secret is blocked by the pipeline | A random AWS-style key pair in `services/notes-api/settings_check.py` on branch `proof/fake-secret` (commit `b715f9a5`). Pipeline #3026733039 failed after 40 s at the `gitleaks` job of the security stage. `semgrep` and `trivy-deps` passed. The later stages were skipped, so nothing was built or deployed. The branch was deleted afterwards, locally and on GitLab. The key was random and never valid. |
| 6 | Baseline against autoencoder | [evaluation-summary.md](evaluation-summary.md), numbers from [phase-4-ml.md](phase-4-ml.md). The autoencoder has the higher F1 on both apps on the final test (0.963 and 0.865 against 0.396 and 0.522) and on the held-out session (0.902 and 0.977 against 0.364 and 0.419). |
| 7 | The same deployment on a cloud server | Not repeated. The server was a temporary part of the project and was destroyed. Evidence (plan, Ansible run, 10 pods Ready, screenshots) is in [phase-9-infrastructure.md](phase-9-infrastructure.md). |

## Success criteria from the specification

| Criterion | Status |
|---|---|
| Metrics flow app, queue, database with no manual step | Met (phase 3, seen again today: queues drained, rows growing) |
| Autoencoder against baseline, five measures, explained | Met (phase 4, evaluation summary) |
| Injected fault gives an alert, alert stops when the fault is removed | Met (checks 2, 3a, 3b) |
| Fake secret or vulnerable dependency blocked | Met (check 5 today, vulnerable library in phase 6) |
| Worse retrained model rejected | Met (phase 10, gate job red with `GATE: REJECTED`) |
| Every service has a health probe and a resource limit on Kubernetes | Met: all 10 workloads have `limits` and liveness and readiness probes in `k8s/` |
| Someone else can rebuild it from the documentation | README and phase notes exist. Not yet tested by another person on a clean machine. |

## Other observations (not faults)

- **Noise after a cold boot.** In the first 13 minutes after the reboot, about 5 false alert episodes appeared with no fault injected: 4 on notes-api (quiet from 10:28) and 1 on report-api. The report-api alert from 10:16:43 stayed open until 10:39:53 because its score hovered just above the threshold (0.7 to 1.7 against 0.66). A second borderline report-api alert opened at 10:47:03 (score 0.6735 against 0.6601) and closed at 10:48:05. This matches the known limits written in phase 5: the models were trained on Docker Compose with more headroom, and report-api false-alarms when traffic returns after an idle period. The model and thresholds were not changed.
- **One alert per incident.** Cool-downs are per app and kind, so an open report-api alert did not hide the notes-api fault.
- **Reconnect.** At 10:47:03 the detector's RabbitMQ connection was reset and the service reconnected within a second. No pod restarted and the queues kept 1 consumer and 0 waiting messages.

## Limits of this check

- One run on one laptop. Detection quality on a freshly booted kind cluster is noisier than in the Compose recordings the model was trained on.
- The pod-kill check compared two row counts; it did not look at the timeline for gaps (that was done in phase 7).
- The faults are injected by our own tool.
- The gitleaks job log was not saved in this note.
