"""The two shapes ingestion handles: a raw Sample from the queue, a Rate for the database."""
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class Sample:
    """Raw counters of one app at one moment (the collector's message)."""
    ts: datetime
    app: str
    up: bool
    cpu_seconds_total: float
    memory_bytes: float
    requests_total: float
    latency_sum_seconds: float
    latency_count: float

    @classmethod
    def from_message(cls, data: dict) -> "Sample":
        return cls(
            ts=datetime.fromisoformat(data["ts"]),
            app=data["app"],
            up=bool(data["up"]),
            cpu_seconds_total=float(data["cpu_seconds_total"]),
            memory_bytes=float(data["memory_bytes"]),
            requests_total=float(data["requests_total"]),
            latency_sum_seconds=float(data["latency_sum_seconds"]),
            latency_count=float(data["latency_count"]),
        )


@dataclass
class Rate:
    """One row of metric_rates. Rates are None when they cannot be computed."""
    ts: datetime
    app: str
    cpu_pct: float | None
    req_per_s: float | None
    avg_latency_ms: float | None
    memory_mb: float
    reset: bool

    def to_message(self) -> dict:
        """The JSON-ready dict sent to the rates queue (timestamp as text)."""
        message = asdict(self)
        message["ts"] = self.ts.isoformat()
        return message
