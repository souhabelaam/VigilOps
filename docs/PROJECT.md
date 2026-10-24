<!-- Text extracted from VigilOps-doc.pdf (spec dated 2026-10-09). Layout of tables is flattened; the PDF is the formatted original. -->

VigilOps: A Microservices AIOps Platform for
Intelligent Anomaly Detection on Kubernetes
Oct 9, 2026 · ​@souha
For Claude Code: read this first
This document is the full specification of the VigilOps project, written for a student who is
learning DevOps by building it. If you are Claude Code, read all of it before writing any
code, and follow section 14 (the working agreement) first: the student's learning matters
more than speed.
Where to find what:
Scope, exclusions and constraints (including 8 GB of RAM): section 3
Architecture and services: sections 4 and 5
Machine learning specification: section 6
DevOps and MLOps practices and tools: sections 7 and 8
Order of work and deliverable of each phase: section 9
Folder layout: section 10
Definition of success: section 13
How you work with the student: section 14
If a request from the student conflicts with this document, say so and ask which one wins.
The student keeps this document in the repository as docs/PROJECT.md .
1. Project overview
This project, named VigilOps (a vigil is a watch kept through the night), builds a system
that watches running applications, learns what normal behavior looks like with a model
you train yourself, and raises an alert when something looks abnormal. It is built as small
independent services (microservices) and delivered with a complete DevOps chain.
The story in plain words. Two small websites run on your laptop. Every few seconds a
program (the collector) asks each one for its CPU use, memory use, response time and
error count. Those numbers go into a mailbox (the queue), and another program saves
them in a database. After a few hours of normal running you have a record of what normal
AIOps Platform: Microservices, Machine Learning and DevOps
Page 1 of 18

looks like, and you train your model on it. Later you break one website on purpose, for
example by making it use all the CPU. The numbers change, your model flags them as
strange, and an alert program notifies you. You fix the website and the alerts stop.
In one line: watch, learn what normal is, shout when it is not.
The practice behind it is called AIOps: using machine learning to detect incidents in IT
systems earlier than fixed thresholds can. The project also adds MLOps, which means
applying the same automation (versioning, pipelines, quality gates) to the model as to the
code.
2. Objectives
Main objective: design, build and deploy a microservices platform that collects metrics
from applications, detects anomalies with a model trained from scratch (no external AI
API), and alerts automatically, with the whole system delivered by an automated and
secured DevOps pipeline.
Specific objectives:
1. Decompose the platform into small services that communicate through REST and a
message queue.
2. Containerize every service, one Dockerfile per service, and run the whole system with
Docker Compose.
3. Generate a labeled dataset by running target applications under load and injecting
faults.
4. Train and compare a simple baseline detector and a deep learning autoencoder, and
evaluate them honestly.
5. Serve the trained model inside an anomaly detection service.
6. Automate build, test, security scans and deployment with a CI/CD pipeline.
7. Deploy all services on Kubernetes with health probes and resource limits.
8. Observe the platform with Prometheus and Grafana and trigger alerts.
9. Version models and data, and add an automated gate that blocks a retrained model if it
performs worse than the current one.
10. Describe the infrastructure as code with Terraform and configure the cloud server
with Ansible (k3s, Node Exporter).
11. Document the architecture and every technical choice.
AIOps Platform: Microservices, Machine Learning and DevOps
Page 2 of 18

Learning objective: after the project you can explain, without notes, why each tool is
there, what would break without it, and how the model decides that something is
abnormal.
3. Scope and constraints
The project is large, so the scope is cut on purpose: four core services, Grafana as the only
dashboard, and everything runs locally first.
In scope
Two small target applications that you can break on purpose.
A load generator and a fault injection script.
Four core services: collector, ingestion, anomaly detection, alerting.
A baseline detector and an autoencoder, trained and evaluated by you.
Docker, Docker Compose, GitLab CI with security scans, Kubernetes, Prometheus,
Grafana, MLflow, Terraform, Ansible and one cloud deployment on AWS Learner Lab.
Out of scope
A custom web front end (Grafana is the dashboard).
Spring Cloud components (Eureka, Config Server). They add a second language and
little learning for this project.
Kafka. RabbitMQ is much lighter on RAM.
Large language models or any external AI API.
Service mesh, Helm charts and GitOps, unless time remains at the end.
Constraints
8 GB of RAM. Components cannot all run at full size at once. Set low memory limits on
every pod, avoid the full kube-prometheus-stack , and train the model outside the
cluster.
No cloud budget. Kubernetes runs locally ( kind or k3s ).
AWS Academy Learner Lab (final phase). The budget is $50, the session lasts 4 hours
by default, credentials are temporary and change every session, and IAM is restricted.
Use one EC2 instance sized for k3s (about 4 to 8 GB of RAM; check which instance
types your lab allows), avoid EKS, NAT gateways and load balancers, and run
terraform destroy after each session.
AIOps Platform: Microservices, Machine Learning and DevOps
Page 3 of 18

Ansible is part of the cloud phase. It configures the EC2 instance after Terraform
creates it: it installs k3s and Node Exporter. If the Learner Lab is unavailable, the same
playbook runs against a local virtual machine, so the Ansible work never depends on
the cloud.
4. Architecture
Follow the arrows: the collector reads the apps, the queue carries the metrics to
ingestion, ingestion stores them and passes them to anomaly detection, which scores
them with your trained model and calls alerting. The highlighted box is where your own
machine learning work runs. Below the cluster, the pipeline tests, scans and builds every
service, then deploys it.
platform architecture · 6 services, queue, model, delivery chain
AIOps Platform: Microservices, Machine Learning and DevOps
Page 4 of 18

5. The services
Each service has one job and its own Dockerfile, so it can be built, scaled and redeployed
alone. Services talk through the queue where possible, so one failure does not stop the
others.
Service
Role
Receives
Produces
Target apps (2)
Small web apps being
watched; you break
them on purpose
HTTP requests
from the load
generator
Metrics endpoint
( /metrics ) and health
endpoint ( /health )
Load generator
Sends steady traffic so
the apps behave like
real ones
Nothing
HTTP traffic
Fault injector
Makes the apps
misbehave (CPU burn,
memory leak, slow
responses, crash) and
logs when
Your command
Faults, plus a label file of
when each fault
happened
Collector
Reads the metrics of
each target app every
few seconds
Metrics endpoints
Messages in the queue
Queue
(RabbitMQ)
Holds messages
between services so
none is lost if one is
slow
Messages from
the collector
Messages to ingestion
Ingestion
Cleans metrics and
stores them
Queue messages
Rows in PostgreSQL,
and messages for
anomaly detection
Anomaly
detection
Loads your trained
model and scores each
new metric window
Metric windows
An anomaly score and a
flag
Alerting
Sends a notification
when an anomaly is
flagged, and avoids
repeats
Anomaly events
Email or Telegram
message
AIOps Platform: Microservices, Machine Learning and DevOps
Page 5 of 18

The collector is the only service that talks to the target apps. Anomaly detection is the
only service that knows the model. Keeping those boundaries clean is what makes the
system microservices and not one program split into folders.
6. Machine learning part
The model is trained by you, on data you generate, and it must be compared honestly with
a simple baseline. The comparison matters more than a high score.
Step 1: Build the dataset
Run the target apps under the load generator for several hours with no faults. This is
the normal data.
Run separate sessions where the fault injector creates incidents: CPU burn, memory
leak, slow responses, crashing pods. Log the start and end time of each fault. This gives
labeled anomaly data.
Features per time step: CPU use, memory use, request latency, request rate, error rate.
Keep a public benchmark such as NAB (Numenta Anomaly Benchmark) as an optional
extra test set.
Step 2: Prepare the data
Cut the time series into fixed-size windows (for example the last N readings).
Normalize with statistics computed on the training data only.
Split by time, not at random: train on normal data, validate on later normal data, test on
sessions with faults. A random split leaks the future into training and gives false
results.
Step 3: Baseline
A fixed threshold or a z-score per metric, and Isolation Forest from scikit-learn.
The baseline is the bar the deep model must beat.
Step 4: Autoencoder (the model you build)
A dense autoencoder in PyTorch first, then an LSTM autoencoder if time allows.
Service
Role
Receives
Produces
Grafana +
Prometheus
Show metrics, anomaly
scores and service
health
Metrics from all
services
Dashboards and alerts
AIOps Platform: Microservices, Machine Learning and DevOps
Page 6 of 18

It is trained only on normal windows to rebuild its own input. On normal data the
rebuild error is small. On abnormal data the error is large, and that error is the anomaly
score.
The alert threshold is chosen on validation data, for example a high percentile of the
error on normal windows.
Step 5: Evaluation
Report all five for the baseline and for the autoencoder on the same test sessions. If the
autoencoder does not beat the baseline, explain why. That is still a valid result and a good
defense.
Step 6: Serving
Export the trained model and its normalization values as files.
The anomaly service loads them at startup and scores each incoming window.
Baking the model into the service image is the simplest option: a new model means a
new image version.
7. DevOps and MLOps practices
Each practice below answers one question: how is this code or model built, checked,
shipped and watched without manual steps.
Containers
One Dockerfile per service: multi-stage build, non-root user, small base image.
The anomaly service image is the largest because of PyTorch; use the CPU-only build to
keep it small.
Measure
What it tells you
Precision
Of the alerts raised, how many were real incidents
Recall
Of the real incidents, how many were caught
F1 score
One balance between precision and recall
Detection delay
How many seconds after a fault starts the alert
fires
False alerts per hour
How noisy the system is on normal data
AIOps Platform: Microservices, Machine Learning and DevOps
Page 7 of 18

One docker-compose.yml runs the whole system locally. Build and debug the data
flow here before touching Kubernetes.
CI/CD with security (GitLab CI)
Stages: lint, unit tests, build image, security scans, push to the registry, deploy.
Scans: Gitleaks (secrets), Semgrep (source code), Trivy (dependencies and images),
Checkov (Terraform and Kubernetes files).
The pipeline fails on critical findings, so a vulnerable commit never reaches the cluster.
Kubernetes ( kind or k3s )
A Deployment and a Service per service, a ConfigMap for settings, a Secret for
passwords.
Liveness and readiness probes on every service, and CPU and memory limits on every
pod.
PostgreSQL and RabbitMQ run with one replica each and a persistent volume, so data
survives restarts. This is the fiddliest part; do it after the stateless services work.
Optional: a Horizontal Pod Autoscaler on the anomaly service.
Observability
Every service exposes /metrics . Prometheus scrapes them, Grafana shows them.
Dashboards: service health, queue depth, anomaly score over time, alerts fired.
Prometheus and Grafana are installed in their plain form, not the full kube-
prometheus-stack , to save RAM.
MLOps
MLflow records each training run: parameters, metrics, the model file.
DVC (or a clear folder convention) versions the datasets.
A CI stage retrains the model, evaluates it on the fixed test sessions, and compares it
with the current model. If it is worse, the pipeline stops and the old model stays.
Infrastructure as code
Terraform describes the Kubernetes namespace and resources locally, then the EC2
instance on AWS in the cloud phase.
Checkov scans every Terraform file.
Configuration management (cloud phase)
AIOps Platform: Microservices, Machine Learning and DevOps
Page 8 of 18

Terraform creates the EC2 instance; an Ansible playbook then installs k3s, sets up the
firewall and installs Node Exporter, which exposes the server's CPU, memory and disk
metrics to Prometheus. The pipeline then deploys the services on it.
This is the standard split: Terraform creates things, Ansible configures what is inside
them.
8. Technologies used
Python is used for every service so that the services and the model share one language
and one set of libraries.
Tool
Category
Role in the project
Why this one
Python +
FastAPI
Services
All microservices and the
target apps
One language for
services and ML; light
and fast to write
RabbitMQ
Messaging
Queue between collector,
ingestion and anomaly
detection
Much lighter than
Kafka on 8 GB RAM
PostgreSQL
Database
Stores metrics and
anomaly events
Standard, reliable,
runs in a small
container
scikit-learn
ML
Baseline detectors (z-
score, Isolation Forest)
Simple reference to
beat
PyTorch (CPU)
ML
Autoencoder and LSTM
autoencoder
Full control over the
model; no external API
MLflow
MLOps
Tracks training runs and
model versions
Free, runs locally with
file storage
DVC
MLOps
Versions datasets
Keeps data out of Git
Docker + Docker
Compose
Containers
Packages each service;
runs the whole system
locally
Industry standard
GitLab CI/CD
CI/CD
Build, test, scan, deploy
pipeline
Free tier, built-in
registry
AIOps Platform: Microservices, Machine Learning and DevOps
Page 9 of 18

9. Work plan
The phases are ordered so that each one reuses the previous one. Phases 1 to 6 are the
core; phases 7 to 9 add depth. Phase 9 includes Ansible, so protect time for it and shorten
phase 8 first if time runs short.
Tool
Category
Role in the project
Why this one
Gitleaks,
Semgrep, Trivy,
Checkov
Security
Secrets, code,
dependency/image and
infrastructure scans
Each covers a
different layer
Kubernetes
( kind or k3s )
Orchestration
Runs and manages the
services
Real Kubernetes on a
laptop, free
Prometheus +
Grafana
Observability
Metrics collection and
dashboards
De facto standard pair
Terraform
Infrastructure as
code
Creates cluster resources
and the EC2 instance
Standard IaC tool
Ansible
Configuration
management
Installs k3s and Node
Exporter on the EC2
instance
Complements
Terraform in the cloud
phase
AWS Academy
Learner Lab
Cloud
One small EC2 instance
for the final cloud
deployment
Available to you; $50
budget
Node Exporter
Observability
Exposes the EC2 server's
CPU, memory and disk
metrics to Prometheus;
installed by Ansible
Standard host-metrics
agent for Prometheus
Phase
Tasks
Deliverable
1. Foundations
Set up Linux or WSL2, Git,
Docker, Python, GitLab project;
create the two target apps with
/health and /metrics
Target apps run in containers
AIOps Platform: Microservices, Machine Learning and DevOps
Page 10 of 18

Phase
Tasks
Deliverable
2. Data
Write the load generator and
the fault injector; run normal
and faulty sessions; save
metrics and fault labels
Labeled dataset
3. Data flow
Build collector, RabbitMQ,
ingestion and PostgreSQL; write
one Dockerfile per service and a
docker-compose.yml
Metrics flow end to end in
Compose
4. Machine learning
Prepare windows; train the
baseline, then the autoencoder;
evaluate both; log runs in
MLflow
Trained model and evaluation
report
5. Detection and
alerts
Build the anomaly service that
loads the model, and the
alerting service; connect them
to the queue
Anomaly flagged and alert sent
in Compose
6. CI/CD
Write the GitLab CI pipeline:
lint, tests, build, Gitleaks,
Semgrep, Trivy, push to registry
Green pipeline that blocks a
vulnerable commit
7. Kubernetes
Install kind or k3s ; write
manifests with probes, limits,
ConfigMap and Secret; deploy
stateless services first, then
RabbitMQ and PostgreSQL with
volumes; add Prometheus and
Grafana
Full system running on
Kubernetes with a dashboard
8. Terraform and
MLOps gate
Describe resources with
Terraform and scan with
Checkov; add the retrain-and-
compare stage to the pipeline
Pipeline that refuses a worse
model
AIOps Platform: Microservices, Machine Learning and DevOps
Page 11 of 18

Write documentation notes at the end of each phase, not in the last week. Develop in
Docker Compose first and move to Kubernetes only when the data flow works there.
10. Repository structure
One repository holds everything. Each service has its own folder and Dockerfile, so it can
be built and deployed alone.
vigilops/
├── services/
│   ├── target-app-1/        # Dockerfile, app code
│   ├── target-app-2/
│   ├── collector/
│   ├── ingestion/
│   ├── anomaly-detection/   # loads the trained model
│   └── alerting/
├── tools/
│   ├── load-generator/
│   └── fault-injector/
├── ml/
│   ├── data/                # versioned with DVC, not in Git
│   ├── notebooks/           # exploration and evaluation
│   ├── train.py             # training script, logs to MLflow
│   └── evaluate.py          # compares baseline and autoencoder
├── docker-compose.yml
├── k8s/                     # Deployments, Services, ConfigMaps, Secrets
Phase
Tasks
Deliverable
9. Cloud and Ansible
Terraform creates one EC2
instance on Learner Lab; an
Ansible playbook installs k3s
and Node Exporter on it; the
pipeline deploys; Prometheus
scrapes the server; then
terraform destroy
Cloud deployment demo
10. Documentation
and demo
Architecture diagram, setup
guide, evaluation results,
screenshots, demo script, final
report
Final report and live demo
AIOps Platform: Microservices, Machine Learning and DevOps
Page 12 of 18

├── terraform/
├── ansible/                 # playbooks: k3s, Node Exporter
├── .gitlab-ci.yml
└── docs/                    # architecture, setup guide, report
11. Deliverables
The final package contains the following.
12. Risks and mitigations
The biggest risk is scope: this is three projects in one, so cutting early is cheaper than
cutting late.
Git repository with all services, one Dockerfile per service, and a docker-compose.yml
Labeled dataset, with the load generator and fault injector that produced it
Training and evaluation code, with baseline and autoencoder results (precision, recall,
F1, detection delay, false alerts per hour)
MLflow record of the training runs and the chosen model version
Working GitLab CI pipeline with tests, Gitleaks, Semgrep, Trivy and the model gate
Kubernetes manifests with probes, resource limits, ConfigMaps and Secrets
Terraform code scanned by Checkov
Prometheus and Grafana dashboards, and a working alert
Ansible playbook and a cloud deployment on one EC2 instance, with its Node Exporter
metrics in Grafana
Documentation: architecture diagram, setup guide, explanation of each tool choice
Demo scenario with screenshots, and the final report
Risk
Why it happens
Mitigation
Scope too large
Microservices, ML and DevOps
in one project
Keep four core services; drop
the HPA and the LSTM first
The ML looks bolted on
A model added without a
reason or a comparison
Always compare against the
baseline on the same test
sessions and explain the
result
AIOps Platform: Microservices, Machine Learning and DevOps
Page 13 of 18

Risk
Why it happens
Mitigation
Misleading evaluation
Random split leaks the future;
threshold tuned on test data
Split by time; choose the
threshold on validation data
only
Not enough data
Faults are rare and you have no
real incident data
Generate faults yourself and
run long sessions; add NAB as
an extra test set
8 GB of RAM
Cluster, queue, database,
Prometheus and Grafana
together
Set low memory limits;
develop in Compose first; use
plain Prometheus and
Grafana; train outside the
cluster
Large PyTorch image
The full PyTorch build is several
GB
Use the CPU-only build and a
multi-stage Dockerfile
Stateful services on
Kubernetes
RabbitMQ and PostgreSQL
need volumes and careful
restarts
Deploy them last, one replica
each
Learner Lab limits
$50 budget, 4-hour sessions,
expiring credentials, restricted
IAM
Cloud is the last phase; one
EC2 instance with about 4 to
8 GB of RAM and a disk of
about 20 GB, so that k3s and
the PyTorch image fit; delete
the instance as soon as the
demo is done; terraform
destroy after each session;
never commit credentials
Copy-paste without
understanding
Generated code runs but
teaches nothing
Write or explain each stage
yourself before moving on
Documentation left to
the end
Notes written from memory
are thin
Document at the end of every
phase
Ansible work blocked by
the cloud
Learner Lab sessions expire
and the server's IP and
credentials change
Write and test the playbook
first against a local virtual
machine; run it on EC2 last
AIOps Platform: Microservices, Machine Learning and DevOps
Page 14 of 18

13. Success criteria and demo
The project succeeds if a fault you inject is detected and alerted automatically, and if the
whole system can be rebuilt and redeployed from the repository.
Success criteria
Metrics flow from the target apps to the database through the queue with no manual
step.
The autoencoder is evaluated against the baseline with the five measures, and the
result is explained.
An injected fault produces an alert, and the alert stops when the fault is removed.
A commit with a fake secret or a vulnerable dependency is blocked by the pipeline.
A retrained model that is worse than the current one is rejected by the pipeline.
Every service has a health probe and a resource limit on Kubernetes.
Someone else can rebuild the platform by following the documentation.
Demo scenario
1. Start the platform and show Grafana with normal metrics.
2. Inject a CPU fault into one target app and show the anomaly score rising.
3. Show the alert arriving, then remove the fault and show it clearing.
4. Kill a pod and show Kubernetes restarting it.
5. Push a commit with a fake secret and show the pipeline blocked.
6. Show the evaluation table: baseline against autoencoder.
7. Show the same deployment running on the EC2 instance, created by Terraform and
configured by Ansible, with its host metrics in Grafana.
14. Working agreement for Claude Code
This section is addressed to Claude Code. The student's goal is to learn DevOps,
microservices and applied machine learning by building VigilOps, not only to finish it.
Following these rules matters more than speed.
Context about the student
Final-year engineering student. Has trained machine learning models before. New to
Docker, CI/CD, Kubernetes, Terraform and Ansible: these are learned during this
project.
AIOps Platform: Microservices, Machine Learning and DevOps
Page 15 of 18

Works on a laptop with 8 GB of RAM. Confirm the operating system (Linux or WSL2
expected) at the start.
Cloud access is an AWS Academy Learner Lab: $50 budget, temporary credentials that
change every session.
Writes in English. Explain in simple words and define each new term the first time it
appears.
Rules: always do
1. Read this whole document before writing code. It is the source of truth for scope, tools
and order.
2. Work on one phase at a time (section 9), stop at that phase's deliverable, and wait for
the student to confirm before starting the next one.
3. Before each phase, say in a few sentences what you will build, why it exists in the
architecture, and which concept is new. After it, ask the student to explain it back.
4. Keep each service in its own folder with its own Dockerfile. Make the data flow work in
Docker Compose before writing Kubernetes manifests.
5. Run what you write (tests, docker compose up , kubectl get pods ) and report the
real output. Never say something works without having run it.
6. Make small commits with clear messages after each working step.
7. Set CPU and memory limits on every container, so the whole system fits in 8 GB.
8. Write a short note in docs/ at the end of each phase: what was built, why, and how to
run it.
Rules: never do
Never add tools outside the scope in section 3: no Kafka, no Spring Boot or Spring
Cloud, no service mesh, no Helm, and no external AI or LLM API for the detection
model.
Never commit credentials, tokens or keys, and never print the Learner Lab credentials.
Use CI variables, Kubernetes Secrets and a git-ignored .env file.
Never run terraform apply , terraform destroy or any command that creates or
deletes cloud resources without the student's explicit confirmation at that moment.
Explain what it will create and the cost risk first.
Never evaluate the model with a random split or tune the alert threshold on test data.
Split by time and always compare with the baseline.
Never hide a bad result. If the autoencoder does not beat the baseline, report it and
help explain why.
AIOps Platform: Microservices, Machine Learning and DevOps
Page 16 of 18

Never silently rewrite code the student wrote. Propose the change and show the
difference.
Who writes what
The student writes the core piece of each phase, with you guiding and reviewing. You may
generate the repetitive parts, and you explain them.
Routine for every phase
1. Plan: you explain what will be built, why, and which concepts are new.
2. Build: the student writes the core piece; you generate the rest and explain it.
Phase
The student writes
You may generate
1. Foundations
Endpoints of the first target
app
Second target app, boilerplate
2. Data
What each fault does in the
fault injector
Load generator, code that saves
the metrics
3. Data flow
Collector and ingestion logic,
the first Dockerfile
Other Dockerfiles, docker-
compose.yml , RabbitMQ and
PostgreSQL setup
4. Machine learning
Windowing, the autoencoder,
the evaluation
Plots, MLflow logging boilerplate
5. Detection and
alerts
Scoring logic of the anomaly
service
Email or Telegram integration,
API boilerplate
6. CI/CD
First stages of .gitlab-
ci.yml : lint, test, build
Scan stages, after the student
understands each one
7. Kubernetes
The first Deployment and
Service, by hand
Other manifests, probes, limits,
Prometheus and Grafana config
8. Terraform and
model gate
The model comparison logic of
the gate
Terraform boilerplate, Checkov
config
9. Cloud and Ansible
The first Ansible tasks
Rest of the playbook, Terraform
for the EC2 instance
10. Documentation
and demo
Explanations in the student's
own words
Diagrams, formatting, demo
script structure
AIOps Platform: Microservices, Machine Learning and DevOps
Page 17 of 18

3. Verify: run it and show the real output.
4. Break it: the student predicts what will happen, then you change something on
purpose and run it again.
5. Explain back: the student writes two or three sentences in their own words; you
correct them.
6. Commit and note: commit the work and add the note to docs/ .
The phase is done only when its deliverable in section 9 exists and works.
How the student starts
Save this document as docs/PROJECT.md in the repository. Copy the context and the two
rule lists above into a file named CLAUDE.md at the repository root, which Claude Code
reads at the start of each session. Then send this first message:
Read docs/PROJECT.md completely, especially section 14 (working agreement).
Then confirm my operating system and tell me what you understood about the 
project in five sentences.
We start with phase 1 (Foundations). Before writing any code, explain what we 
will build,
why it exists in the architecture, and which concepts are new for me.
Then tell me which parts I should write myself and which parts you will 
generate.
Do not move to phase 2 until I confirm that phase 1 is done.
AIOps Platform: Microservices, Machine Learning and DevOps
Page 18 of 18
