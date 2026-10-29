from datetime import datetime, timedelta, timezone

import numpy as np

from app.services.windows import WindowBuilder

T0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)


class GrowthModel:
    """3-row window, no summary stats, memory as growth; scaler does nothing."""
    window, log_latency, stats, mem_delta, mem_growth = 3, False, False, False, True
    mean, std = np.zeros(4), np.ones(4)


def feed(memories):
    builder, window = WindowBuilder(GrowthModel(), 6), None
    for i, memory in enumerate(memories):
        window = builder.add({"ts": (T0 + timedelta(seconds=5 * i)).isoformat(), "reset": False,
                              "cpu_pct": 1.0, "req_per_s": 1.0, "avg_latency_ms": 5.0, "memory_mb": memory})
    return window.reshape(3, 4)[:, 3]   # the memory column of the window


def test_memory_growth_is_kept():
    assert feed([50, 55, 60]).tolist() == [0, 5, 10]


def test_memory_falling_counts_as_zero():
    # a container returning memory by itself must not look like a fault
    assert feed([50, 45, 40]).tolist() == [0, 0, 0]


def test_memory_level_does_not_matter():
    assert feed([23, 28, 33]).tolist() == feed([53, 58, 63]).tolist()
