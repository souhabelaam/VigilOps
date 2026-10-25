"""Turn raw metrics.csv (running totals) into per-5-second rate tables.

Usage: python ml/prepare_data.py
Reads  ml/data/<session>/metrics.csv (+ labels.csv for faulty sessions)
Writes ml/data/prepared/<session>.csv
"""
import csv
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "prepared"
SESSIONS = [
    "normal-1", "normal-2", "normal-3", "normal-4", "normal-partial",
    "faulty-1", "faulty-2", "faulty-3", "faulty-4", "faulty-5", "faulty-6",
]
MAX_GAP_S = 6.0  # a pair of rows further apart than this is never diffed

COLUMNS = ["session", "timestamp_utc", "app", "cpu_pct", "req_per_s",
           "avg_latency_ms", "memory_mb", "reset", "label", "fault"]


def parse_time(text):
    return datetime.fromisoformat(text)


def read_metrics(path):
    """Return {app: [row dicts sorted by time]} with numbers converted."""
    by_app = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if int(r["up"]) == 0:
                # app was down (crash): the numbers are empty
                row = {"t": parse_time(r["timestamp_utc"]),
                       "ts": r["timestamp_utc"], "up": 0}
                by_app.setdefault(r["app"], []).append(row)
                continue
            row = {
                "t": parse_time(r["timestamp_utc"]),
                "ts": r["timestamp_utc"],
                "up": int(r["up"]),
                "cpu": float(r["cpu_seconds_total"]),
                "mem": float(r["memory_bytes"]),
                "req": float(r["requests_total"]),
                "lat_sum": float(r["latency_sum_seconds"]),
                "lat_cnt": float(r["latency_count"]),
            }
            by_app.setdefault(r["app"], []).append(row)
    for rows in by_app.values():
        rows.sort(key=lambda x: x["t"])
    return by_app


def read_labels(path):
    """Return list of (app, fault, start, end); empty if no label file."""
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return [(r["target"], r["fault"],
                 parse_time(r["start_utc"]), parse_time(r["end_utc"]))
                for r in csv.DictReader(f)]


def find_label(labels, app, t):
    for target, fault, start, end in labels:
        if target == app and start <= t <= end:
            return 1, fault
    return 0, ""


def rates_for_app(session, app, rows, labels):
    out = []
    for prev, cur in zip(rows, rows[1:]):
        if prev["up"] == 0 or cur["up"] == 0:
            continue  # app was down: no valid counters
        seconds = (cur["t"] - prev["t"]).total_seconds()
        if seconds <= 0 or seconds > MAX_GAP_S:
            continue  # gap: never diff across it

        d_cpu = cur["cpu"] - prev["cpu"]
        d_req = cur["req"] - prev["req"]
        d_cnt = cur["lat_cnt"] - prev["lat_cnt"]
        d_sum = cur["lat_sum"] - prev["lat_sum"]
        # a counter that went down means the app restarted (crash signal)
        reset = int(d_cpu < 0 or d_req < 0 or d_cnt < 0 or d_sum < 0)

        label, fault = find_label(labels, app, cur["t"])
        if reset:
            # rates are meaningless, keep the row only as a crash marker
            cpu_pct = req_s = lat_ms = ""
        else:
            cpu_pct = round(d_cpu / seconds * 100, 3)
            req_s = round(d_req / seconds, 3)
            # no requests in the window -> latency undefined, leave empty
            lat_ms = round(d_sum / d_cnt * 1000, 3) if d_cnt > 0 else ""
        out.append([session, cur["ts"], app, cpu_pct, req_s, lat_ms,
                    round(cur["mem"] / 1e6, 3), reset, label, fault])
    return out


def main():
    OUT.mkdir(exist_ok=True)
    for session in SESSIONS:
        folder = DATA / session
        by_app = read_metrics(folder / "metrics.csv")
        labels = read_labels(folder / "labels.csv")
        rows = []
        for app, app_rows in by_app.items():
            rows += rates_for_app(session, app, app_rows, labels)
        rows.sort(key=lambda r: (r[1], r[2]))
        with open(OUT / f"{session}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(rows)
        n_label = sum(r[8] for r in rows)
        n_reset = sum(r[7] for r in rows)
        print(f"{session:15} rows={len(rows):5} labeled={n_label:4} resets={n_reset}")


if __name__ == "__main__":
    main()
