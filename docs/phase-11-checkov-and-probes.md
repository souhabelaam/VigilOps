# Phase 11: health probes for every service, and Checkov in the pipeline

## What was built
1. **Health doors for the last two workers.** `anomaly-detection` and `alerting` now answer
   `GET /health` (liveness: "is the loop still going round?") and `GET /ready` (readiness: "can I work?")
   on port 8080, from a background thread, like `collector` and `ingestion`. Every service now has a probe,
   which was a success criterion of the project.
2. **Checkov in GitLab CI**, two jobs in the `security` stage, run on every push.
3. **A fix for the Trivy jobs** (see "Lessons").

## Health doors
- Each service has its own copy of `app/core/health.py` (no shared code between services).
- The queue consumer calls `should_run()` at least once a second, even when the queue is empty. That
  function now also calls `health.beat()`. If a handler hangs, the beats stop; after 15 s of silence
  `/health` answers 503 and Kubernetes restarts the container.
- Readiness: anomaly-detection is ready once the models are loaded and the output queue is connected;
  alerting is ready once the notifier is built (it then connects to RabbitMQ and retries by itself).
- Tests: 3 new tests per service (13 and 26 tests pass), ruff clean.

**Seen live** (`kubectl describe pod`): both pods run image `96094a32`, `Liveness: http-get :8080/health`,
`Readiness: http-get :8080/ready`, `Ready: True`, `Restart Count: 0`. One `Readiness probe failed ...
connection refused` event right after start is normal: Python was still starting and the door was not open yet.

**Not proven live:** that a hung worker is really restarted. Only the unit tests cover the "15 s of silence
means dead" logic.

## Checkov in CI
| Job | Scans | Policy | Result |
|---|---|---|---|
| `checkov-terraform` | `infra/terraform` | any failed check fails the job | 31 passed, 0 failed, 2 skipped (`CKV_AWS_126`, `CKV2_AWS_41`, reasons written in `main.tf`) |
| `checkov-kubernetes` | `k8s/` | **report only** (`--soft-fail`) | 778 passed, **137 failed** |

Checkov is pinned to 3.4.3, the version used on the laptop, installed with pip in a `python:3.12-slim` job.
Locally checked: Terraform exits 0, Kubernetes with `--soft-fail` exits 0, without it exits 1.

### The 137 Kubernetes findings (known limit, not hidden)
14 kinds of check, each failing on all 10 workloads (secrets-as-files on 7):
- no `securityContext`: privilege escalation allowed, not forced non-root, no high UID, no read-only
  root filesystem, capabilities not dropped (`NET_RAW`), no seccomp profile (CKV_K8S_20/22/23/28/29/30/31/37/40)
- images pinned by tag, not by digest (CKV_K8S_43); pull policy not `Always` (CKV_K8S_15)
- service account token mounted although the pods never call the Kubernetes API (CKV_K8S_38)
- no NetworkPolicy (CKV2_K8S_6); secrets given as environment variables, not files (CKV_K8S_35)

Why report-only: making the job blocking today would fail every push. The fix is to harden the manifests
(`securityContext` on the 8 workers, `automountServiceAccountToken: false`, a NetworkPolicy) and test that
everything still starts; PostgreSQL and RabbitMQ write to disk, so they need care. The Dockerfiles already
run as the non-root `appuser`, so part of this is cheap. When the manifests are hardened, remove
`--soft-fail` and skip the remaining checks one by one with a written reason, as done for Terraform.

## Lessons
- **Trivy failed twice with `BLOB_UNKNOWN`** while downloading its vulnerability database from the default
  mirror (`mirror.gcr.io`). Retrying did not help; nothing was scanned. Fix: `TRIVY_DB_REPOSITORY:
  ghcr.io/aquasecurity/trivy-db:2` in `trivy-deps` and `trivy-images` (same database, other registry). The
  pipeline then passed. A security scan that cannot start is not a pass: the job failed, which is the safe behaviour.
- A pipeline that deploys on every push also deployed the new probes by itself: no manual step.
- The first pull of the two new images took 5 minutes on this laptop (known slow image pulls).
