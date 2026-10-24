# Running data sessions

A session is one run of the apps with traffic, while the recorder saves metrics.
A **normal** session has no faults. A **faulty** session also runs the injector,
which writes the labels. Each session gets its own folder in `ml/data/`
(git-ignored, so big CSV files are never committed).

## Pieces
| Piece | Script | What it does |
|---|---|---|
| Apps | `docker-compose.yml` | notes-api (8001) and report-api (8002), limits, faults switchable |
| Load generator | `tools/load-generator/load_generator.py` | steady fake traffic |
| Metrics recorder | `tools/metrics-recorder/metrics_recorder.py` | saves `/metrics` to a CSV every 5 s |
| Fault injector | `tools/fault-injector/fault_injector.py` | turns faults on/off, writes the label CSV |

## Prepare (once per session)
```
docker compose up --build -d
mkdir ml\data\normal-1
```
Use a new folder name each time (`normal-2`, `faulty-1`, ...).

## Normal session: three steps, no injector
Open two terminals in the project root.

Terminal 1, traffic:
```
python tools\load-generator\load_generator.py --rate 2 --duration 3600
```
Terminal 2, recorder:
```
python tools\metrics-recorder\metrics_recorder.py --out ml\data\normal-1\metrics.csv --duration 3600
```
`--duration` is in seconds (3600 = 1 hour). Start with a 10-minute rehearsal (600).

Result: `metrics.csv` of healthy behavior.

## Faulty session: same plus the injector
Third terminal, started at the same time:
```
python tools\fault-injector\fault_injector.py --labels ml\data\faulty-1\labels.csv --total 3600
```
Result in the session folder: `metrics.csv` (the numbers) and `labels.csv` (when each
fault started and ended). For a quick rehearsal add
`--fault-min 30 --fault-max 60 --gap-min 60 --gap-max 120`.

## Checks
- Before a **normal** session make sure no fault is left on: `curl http://127.0.0.1:8001/faults`
  and `curl http://127.0.0.1:8002/faults` must show cpu/memory false and latency_ms 0.
  If not, run `docker compose restart`.
- The laptop must not go to sleep during a session (it would leave a gap in the data).
- Stop everything with Ctrl+C in each terminal, then `docker compose down` when done.

## Why Docker for sessions
CPU and memory metrics (`process_cpu_seconds_total`, `process_resident_memory_bytes`)
only exist on Linux, so sessions must use the containers, not the Windows virtualenvs.
