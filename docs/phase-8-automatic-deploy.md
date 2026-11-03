# Phase 8: automatic deploy to Kubernetes

## What was built
Every push to `main` now ends with the new version running in the kind cluster, without a human
typing `kubectl`. Passwords are stored encrypted in git (Sealed Secrets), so the whole platform
is deployed from the repository.

```
git push main
  -> security stage        gitleaks, semgrep, trivy-deps          (shared GitLab runners)
  -> pipelines stage       lint, 6 test jobs, build 6 images, push, trivy-images   (shared runners)
  -> deploy stage          deploy job                             (YOUR laptop runner, tag "laptop")
        kustomize edit set image ...:<short sha>   -> kubectl apply -k k8s/ -> kubectl rollout status
```

| Piece | What it is | Where |
|---|---|---|
| GitLab runner `vigilops-laptop` | worker program in a Docker container on the laptop, `docker` executor, jobs run on the `kind` Docker network | container `vigilops-runner`, registered to this project only (locked, tag `laptop`, does not run untagged jobs) |
| Robot account `gitlab-deployer` | ServiceAccount + Role + RoleBinding limited to the `vigilops` namespace | `k8s/bootstrap/ci-rbac.yaml` |
| `KUBECONFIG_B64` | the robot's kubeconfig (server `https://vigilops-control-plane:6443`, robot token) as one base64 line | GitLab CI variable, masked + protected. The only CI variable the deploy needs. |
| Sealed Secrets controller v0.41.2 | decrypts `SealedSecret` objects into real Secrets, inside the cluster | namespace `kube-system` |
| `k8s/secrets/*-sealed.yaml` | the 3 Secrets (`vigilops-secrets`, `gitlab-registry`, `grafana-admin`) encrypted with the cluster's public key, safe in git | repository |
| `deploy` job | see the flow above | `.gitlab-ci.yml` |

## Why it is built this way
- **A runner on the laptop.** GitLab's shared runners run in the cloud and cannot reach a kind
  cluster on a laptop. A runner on the laptop asks GitLab for jobs itself, so nothing has to connect in.
- **The cluster address changes inside a job.** `127.0.0.1` means "this machine". On the laptop it is the
  door Docker opened to the cluster. Inside a job container it points to the job itself. Containers on the
  same Docker network reach each other by name, so the CI kubeconfig uses `vigilops-control-plane:6443`.
- **A robot with small rights instead of the admin key.** If `KUBECONFIG_B64` leaked, it could only
  create/update Deployments, Services, ConfigMaps, volume claims and SealedSecrets in `vigilops`, and read pods.
  It cannot delete, cannot read or write plain Secrets, and sees nothing outside the namespace.
  A `Namespace` is cluster-wide, so `namespace.yaml` moved to `k8s/bootstrap/` (one-time admin step).
- **Sealed Secrets instead of CI variables.** A Kubernetes Secret is only base64, so it cannot go in git.
  `kubeseal` encrypts it with the controller's public key. Only the controller's private key (never
  leaves the cluster) can decrypt it. The pipeline needs no password, and a new cluster needs no
  typing of passwords. Encrypted files are bound to name + namespace.
- **All 6 images are built on every push to `main`.** CI used to build only the services whose folder
  changed, so a commit that touched only `k8s/` had no image for its tag. On `main` the services pipeline
  now always runs; on other branches it still runs only when relevant files change.
- **The tag is set by the pipeline.** `kustomize edit set image` writes the commit's short sha into the
  job's copy of `k8s/kustomization.yaml`, so nobody edits `newTag` by hand.

## How to run it (from nothing)
```
# 1) cluster and one-time admin setup
kind create cluster --config k8s/kind-config.yaml --name vigilops
kubectl apply -f k8s/bootstrap/                  # namespace + robot account

# 2) Sealed Secrets: restore the private key BEFORE the controller starts, so old sealed files still decrypt
kubectl apply -f <backup>/master-key.yaml
kubectl apply -f controller.yaml                 # release v0.41.2 of bitnami/sealed-secrets

# 3) CI access: build the robot's kubeconfig (token and CA come from the Secret gitlab-deployer-token),
#    base64 it, store it as the masked + protected CI variable KUBECONFIG_B64

# 4) runner (once): create a project runner in GitLab (tag laptop, no untagged jobs), then
docker run -d --name vigilops-runner --restart unless-stopped -v vigilops-runner-config:/etc/gitlab-runner -v /var/run/docker.sock:/var/run/docker.sock gitlab/gitlab-runner:alpine-v19.4.1
docker exec -it vigilops-runner gitlab-runner register --non-interactive --url https://gitlab.com --token <glrt-token> --executor docker --docker-image alpine:3.20 --docker-network-mode kind

# 5) push to main: the pipeline deploys everything
```
To add or change a Secret: make the Secret as YAML with `--dry-run=client -o yaml`, pipe it to
`kubeseal --format yaml`, save the result in `k8s/secrets/`, commit. A Secret that already exists in
the cluster must first get the annotation `sealedsecrets.bitnami.com/managed="true"`, otherwise the
controller refuses to take it over.

**Back up the controller's private key** outside the repository (it decrypts every sealed file):
`kubectl -n kube-system get secret -l sealedsecrets.bitnami.com/sealed-secrets-key=active -o yaml`.

## Live results
- Runner: registered, `gitlab-runner verify` valid, executor `docker`, network `kind`.
- Robot limits checked with `kubectl auth can-i`: patch deployments **yes**, delete deployments **no**,
  read pods in `default` **no**, patch sealedsecrets **yes**, get secrets **no**.
- A container on the `kind` network with the CI kubeconfig listed the pods; `get nodes` was refused (cluster-wide).
- All 3 Secrets taken over by the controller (`SealedSecret unsealed successfully`); the 8 keys of
  `vigilops-secrets` were still present; `kubectl apply -k k8s/ --dry-run=server` reported every object `unchanged`.
- Pipeline on commit `221fcd34`: security, tests and 6 builds green; the deploy job applied the manifests
  and the 6 services moved to image `221fcd34`. After the fix below, the deploy job passed and all
  10 pods were Ready.

## Lessons and bugs
- **First deploy failed with `ImagePullBackOff` and `401 Unauthorized`.** The registry Secret had been
  sealed with a password that was not the real deploy-token password (21 characters, a deploy-token
  password is about 25 and starts with `gldt-`). It went unnoticed because the old pods ran from images
  already on the node. Fix: a new deploy token, the Secret sealed again, the stuck pods deleted, the job retried.
- **The rolling update protected the apps.** While the new pods could not start, the old ones kept
  running: Kubernetes removes an old pod only after its replacement is Ready. The deploy job failed
  (`rollout status` timed out) instead of silently leaving a broken release.
- A SealedSecret does not retry after a refusal when only the target Secret changes: delete and re-apply
  the SealedSecret to make the controller try again.
- `kubectl diff` needs a `diff` program that Windows does not have: use `kubectl apply -k --dry-run=server`.
- PowerShell: two commands on one line are read as one (`curl ... tar -xzf` became curl options);
  .NET file calls use the folder PowerShell was started in, not the one set with `cd`.

## Limits (not hidden)
- **The deploy target is a laptop cluster.** The runner works only while Docker, the `vigilops-runner`
  container and the kind cluster run. Nothing is reachable from outside.
- The runner mounts the Docker socket, which gives its jobs control of Docker on the laptop. Acceptable
  for a personal machine and a locked, single-project runner; not for a shared server.
- **`newTag` values in git go stale.** The pipeline sets the tag only inside the job. The repository still
  shows the last tag a human wrote, so git alone does not say what is running. GitOps (Argo CD or Flux)
  would fix this and is out of scope.
- **Sealed Secrets depend on the private key.** If the key is lost with the cluster, every sealed file is
  unreadable and the Secrets must be re-created. Restoring the key in a fresh cluster was **not tested**.
- A password that was ever committed or pasted somewhere else is not protected by sealing it afterwards.
  Rotating a password means sealing the new value again.
- A secrets manager (Vault, AWS Secrets Manager with External Secrets) is the professional next step
  and was not used.
- The deploy job only waits for rollouts; there is no smoke test that calls `/health` through the cluster
  (a job container is not on the pod network). Anomaly-detection and alerting still have no probes.
- Prometheus has no persistent volume, and the first pull of 6 new images is slow on this laptop.
