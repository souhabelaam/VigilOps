from datetime import datetime, timedelta, timezone

import numpy as np

from app.services.detector import AppDetector, decide

T0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)


class StubModel:
    """Window of 2 rows; the score is simply the cpu of the last row."""
    window, log_latency, stats, mem_delta, mem_growth = 2, False, False, False, False
    mean, std, threshold = np.zeros(4), np.ones(4), 10.0

    def score(self, x):
        return float(x[-4])


def rate(second, cpu=1.0, reset=False):
    return {"ts": (T0 + timedelta(seconds=second)).isoformat(), "app": "notes-api",
            "cpu_pct": None if reset else cpu, "req_per_s": 1.0, "avg_latency_ms": 5.0,
            "memory_mb": 50.0, "reset": reset}


def feed(detector, cpus, start=0):
    return [detector.process(rate(start + 5 * i, cpu)) for i, cpu in enumerate(cpus)]


def test_decide_needs_k_scores_in_a_row_above_threshold():
    assert decide([11, 12], 2, 10) is True
    assert decide([11, 9], 2, 10) is False
    assert decide([12], 2, 10) is False       # not enough scores yet
    assert decide([9, 11], 1, 10) is True     # k=1: only the last one counts


def test_quiet_app_gives_no_event():
    assert feed(AppDetector(StubModel(), 1, 6), [1, 1, 1, 1]) == [None] * 4


def test_first_row_has_no_full_window():
    assert feed(AppDetector(StubModel(), 1, 6), [50])[0] is None   # window needs 2 rows


def test_k2_ignores_one_blip_but_alarms_on_two():
    events = feed(AppDetector(StubModel(), 2, 6), [1, 1, 50, 1, 50, 50])
    assert [e is not None for e in events] == [False, False, False, False, False, True]
    assert events[-1]["kind"] == "model" and events[-1]["score"] == 50.0


def test_counter_reset_is_a_crash_event_at_once():
    detector = AppDetector(StubModel(), 2, 6)
    feed(detector, [1, 1])
    event = detector.process(rate(10, reset=True))
    assert event["kind"] == "crash" and event["score"] is None


def test_gap_restarts_the_count():
    detector = AppDetector(StubModel(), 2, 6)
    feed(detector, [1, 50, 50])
    # 60 s of silence, then a high row: only 1 row after the gap, so no alarm
    assert detector.process(rate(75, 50)) is None
