# Phase 10: data versioning (DVC) and the retrain-and-compare gate

## What was built
A model can be retrained automatically, and the pipeline refuses it if it is worse than the
current one.

```
push that touches ml/ or the DVC pointer
  -> lint-ml, test-ml, test-parity            (shared GitLab runners, as before)
  -> gate                                      (YOUR laptop runner, tag "laptop")
        dvc pull                               fetch the exact data version git points to
        python ml/gate.py                      retrain both apps (5 seeds each) into a temp folder,
                                               grade NEW and CURRENT models on the same exam,
                                               apply the rule, exit 1 if the new one is worse
```

| Piece | What it is | Where |
|---|---|---|
| DVC 3.67.1 | versions the datasets: git stores a tiny fingerprint file, the real files live in a remote | `.dvc/`, `ml/data.dvc` |
| DVC remote `laptop` | a folder on the laptop outside the repo (`../dvc-remote`, i.e. `C:\Users\PC\dev\dvc-remote`) | `.dvc/config` |
| `ml/data.dvc` | the fingerprint of `ml/data/` (88 files, 1.36 MB). Each git commit points to one exact version of the data. | git |
| `ml/gate_rule.py` | the rule that decides "worse" (pure Python, 10 unit tests) | `ml/tests/test_gate_rule.py` |
| `ml/gate.py` | retrain, grade both models, decide, write `gate-report.json`, set the exit code | `ml/` |
| `gate` job | runs the above in CI on the laptop runner; keeps `gate-report.json` and, when accepted, the candidate models as artifacts | `ci/ml.yml` |

Small change to existing code: `autoencoder.run()` got an `out` folder (a candidate never overwrites
`ml/models/`) and the exported checkpoint now records `train_sessions`.

## The exam and the rule
- **Current model** = the frozen `ml/models/<app>.pt`. **Candidate** = the same recipe
  (`autoencoder.SETTINGS`, 5 seeds) trained again on the DVC data.
- **Exam** = `faulty-2, 3, 4, 5, 7`: sessions that never took part in training or in the threshold
  (`faulty-1` and `faulty-6` were used for tuning, so they are not in it). It never changes, so scores are
  comparable between runs. Each model is graded with its own scaler and its own threshold, which come
  from its own training data.
- **Rule** (fixed before any gate result was seen, see `ml/gate_rule.py`): reject if, for **either**
  app, F1 falls by more than **0.05**, or false alerts per hour rise above **current x 1.5 + 2**.
  The 0.05 comes from `ml/seed_spread.py`: the same recipe moves F1 by +-0.009 (notes-api) and
  +-0.029 (report-api) between seed sets, so a smaller margin would reject good models by bad luck.
  One bad app rejects the whole candidate because both models ship together.

## Why it is built this way
- **DVC, not git, for the data.** Data and code change independently. With the fingerprint in git, a
  change in a score can be traced to code or to data, and CI can fetch the exact version.
- **A laptop folder as the remote.** S3 would need the Learner Lab credentials, which are temporary
  and change every session, so CI would break next time. A folder costs nothing. It forces the gate
  job onto the laptop runner (the one the Phase 8 deploy already depends on).
- **The rule is a separate pure file.** It can be tested in seconds without data or torch, and it is
  the one thing nobody should tune to make a model pass.
- **Candidates are never promoted automatically.** The pipeline only decides "not worse" and keeps the
  files. Copying them into `ml/models/` and exporting for the detection service is a human step.

## Proof runs (local, 2026-11-03)
Same exam each time. Current models: notes-api F1 0.92 (4.7 false/h), report-api F1 0.868 (7.5 false/h).

| Run | Candidate | notes-api F1 / false per h | report-api F1 / false per h | Gate |
|---|---|---|---|---|
| 1 | same recipe, same data | 0.92 / 4.7 | 0.868 / 7.5 | **accepted**: identical to every digit shown, so the retrain is reproducible (33 s) |
| 2 | + the two idle sessions `normal-5`, `normal-7` | 0.924 / 4.7 | 0.858 / 8.8 | **accepted**: inside the noise margins |
| 3 | trained for 3 epochs instead of 150 | 0.92 / 4.7 | 0.855 / 10.0 | **accepted** (see below) |
| 4 | data contaminated: + `faulty-1`, `faulty-6` (faults learned as "normal") | **0.803** / 3.6 (recall 0.878 -> 0.683) | 0.957 / 0.0 | **REJECTED**, exit code 1: notes-api F1 fell 0.92 -> 0.803 |

Two results that look odd and what they mean:
- **Run 2 is accepted, although Phase 5 refused the same sessions.** Phase 5 asked "is it *better* on the
  idle tests?" and the answer was no. The gate asks "is it *worse* on the fixed exam?" and the answer is
  also no. They are different questions, and the rule was not changed to get a different answer.
- **Run 3 (3 epochs) is accepted.** I expected a rejection and did not get one. The thresholds show the
  model really is different (6.2 vs 2.78 and 2.9 vs 0.66), but each model's threshold is calibrated on
  its own healthy data, and the injected faults score hundreds of times above it, so detection is
  almost unchanged on this exam. The gate measures behaviour on the exam, not how hard the model was trained.
  I did not tighten the rule after seeing this; I built a failure that is realistic (contaminated
  data) instead.
- In run 4 report-api actually improved while notes-api got worse; the candidate is still rejected, by design.

## How to run it
```
# locally (from ml/, venv active, data present or restored with `dvc pull`)
python gate.py                                         # same recipe: should be accepted
python gate.py --extra-train normal-5,normal-7         # a different candidate
python gate.py --extra-train faulty-1,faulty-6         # contaminated data: rejected, exit code 1

# restore the data on a new machine
dvc pull                                               # needs the remote folder

# after changing the data
dvc add ml/data ; dvc push ; git add ml/data.dvc ; git commit ...
```

One-time runner setup (so the job can read the remote folder): the folder is mounted read-only into every job
container of the laptop runner, by adding it to `volumes` in the runner's `config.toml`:
`volumes = ["/cache", "/run/desktop/mnt/host/c/Users/PC/dev/dvc-remote:/dvc-remote:ro"]`.

## Honest limits
- **The CI job was not run on GitLab when this note was written**: only `gate.py` was run locally.
  The result of the first real run is added below once it exists.
- **The remote is one folder on one laptop.** If the folder or the laptop is lost, the data is lost
  (only the fingerprint is in git). The raw sessions were never in git before either. A copy to a
  second place is advisable.
- **If the laptop is off, a pipeline that touches `ml/` waits** for the laptop runner, because the
  gate job needs it. The gate cannot run on GitLab's shared runners.
- **The exam is small**: five faulty sessions, a few dozen incidents. `faulty-2..5` were the "final"
  sessions of Phase 4, and report-api was retuned after seeing them (admitted in the Phase 4 note), so
  the exam is not perfectly untouched. The margins come from seed spread measured on five runs.
- **The gate cannot see everything**: it did not reject a 3-epoch model, and it does not look at the
  idle behaviour or at live data. It stops clearly worse models, not every weaker one.
- **No automatic promotion or rollback**: an accepted candidate is only kept as an artifact.
- **MLflow is not used by the gate**: the CI runs are not logged (its database is local and git-ignored).
