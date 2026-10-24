"""Fault injector: breaks the target apps on a schedule and records when.

Loop: wait a normal period -> pick an app and a fault -> turn it ON -> wait ->
turn it OFF. Every incident is appended to a label CSV (the ground truth that the
anomaly detector is trained and tested against). Standard library only.

The apps must be started with FAULTS_ENABLED=true.

Usage:
    python fault_injector.py --labels labels.csv
    python fault_injector.py --labels labels.csv --total 3600 --fault-min 60 --fault-max 120 --gap-min 120 --gap-max 300
"""

import argparse
import csv
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

APPS = {
    "notes-api": "http://127.0.0.1:8001",
    "report-api": "http://127.0.0.1:8002",
}
LABEL_COLUMNS = ["fault", "target", "start_utc", "end_utc", "detail"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def press(method: str, url: str) -> int:
    """Send one request to a /faults button. Returns the HTTP status (0 = unreachable)."""
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError):
        return 0


def turn_on(fault: str, base_url: str) -> str:
    """Start one fault. Returns a short detail string for the label file."""
    if fault == "latency":
        delay_ms = random.choice([500, 1000, 1500, 2000])
        status = press("POST", f"{base_url}/faults/latency?delay_ms={delay_ms}")
        detail = f"delay_ms={delay_ms}"
    else:
        status = press("POST", f"{base_url}/faults/{fault}")
        detail = ""
    if status != 200:
        raise RuntimeError(f"could not start {fault} on {base_url} (HTTP {status}); is FAULTS_ENABLED=true?")
    return detail


def turn_off(fault: str, base_url: str) -> None:
    if fault != "crash":  # a crash has no OFF button: the app is simply restarted
        press("DELETE", f"{base_url}/faults/{fault}")


def append_label(path: str, row: dict) -> None:
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=LABEL_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def run_incident(fault: str, target: str, seconds: float, labels: str) -> None:
    base_url = APPS[target]
    detail = turn_on(fault, base_url)
    start = now_iso()
    print(f"[{start}] ON  {fault} on {target} {detail} for {seconds:.0f}s", flush=True)
    try:
        time.sleep(seconds)
    finally:
        # Always switch the fault off and record it, even on Ctrl+C.
        turn_off(fault, base_url)
        end = now_iso()
        append_label(labels, {"fault": fault, "target": target, "start_utc": start, "end_utc": end, "detail": detail})
        print(f"[{end}] OFF {fault} on {target}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Break the target apps on a schedule and record the labels")
    parser.add_argument("--labels", default="labels.csv", help="CSV file the incidents are appended to")
    parser.add_argument("--faults", default="cpu,memory,latency", help="comma list from: cpu,memory,latency,crash")
    parser.add_argument("--targets", default=",".join(APPS), help="comma list of apps to break (default: all)")
    parser.add_argument("--total", type=float, default=0, help="seconds to run, 0 = until Ctrl+C")
    parser.add_argument("--fault-min", type=float, default=120, help="shortest incident, seconds")
    parser.add_argument("--fault-max", type=float, default=300, help="longest incident, seconds")
    parser.add_argument("--gap-min", type=float, default=300, help="shortest normal period between incidents")
    parser.add_argument("--gap-max", type=float, default=900, help="longest normal period between incidents")
    args = parser.parse_args()

    faults = [name.strip() for name in args.faults.split(",") if name.strip()]
    targets = [name.strip() for name in args.targets.split(",") if name.strip()]
    unknown = [name for name in targets if name not in APPS]
    if unknown:
        parser.error(f"unknown target(s): {', '.join(unknown)}; choose from {', '.join(APPS)}")
    start = time.time()

    try:
        while args.total == 0 or time.time() - start < args.total:
            gap = random.uniform(args.gap_min, args.gap_max)
            print(f"normal period: {gap:.0f}s", flush=True)
            time.sleep(gap)
            if args.total and time.time() - start >= args.total:
                break
            run_incident(
                fault=random.choice(faults),
                target=random.choice(targets),
                seconds=random.uniform(args.fault_min, args.fault_max),
                labels=args.labels,
            )
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
