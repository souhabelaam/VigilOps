# Phase 9: infrastructure as code (Terraform, Checkov, Ansible) and a demo on AWS

## What was built
A server in the cloud that exists only for one session, created and configured from files, with
VigilOps running on it, then destroyed.

```
Terraform   creates the server, its firewall and its SSH key       infra/terraform/
Checkov     scans the Terraform files for security mistakes
Ansible     turns the empty Ubuntu server into a k3s cluster       infra/ansible/playbook.yml
kubectl     applies the platform on it (overlay, see below)        infra/aws-demo/
Terraform   destroys everything
```

| Piece | What it does |
|---|---|
| `infra/terraform/` | 7 AWS resources: security group (firewall), 3 ingress rules (SSH 22, Kubernetes API 6443, app ports 30002-30003), 1 egress rule, the key pair (public key only) and one `t3.medium` Ubuntu 24.04 server (20 GB encrypted disk, metadata v2 only). Ingress is limited to **my IP only** (`my_ip_cidr`, no default on purpose). |
| Checkov | 31 checks passed, 0 failed, 2 skipped. The skips are written in `main.tf` with their reason: detailed monitoring costs extra for a 30-minute server (`CKV_AWS_126`), and the Learner Lab cannot create IAM roles and the server never calls AWS (`CKV2_AWS_41`). |
| `infra/ansible/playbook.yml` | installs packages (curl, ufw, node-exporter), installs k3s with the public IP in its certificate, waits for the node to be Ready, sets up the host firewall (ufw), downloads the kubeconfig and points it at the public IP. |
| `infra/aws-demo/kustomization.yaml` | an overlay: reuses `k8s/` and removes only the 3 `SealedSecret` files. |

## Why it is built this way
- **Throwaway server.** The Learner Lab has a $50 budget and credentials that change every session.
  The server is created and destroyed in the same session (about $0.05 per hour while it lives).
  Everything is rebuilt from files, so nothing is lost by destroying it.
- **Two firewalls.** The AWS security group blocks traffic before it reaches the server. `ufw` on the
  server is a second wall. Both only let my IP in.
- **Playbook order.** SSH is allowed in `ufw` *before* the firewall is enabled. Enabling it first would
  deny Ansible's own SSH connection and lock us out. The pod and service ranges (`10.42.0.0/16`,
  `10.43.0.0/16`, private networks inside k3s, not my laptop) are allowed too, otherwise `ufw`
  blocks the traffic between pods and breaks the cluster.
- **Idempotent tasks.** Each task describes a state. The k3s install has `creates:` so it is skipped
  when k3s already exists.
- **Overlay instead of editing `k8s/`.** The sealed files were encrypted for the kind cluster's key.
  The AWS cluster does not have that key, so it could not read them. Installing the controller
  with the real master key on a cloud server would put the key that protects every secret in git
  on a machine outside my control. So the 3 Secrets were created by hand on the new cluster
  (`vigilops-secrets` from `.env`, `gitlab-registry` from the deploy token, `grafana-admin`), and
  they disappear with the server. `kubectl apply -k k8s/` is unchanged for GitLab and kind.
- **No credentials in files.** Terraform reads `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and
  `AWS_SESSION_TOKEN` from the terminal. The kubeconfig Ansible downloads is an admin key, so
  `infra/ansible/out/` is git-ignored and the file was deleted after the demo.

## How to run it
Prerequisites: a Learner Lab session, an SSH key pair (`ssh-keygen`), Terraform, Ansible in WSL
(`pipx install --include-deps ansible`, Ansible does not run natively on Windows).

```
# 1) credentials in the terminal (from "AWS Details" in the Learner Lab), never in a file
$env:AWS_ACCESS_KEY_ID="..." ; $env:AWS_SECRET_ACCESS_KEY="..." ; $env:AWS_SESSION_TOKEN="..."

# 2) the server
cd infra/terraform
terraform init
terraform plan  -var "my_ip_cidr=<my ip>/32" -var "public_key_path=C:/Users/PC/.ssh/vigilops-demo.pub"
terraform apply -var "my_ip_cidr=<my ip>/32" -var "public_key_path=C:/Users/PC/.ssh/vigilops-demo.pub"

# 3) configure it (in WSL; the key must be copied to the Linux home and chmod 600)
cd /mnt/c/Users/PC/dev/VigilOps/infra/ansible
export ANSIBLE_CONFIG=$PWD/ansible.cfg
ansible-playbook -i <public ip>, -u ubuntu --private-key ~/.ssh/vigilops-demo playbook.yml

# 4) deploy (a separate PowerShell window: it now talks to AWS, not to kind)
$env:KUBECONFIG="...\infra\ansible\out\k3s.yaml"
kubectl apply -f k8s/bootstrap/namespace.yaml
kubectl -n vigilops create secret generic vigilops-secrets --from-env-file=.env
kubectl -n vigilops create secret docker-registry gitlab-registry --docker-server=registry.gitlab.com --docker-username=... --docker-password=...
kubectl -n vigilops create secret generic grafana-admin --from-literal=admin-password=...
kubectl apply -k infra/aws-demo

# 5) ALWAYS at the end
terraform destroy -var "my_ip_cidr=<my ip>/32" -var "public_key_path=..."
```

## Result of the demo run (2026-11-03)
| Step | Result |
|---|---|
| `terraform plan` | 7 to add, 0 to change, 0 to destroy; the 3 ingress rules showed my `/32` |
| `terraform apply` | 7 added; server created in 15 s |
| Ansible, first run | `ok=10 changed=7 failed=0`; the firewall was enabled without losing the SSH connection |
| Ansible, second run | `ok=10 changed=2 failed=0` (see limits) |
| `kubectl get nodes` from the laptop | 1 node `Ready`, k3s v1.31.14 |
| `kubectl apply -k infra/aws-demo` | 10 pods `1/1 Running`, 0 restarts, about 1 minute (images pulled much faster than on the laptop) |
| Pipeline inside the cluster | `raw-metrics`, `rates`, `anomalies`: 1 consumer, 0 messages each |
| Data | 474 rows in `metric_rates` after about 20 minutes; 95 s later 512 rows: +38 = 19 sampling rounds x 2 apps, no gap |
| From the laptop | `http://<ip>:30002/health` answered `{"status":"ok"}`; the notes page loaded in the browser |
| `terraform destroy` | 7 destroyed |

Screenshots: `docs/images/phase-9-pods.png`, `phase-9-notes-api.png`, `phase-9-data-flow.png`,
`phase-9-aws-instance.png` (account banner blurred).

Checkov and the playbook syntax were checked before any resource was created (`ansible-playbook
--syntax-check`).

## Problems met and how they were solved
- **`No valid credential sources found`**: the AWS variables were not set in the window running
  Terraform (variables belong to one terminal window). Set them again in that window.
- **Ansible ignored `ansible.cfg`**: the project is on `/mnt/c`, which Linux sees as world-writable,
  and Ansible then ignores the config on purpose. Fixed with `export ANSIBLE_CONFIG=$PWD/ansible.cfg`.
- **SSH refused the key**: same reason, a key on `/mnt/c` looks readable by everyone. Copy it to the
  Linux home and `chmod 600`.
- **PowerShell 5.1 and quotes**: a long `wsl -e bash -lc '...'` was split into two lines, and the inner
  double quotes of a `psql -c "..."` command were removed. Fixed by typing commands inside `wsl`
  and by piping the SQL through stdin.
- **Overlay loop**: the first overlay lived inside `k8s/` and included `k8s/`, which kustomize reports as a
  cycle. Moved to `infra/aws-demo/`.
- **Sealed Secrets cannot move between clusters**: see "Overlay instead of editing `k8s/`".

## Honest limits
- **The AWS deploy is manual**, by design: the server does not live between sessions. The automatic
  GitLab deploy (Phase 8) targets the kind cluster on the laptop.
- **`ansible.cfg` turns host key checking off.** This is acceptable only because the server is
  brand new and destroyed within the hour. It must not be copied to a permanent server.
- **The second Ansible run reports `changed=2`, not 0.** The two kubeconfig tasks undo each other:
  one downloads the original file (with `127.0.0.1`), the next rewrites it. The server itself is not
  modified twice, but the tasks are not strictly idempotent.
- **Checkov did not run in the pipeline when this phase was written** (added later, see
  `phase-11-checkov-and-probes.md`), and it does not scan the Ansible playbook. Terraform and Ansible
  are not run by GitLab.
- **Terraform state is local** (`terraform.tfstate`, git-ignored). Losing it while a server exists would
  leave a server Terraform no longer knows about. Fine for one session; a real project would use a
  remote state with locking.
- **node-exporter runs on the server but nothing scrapes it yet.** The Prometheus in the cluster only
  scrapes the two apps. It is installed and the port is closed to the outside.
- **The apps are only reachable from my IP.** If my IP changes (another network), the rules must be
  recreated with a new `my_ip_cidr`.
- **Secrets are typed by hand on the new cluster.** Not automated on purpose (see above).
- **The data on the AWS cluster was not tested with a fault.** Only that the pipeline is connected and
  stores data; detection quality was measured in Phases 4, 5 and 7.
