"""Load generator: pretends to be users calling notes-api and report-api.

It sends a steady, slightly random stream of requests so the apps' metrics
(CPU, memory, latency) look like a real, healthy service. Standard library only.

Usage:
    python load_generator.py                      # run until Ctrl+C
    python load_generator.py --rate 3 --duration 600
"""

import argparse
import json
import random
import time
import urllib.error
import urllib.request

NOTES_URL = "http://127.0.0.1:8001"
REPORTS_URL = "http://127.0.0.1:8002"


def call(method: str, url: str, body: dict | None = None):
    """Send one HTTP request. Returns (status_code, parsed_json_or_None)."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError):
        return 0, None  # app unreachable (for example during a crash fault)


class User:
    """One fake user. Each step() does one random action."""

    def __init__(self, notes_url: str, reports_url: str) -> None:
        self.notes_url = notes_url
        self.reports_url = reports_url
        self.my_note_ids: list[int] = []  # notes this user may delete later

    def step(self) -> int:
        action = random.choices(
            ["create_note", "list_notes", "delete_note", "make_report", "list_reports"],
            weights=[25, 30, 20, 15, 10],
        )[0]
        return getattr(self, action)()

    def create_note(self) -> int:
        body = {"title": f"note {random.randint(1, 9999)}", "content": "x" * random.randint(0, 200)}
        status, note = call("POST", f"{self.notes_url}/notes", body)
        if status == 201 and note:
            self.my_note_ids.append(note["id"])
        return status

    def list_notes(self) -> int:
        return call("GET", f"{self.notes_url}/notes")[0]

    def delete_note(self) -> int:
        if not self.my_note_ids:
            return self.create_note()
        note_id = self.my_note_ids.pop(random.randrange(len(self.my_note_ids)))
        return call("DELETE", f"{self.notes_url}/notes/{note_id}")[0]

    def make_report(self) -> int:
        # small limits keep the CPU cost modest: about 0.01 to 0.3 s each
        limit = random.randint(5_000, 60_000)
        return call("POST", f"{self.reports_url}/reports", {"limit": limit})[0]

    def list_reports(self) -> int:
        return call("GET", f"{self.reports_url}/reports")[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Send steady fake traffic to the target apps")
    parser.add_argument("--rate", type=float, default=2.0, help="average requests per second")
    parser.add_argument("--duration", type=float, default=0, help="seconds to run, 0 = until Ctrl+C")
    parser.add_argument("--notes-url", default=NOTES_URL)
    parser.add_argument("--reports-url", default=REPORTS_URL)
    args = parser.parse_args()

    user = User(args.notes_url, args.reports_url)
    start = time.time()
    last_print = start
    sent = errors = 0

    try:
        while args.duration == 0 or time.time() - start < args.duration:
            status = user.step()
            sent += 1
            if not 200 <= status < 300:
                errors += 1

            # Random pause around 1/rate seconds, so traffic is steady but not robotic.
            time.sleep(random.expovariate(args.rate))

            if time.time() - last_print >= 10:
                print(f"{int(time.time() - start):>6}s  sent={sent}  errors={errors}", flush=True)
                last_print = time.time()
    except KeyboardInterrupt:
        pass
    print(f"done: sent={sent} errors={errors}")


if __name__ == "__main__":
    main()
