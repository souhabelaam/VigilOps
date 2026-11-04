# Evaluation summary: baseline against autoencoder

One-page summary of the model evaluation. Every number is copied from [phase-4-ml.md](phase-4-ml.md), where the method, the split and the caveats are explained in full.

## The five measures

| measure | plain meaning |
|---|---|
| precision | of all alarms, how many were real (correct alarms / all alarms) |
| recall | of all real incidents, how many were caught (caught / all real) |
| F1 | one number that mixes precision and recall (higher is better, 1.0 is perfect) |
| detection delay | seconds from the start of the fault to the first alarm |
| false alerts per hour | alarms raised while the app was healthy, scaled to one hour |

## How it was graded

- The split is by time, never random. Train: normal-1, 2, 4. Threshold: normal-3 (healthy data only). Tuning: faulty-1 and 6.
- The baseline is an IsolationForest from scikit-learn with default settings, scored on the same sessions.
- Crash incidents are handled by a rule (app down or counter reset), not by the autoencoder, and are not part of these tables.

## Result 1: final test (faulty-2..5, never used for tuning)

| app | model | precision | recall | F1 | detected | mean delay | false alerts/h |
|---|---|---|---|---|---|---|---|
| notes-api | IsolationForest | 0.275 | 0.708 | 0.396 | 7/7 | 5.7 s | 13.1 |
| notes-api | **autoencoder** | 0.977 | 0.949 | **0.963** | 7/7 | 5.0 s | 4.0 |
| report-api | IsolationForest | 1.000 | 0.353 | 0.522 | 3/6 | 11.7 s | 0.0 |
| report-api | **autoencoder** | 0.771 | 0.985 | **0.865** | 6/6 | 0.8 s | 18.3 |

## Result 2: held-out session (faulty-7, recorded after the models were frozen)

| app | model | precision | recall | F1 | detected | mean delay | false alerts/h |
|---|---|---|---|---|---|---|---|
| notes-api | IsolationForest | 1.000 | 0.222 | 0.364 | 1/3 | 20.0 s | 0.0 |
| notes-api | **autoencoder** | 0.958 | 0.852 | **0.902** | 3/3 | 6.7 s | 10.6 |
| report-api | IsolationForest | 1.000 | 0.265 | 0.419 | 2/4 | 35.0 s | 0.0 |
| report-api | **autoencoder** | 0.977 | 0.977 | **0.977** | 4/4 | 1.2 s | 7.1 |

## What to say about it

- The autoencoder beats the baseline on F1 on every app and every test set, and it detects every incident. The baseline misses half of the report-api incidents and most of notes-api's on the held-out session.
- The baseline sometimes has fewer false alarms (0.0 per hour on report-api), but only because it raises few alarms at all: its recall is 0.22 to 0.35.
- The autoencoder is not free of problems. report-api has 18.3 false alerts per hour on the final test. In the running system, a debounce rule (notes-api: 2 alarms in a row) and a cool-down (one notification per incident) reduce what the user sees.
- notes-api scored lower on the held-out session (0.902) than on the final test (0.963). A fair range for new data is about 0.90 to 0.96 for notes-api and 0.87 to 0.98 for report-api.

## Limits

- Few incidents: 7 and 6 non-crash incidents in the final test, 3 and 4 in the held-out session. Differences of a few points are noise.
- The faults are injected by our tool, not real incidents.
- The report-api memory fix was found after seeing the final-test results, so part of its gain is tuned to those sessions. The held-out session did not show inflation (0.977).
- False alerts per hour on the held-out session come from about 12 healthy minutes, so each number is rough.
- Seed spread (5 repeats of the whole training): notes-api F1 0.957 ± 0.009, report-api 0.870 ± 0.029.

## Reproduce

```
ml\.venv\Scripts\python.exe ml\holdout.py      # scores the saved models on faulty-7
ml\.venv\Scripts\python.exe ml\autoencoder.py  # trains, grades on faulty-2..5, exports (logs to MLflow)
```

Data comes from DVC (`dvc pull`). The retrain gate ([phase-10-mlops-gate.md](phase-10-mlops-gate.md)) uses the same grading to accept or reject a new model.
