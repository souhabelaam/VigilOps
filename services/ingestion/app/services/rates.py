"""Turn raw counters (odometers) into rates, one app at a time.

Same rules as ml/prepare_data.py, so the model sees live data shaped like its training data.
"""
from app.schemas.sample import Rate, Sample


class RateCalculator:
    def __init__(self, max_gap_s: float):
        self._max_gap_s = max_gap_s
        self._previous: dict[str, Sample] = {}   # last good (up) sample of each app

    def process(self, cur: Sample) -> Rate | None:
        """Return the Rate row to store, or None when nothing can be stored."""
        if not cur.up:
            return None  # app down: its numbers are empty; keep the old sample for the reset check

        prev = self._previous.get(cur.app)
        self._previous[cur.app] = cur
        if prev is None:
            return None  # first sample of this app: nothing to subtract from yet

        d_cpu = cur.cpu_seconds_total - prev.cpu_seconds_total
        d_req = cur.requests_total - prev.requests_total
        d_cnt = cur.latency_count - prev.latency_count
        d_sum = cur.latency_sum_seconds - prev.latency_sum_seconds
        memory_mb = round(cur.memory_bytes / 1e6, 3)

        # a counter that went down means the app restarted. Checked BEFORE the gap rule,
        # because a crash leaves a gap and we do not want to lose the crash signal.
        if d_cpu < 0 or d_req < 0 or d_cnt < 0 or d_sum < 0:
            return Rate(cur.ts, cur.app, None, None, None, memory_mb, reset=True)

        seconds = (cur.ts - prev.ts).total_seconds()
        if seconds <= 0 or seconds > self._max_gap_s:
            return None  # gap: never subtract across it

        return Rate(
            ts=cur.ts,
            app=cur.app,
            cpu_pct=round(d_cpu / seconds * 100, 3),
            req_per_s=round(d_req / seconds, 3),
            # no requests in the window -> latency undefined
            avg_latency_ms=round(d_sum / d_cnt * 1000, 3) if d_cnt > 0 else None,
            memory_mb=memory_mb,
            reset=False,
        )
