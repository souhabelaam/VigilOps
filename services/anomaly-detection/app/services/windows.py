"""Rebuild, from live rates, the exact input the model saw in training (see ml/windows.py).

Same steps in the same order: fill empty values, log latency, memory as change,
scale with the saved mean/std, describe the window with summary numbers.
"""
from collections import deque
from datetime import datetime

import numpy as np

from app.services.autoencoder import Ensemble

FIELDS = ["cpu_pct", "req_per_s", "avg_latency_ms", "memory_mb"]   # = the model's features
LATENCY, MEMORY = 2, 3   # positions in FIELDS


class WindowBuilder:
    """Keeps the recent rows of ONE app and says when a full, usable window exists."""

    def __init__(self, model: Ensemble, max_gap_s: float):
        self._model = model
        self._max_gap_s = max_gap_s
        self._last = [np.nan] * len(FIELDS)     # last known value of each feature
        self._rows: deque = deque(maxlen=model.window)   # (time, values, was_reset)
        self._previous_time: datetime | None = None

    def add(self, rate: dict) -> np.ndarray | None:
        """Add one rate. Return the model input, or None when there is no usable window yet.

        A window is unusable if it is not full, if a row is still empty, or if it
        contains a counter reset (a crash: a rule handles that, not the model).
        """
        ts = datetime.fromisoformat(rate["ts"])
        values = []
        for i, name in enumerate(FIELDS):
            if rate[name] is not None:
                self._last[i] = float(rate[name])   # empty value: carry the last known one
            values.append(self._last[i])
        if self._model.log_latency:
            values[LATENCY] = np.log1p(values[LATENCY])

        if self._previous_time and (ts - self._previous_time).total_seconds() > self._max_gap_s:
            self._rows.clear()      # never join rows across a gap
        self._previous_time = ts
        self._rows.append((ts, values, bool(rate["reset"])))

        if len(self._rows) < self._model.window:
            return None
        if any(row[2] for row in self._rows):
            return None
        window = np.array([row[1] for row in self._rows], dtype=float)
        if np.isnan(window).any():
            return None
        return self._prepare(window)

    def _prepare(self, window: np.ndarray) -> np.ndarray:
        model = self._model
        if model.mem_delta:
            window[:, MEMORY] -= window[0, MEMORY]
        scaled = (window - model.mean) / model.std
        if not model.stats:
            return scaled.reshape(-1)
        return np.concatenate([scaled.mean(axis=0), scaled.std(axis=0), scaled.min(axis=0),
                               scaled.max(axis=0), scaled[-1] - scaled[0]])
