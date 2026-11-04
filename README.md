# VigilOps

A small AIOps platform. Two target apps (`notes-api`, `report-api`) are watched by a pipeline that collects
their metrics, learns what "healthy" looks like with an autoencoder, raises an alert when something looks
wrong, and clears it when things go back to normal. Everything is built, scanned and deployed by a CI/CD
pipeline, runs on Kubernetes, and the cloud part is created with Terraform and configured with Ansible.

Full specification: [docs/PROJECT.md](docs/PROJECT.md). One note per phase is in [docs/](docs/).

## How the data flows

```
notes-api / report-api
        |  (metrics endpoints)
     collector --> [raw-metrics queue] --> ingestion --> PostgreSQL (rates)
                                               |
                                        [rates queue]
                                               v
                                      anomaly-detection --> [anomalies queue] --> alerting --> e-mail
Prometheus --> Grafana  (dashboard of the target apps)
```

RabbitMQ carries the queues. The detection service uses a numpy copy of the trained model (no torch in the
container); `ml/check_numpy.py` proves both give the same scores.

## Repository map

| Folder | What is in it | Note |
|---|---|---|
| `services/` | the 2 target apps + collector, ingestion, anomaly-detection, alerting (one Dockerfile each) | phases 1, 3, 5 |
| `ml/` | data preparation, autoencoder, baseline, evaluation, retrain gate, DVC-tracked data | phases 4, 10 |
| `tools/` | load generator, fault injector, metrics recorder | phase 2 |
| `docker-compose.yml`, `db/` | the whole stack on one machine | phase 3 |
| `k8s/` | Kubernetes manifests, kustomize, monitoring | phase 7 |
| `.gitlab-ci.yml`, `ci/` | pipeline: lint, test, scans, build, gate, deploy | phases 6, 8, 10, 11 |
| `infra/` | Terraform (EC2), Ansible (k3s, firewall), AWS overlay for kustomize | phase 9 |

## Requirements

Windows 11 with WSL2 (or Linux), Docker Desktop, about 3 GB of RAM given to WSL (`.wslconfig`),
Python 3.12, `kubectl`, `kind`. For the cloud deployment: Terraform, Ansible (in WSL), an AWS account.

## Rebuild it, step by step

### 1. Run it with Docker Compose

```
cp .env.example .env          # then edit the values; .env is git-ignored
docker compose up -d --build
docker compose ps             # all containers should be up
```

Start traffic so there is something to measure:

```
python tools/load-generator/load_generator.py --rate 2 --duration 600
```

Inject a fault and watch the alert (the apps need `FAULTS_ENABLED=true`, already set in Compose). Wait about
2.5 minutes after traffic starts so the detection window fills:

```
curl -X POST http://127.0.0.1:8001/faults/cpu     # notes-api; alert arrives in about 10 s
curl -X DELETE http://127.0.0.1:8001/faults/cpu   # remove it; [RESOLVED] follows after ~3 min
```

Set `NOTIFIER=email` and the SMTP values in `.env` to get real e-mails; with `console` alerts are printed
in the `alerting` log.

### 2. Train and evaluate the model (optional, models are committed)

```
cd ml
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Linux: .venv/bin/pip
dvc pull                       # needs the DVC remote, see "Limits" below
.venv/Scripts/python prepare_data.py
.venv/Scripts/python autoencoder.py
.venv/Scripts/python export_numpy.py
```

Results and the baseline comparison are in [docs/phase-4-ml.md](docs/phase-4-ml.md). The retrain gate
(`ml/gate.py`) refuses a retrained model that is worse than the current one: [docs/phase-10-mlops-gate.md](docs/phase-10-mlops-gate.md).

### 3. Run it on Kubernetes (kind)

```
kind create cluster --config k8s/kind-config.yaml          # cluster "vigilops"
kubectl apply -f k8s/bootstrap/namespace.yaml
```

Create the secrets by hand (the sealed files in `k8s/secrets/` only open on the cluster that sealed them,
so a new cluster needs its own):

```
kubectl -n vigilops create secret generic vigilops-secrets --from-env-file=.env
kubectl -n vigilops create secret docker-registry gitlab-registry \
   --docker-server=registry.gitlab.com --docker-username=<deploy-token-user> --docker-password=<token>
kubectl -n vigilops create secret generic grafana-admin --from-literal=admin-password=<choose one>
```

The image names in `k8s/kustomization.yaml` point to the GitLab registry of this project. To use your own
registry, change them and push your own images from your own pipeline. Then:

```
kubectl apply -k infra/aws-demo/        # without the sealed secrets; use k8s/ if you sealed your own
kubectl -n vigilops get pods            # wait for 1/1 Running
```

Grafana: http://127.0.0.1:3000 (user `admin`). notes-api: http://127.0.0.1:8001, report-api: http://127.0.0.1:8002.
Details and lessons: [docs/phase-7-kubernetes.md](docs/phase-7-kubernetes.md).

### 4. CI/CD

Push to GitLab. The pipeline runs Gitleaks, Semgrep and Trivy (a fake secret or a CRITICAL vulnerable
library stops it), lints, tests, builds and pushes the images, scans them, runs the retrain gate when `ml/`
changes, and deploys to the cluster through a runner on the laptop. How to register that runner and the one
CI variable it needs (`KUBECONFIG_B64`) is in [docs/phase-8-automatic-deploy.md](docs/phase-8-automatic-deploy.md).
Checkov checks Terraform (blocking) and the Kubernetes manifests (report only): [docs/phase-11-checkov-and-probes.md](docs/phase-11-checkov-and-probes.md).

### 5. Cloud deployment (AWS Learner Lab)

This part is temporary by design. The server was created, verified and destroyed in one session, because
the Learner Lab credentials and budget are temporary. Nothing runs in AWS now; the evidence (plan, Ansible
run, pods, screenshots) is in [docs/phase-9-infrastructure.md](docs/phase-9-infrastructure.md). To repeat it:

```
cd infra/terraform && terraform init && terraform plan     # read the plan first
terraform apply                                             # creates 7 resources, costs money while it runs
# then the Ansible playbook from WSL: see docs/phase-9-infrastructure.md
terraform destroy                                           # do not forget
```

## Limits (honest list)

- The retrain gate and deploy job need the laptop on, Docker running, and the DVC remote folder
  (`C:\Users\PC\dev\dvc-remote`) mounted in the runner. The data remote is a local folder, not a second copy.
- Detection quality was measured on small data (a few incidents per app). Numbers and caveats: phase 4 and 5 notes.
- Kubernetes manifests have no `securityContext` or NetworkPolicy yet, so `checkov-kubernetes` only reports.
- Updating images in a cluster is done by the CI deploy job; there is no GitOps controller.
- node-exporter host metrics are not yet scraped by Prometheus.
