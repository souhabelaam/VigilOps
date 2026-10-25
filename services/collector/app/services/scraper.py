"""Visit an app's /metrics page and turn the text into a Sample."""
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from app.schemas.sample import Sample

# our own visits and health checks must not count as traffic
IGNORED_PATHS = ("/metrics", "/health", "/faults")

# one metric line looks like:  name{label="x",other="y"} 12.5
LINE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(\S+)$')
PATH_LABEL = re.compile(r'path="([^"]*)"')

SUMMED = {
    "http_requests_total": "requests_total",
    "http_request_duration_seconds_sum": "latency_sum_seconds",
    "http_request_duration_seconds_count": "latency_count",
}


def parse_metrics(text: str, app: str, ts: str) -> Sample:
    """Read the /metrics text of a running app. Pure function, easy to test."""
    sample = Sample(ts=ts, app=app, up=True)
    for raw in text.splitlines():
        match = LINE.match(raw)
        if not match:
            continue  # comment line (# HELP / # TYPE)
        name, labels, number = match.group(1), match.group(2) or "", float(match.group(3))

        if name == "process_cpu_seconds_total":
            sample.cpu_seconds_total = number
        elif name == "process_resident_memory_bytes":
            sample.memory_bytes = number
        elif name in SUMMED:
            path = PATH_LABEL.search(labels)
            if path and path.group(1).startswith(IGNORED_PATHS):
                continue
            field = SUMMED[name]
            setattr(sample, field, getattr(sample, field) + number)
    return sample


def scrape(app: str, base_url: str, timeout: float) -> Sample:
    """Fetch one app. An unreachable app gives a Sample with up=False, never an exception."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with urllib.request.urlopen(f"{base_url}/metrics", timeout=timeout) as response:
            return parse_metrics(response.read().decode(), app, ts)
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
        return Sample(ts=ts, app=app, up=False)
