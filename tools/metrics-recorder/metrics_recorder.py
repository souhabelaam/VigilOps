"""Metrics recorder: saves the apps' /metrics numbers to a CSV file.

Every few seconds it visits each app's /metrics page and appends one row per app.
The values are the raw counters; rates (CPU per second, requests per second,
average latency) are computed later from the difference between two rows.
Business requests only: /metrics, /health and /faults are not counted, so the
recorder and injector do not pollute the data. Standard library only.

Usage:
    python metrics_recorder.py --out metrics.csv
    python metrics_recorder.py --out metrics.csv --interval 5 --duration 3600
"""

import argparse
import csv
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

APPS = {
    "notes-api": "http://127.0.0.1:8001",
    "report-api": "http://127.0.0.1:8002",
}
COLUMNS = [
    "timestamp_utc", "app", "up",
    "cpu_seconds_total", "memory_bytes",
    "requests_total", "latency_sum_seconds", "latency_count",
]
IGNORED_PATHS = ("/metrics", "/health", "/faults")

# one metric line looks like:  name{label="x",other="y"} 12.5
LINE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(\S+)$')
PATH_LABEL = re.compile(r'path="([^"]*)"')


def read_metrics(base_url: str) -> dict | None:
    """Fetch /metrics and return the numbers we record, or None if the app is unreachable."""
    try:
        with urllib.request.urlopen(f"{base_url}/metrics", timeout=5) as response:
            text = response.read().decode()
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None

    values = {"cpu": 0.0, "memory": 0.0, "requests": 0.0, "lat_sum": 0.0, "lat_count": 0.0}
    for raw in text.splitlines():
        match = LINE.match(raw)
        if not match:
            continue  # comment line (# HELP / # TYPE)
        name, labels, number = match.group(1), match.group(2) or "", float(match.group(3))

        if name == "process_cpu_seconds_total":
            values["cpu"] = number
        elif name == "process_resident_memory_bytes":
            values["memory"] = number
        elif name in ("http_requests_total", "http_request_duration_seconds_sum",
                      "http_request_duration_seconds_count"):
            path = PATH_LABEL.search(labels)
            if path and path.group(1).startswith(IGNORED_PATHS):
                continue
            key = {"http_requests_total": "requests",
                   "http_request_duration_seconds_sum": "lat_sum",
                   "http_request_duration_seconds_count": "lat_count"}[name]
            values[key] += number
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Save the apps' metrics to a CSV file")
    parser.add_argument("--out", default="metrics.csv")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between scrapes")
    parser.add_argument("--duration", type=float, default=0, help="seconds to run, 0 = until Ctrl+C")
    args = parser.parse_args()

    is_new = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
    start = time.time()
    rows = 0

    with open(args.out, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if is_new:
            writer.writerow(COLUMNS)
        try:
            while args.duration == 0 or time.time() - start < args.duration:
                tick = time.time()
                stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                for app, url in APPS.items():
                    v = read_metrics(url)
                    if v is None:  # app down (for example a crash fault): record up=0
                        writer.writerow([stamp, app, 0, "", "", "", "", ""])
                    else:
                        writer.writerow([stamp, app, 1, v["cpu"], v["memory"],
                                         v["requests"], v["lat_sum"], v["lat_count"]])
                    rows += 1
                file.flush()
                time.sleep(max(0.0, args.interval - (time.time() - tick)))
        except KeyboardInterrupt:
            pass
    print(f"done: {rows} rows written to {args.out}")


if __name__ == "__main__":
    main()
