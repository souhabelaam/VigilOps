# Phase 2: data preparation

## What was built
`ml/prepare_data.py` turns each raw `metrics.csv` (running totals) into a table of
per-5-second rates in `ml/data/prepared/<session>.csv` (git-ignored).

Columns: `cpu_pct`, `req_per_s`, `avg_latency_ms`, `memory_mb`, `reset`, `label`, `fault`.

## Why
Counters such as `cpu_seconds_total` only go up (like a car odometer). The model needs
"how busy is it now", which is the difference between two rows divided by the seconds
between them.

## Rules in the script
- A pair of rows more than 6 s apart is never diffed (gap).
- Rows with `up=0` are skipped (the app was down, values are empty).
- A counter that goes down means the app restarted: the row is flagged `reset=1`
  and has no rates.
- A row is `label=1` when its time is inside an incident window for that app.

## Results
| session | rows | labeled | resets |
|---|---|---|---|
| normal-1 | 478 | 0 | 0 |
| normal-2 | 478 | 0 | 0 |
| normal-3 | 458 | 0 | 0 |
| normal-partial | 860 | 0 | 0 |
| faulty-1 | 478 | 92 | 0 |
| faulty-2 | 478 | 68 | 0 |
| faulty-3 | 472 | 63 | 2 |

Limits to report honestly: the dataset is small (about 96 min normal, 19 incidents).
`faulty-3` has 5 crashes but only 2 reset rows, because the other restarts happened
while the app showed `up=0`.

## How to run
`python -I ml/prepare_data.py` from the repo root.

## Still to do before training (Phase 4)
Handle empty cells, scale features (fit on train only), build time windows, split by
time: train = normal-1 + normal-2, threshold = normal-3, test = faulty-1..3.
