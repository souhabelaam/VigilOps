# Phase 6: CI/CD with GitLab

## What was built
Every push to GitLab now runs an automatic pipeline: scan, lint, test, build, scan the images.
A pipeline is red when something is wrong, and the later stages never start.

```
.gitlab-ci.yml (parent)
├── stage security   : gitleaks, semgrep, trivy-deps          (every push)
└── stage pipelines  : services-pipeline ──> ci/services.yml  (child)
                       ml-pipeline       ──> ci/ml.yml        (child)
```

| File | Content |
|---|---|
| `.gitlab-ci.yml` | parent: the three security jobs, then triggers the two child pipelines (`strategy: depend`, so the parent is red if a child is red) |
| `ci/services.yml` | stages `lint`, `test`, `build`, `scan` for the 6 services |
| `ci/ml.yml` | `lint-ml`, `test-ml` (numpy + pytest, quick), `test-parity` (CPU torch) |
| `ruff.toml` | ruff settings: python 3.12, line length 120, `.venv` excluded |

### Jobs
| Job | Stage | What it checks | Fails when |
|---|---|---|---|
| gitleaks (v8.21.2) | security | secrets (keys, tokens) in the git history | a secret is found |
| semgrep (1.99.0, `p/python`) | security | insecure Python patterns | any finding (`--error`) |
| trivy-deps (0.57.1) | security | known CVEs in `requirements.txt` files | a CRITICAL with a fix exists |
| ruff (0.14.0) | lint | style and obvious bugs | any finding |
| test per service (6 jobs) | test | pytest of each service | a test fails |
| build per service (6 jobs) | build | builds the image with docker-in-docker (`docker:27.3.1-dind`) and pushes `registry.gitlab.com/souhabenelaam/vigilops/<service>:<short sha>` | build or push fails |
| trivy-images | scan | CVEs in the 6 built images | a CRITICAL with a fix exists |
| lint-ml / test-ml | ml child | ruff, 16 numpy tests (`test_evaluate` 7, `test_windows` 9) | failure |
| test-parity | ml child | numpy forward pass == torch (4 tests) | difference above tolerance |

## Why
- **Scans before the build**: a leaked secret or a vulnerable dependency should stop the pipeline
  before we spend minutes building and pushing images.
- **Parent / child pipelines**: the parent stays small. Each child pipeline has its own stages and
  only runs when its folders change (`rules: changes`, which also lists `.gitlab-ci.yml` itself).
- **Parity test**: the production service scores with numpy, the training uses torch. If someone changes
  one side, CI fails. It was proven to fail when the numpy ReLU was removed.
- **Image tag = short commit sha**: every image can be traced to one commit. No `latest`.
- **Trivy policy**: fail only on CRITICAL (as in the spec), show HIGH without blocking, ignore findings
  with no fix yet (`--ignore-unfixed`).

## How to run
Push to GitLab (`git push gitlab main`): the pipeline starts by itself. Look at *Build > Pipelines*.
Locally, the same checks:
```
ruff check .
cd services/<service> ; .venv\Scripts\python -m pytest
```

## Proof that it blocks
Done on a throwaway branch (deleted afterwards), verified locally:
1. **Fake secret**: random fake AWS keys in `services/notes-api/settings_demo.py` -> `gitleaks` red.
2. **Vulnerable dependency**: `pyyaml==5.3` in `services/alerting/requirements.txt` -> `trivy-deps` red
   (CVE-2020-14343 and CVE-2020-1747, both CRITICAL, fixed in 5.4).

On GitLab (branch `proof/blocked-commit`), both pipelines failed in 26 s at the `security` stage
and the next stage was skipped (#3008179221 fake secret, #3008180829 vulnerable library).
The pipeline of `main` (#3008155927, commit 86838b1) passed in 2 min 21 s.
In both demo cases the lint, test and build stages never started.
A fake secret is used on a branch because a real one, even removed later, stays in git history forever.

## Lessons from building it
- `services` is a **reserved** job name in GitLab CI (it declares service containers). The job is `services-pipeline`.
- With `rules: changes`, **no pipeline existed** when only `.gitlab-ci.yml` changed. Fix: list the file itself.
- CI caught a file that was **never committed** (`templates.py` of alerting): it worked on my machine only.
- Git Bash rewrites paths given to `docker -v`; use `MSYS_NO_PATHCONV=1`.
- `notes-api/requirements.txt` is UTF-16. pip and Trivy both read it, so it was left as is.
- Six ruff findings in `ml/` were fixed (unused imports, lambdas assigned to names).

## Honest limits
- **Known finding**: HIGH `libpcre2-8-0` CVE-2026-103111 in the Debian 13.7 base image. A fixed package
  exists but the base image is not updated yet. HIGH does not block by our policy: accepted for now.
- Shared runners have limited free minutes, and Trivy downloads its database on every run.
- There is **no deploy stage** yet (Phase 7 and later).
- `tools/` is scanned but has no lint job. Services have no GitLab cache for pip.
- The **retrain-and-compare gate** (retrain, compare with the current model, block if worse) belongs to
  Phase 8: it needs the data versioned. The data is 1.5 MB and git-ignored; commit it or use DVC, to decide then.
