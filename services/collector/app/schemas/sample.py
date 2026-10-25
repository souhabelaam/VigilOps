"""The message the collector sends: raw counters of one app at one moment."""
from dataclasses import asdict, dataclass


@dataclass
class Sample:
    ts: str                      # ISO time when the collector read the app
    app: str                     # notes-api or report-api
    up: bool                     # False when the app could not be reached
    cpu_seconds_total: float = 0.0
    memory_bytes: float = 0.0
    requests_total: float = 0.0
    latency_sum_seconds: float = 0.0
    latency_count: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)
