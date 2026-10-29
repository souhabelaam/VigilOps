"""Decide, for each incoming rate, whether the app looks broken."""
from collections import deque

from app.services.autoencoder import Ensemble
from app.services.windows import WindowBuilder


def decide(scores, k: int, threshold: float) -> bool:
    """True when the last k scores are ALL above the threshold.

    One high score can be a blip; k in a row is a real change. Fewer than k scores
    so far means we cannot tell yet. (Same rule as ml/debounce.py.)
    """
    return len(scores) >= k and all(s > threshold for s in list(scores)[-k:])


class AppDetector:
    """Everything the service remembers about ONE app."""

    def __init__(self, model: Ensemble, k: int, max_gap_s: float):
        self._model = model
        self._k = k
        self._builder = WindowBuilder(model, max_gap_s)
        self._scores: deque = deque(maxlen=k)   # only the last k scores matter

    def process(self, rate: dict) -> dict | None:
        """Return an anomaly event for this rate, or None when all looks normal."""
        window = self._builder.add(rate)

        if rate["reset"]:
            # a counter went down: the app restarted. The autoencoder cannot see
            # crashes (after a restart the numbers look healthy), so a rule does.
            self._scores.clear()
            return self._event(rate, "crash", None)

        if window is None:
            self._scores.clear()   # no usable window (not full, or after a gap): count again from zero
            return None

        score = self._model.score(window)
        self._scores.append(score)
        if decide(self._scores, self._k, self._model.threshold):
            return self._event(rate, "model", score)
        return None

    def _event(self, rate: dict, kind: str, score: float | None) -> dict:
        return {"ts": rate["ts"], "app": rate["app"], "kind": kind,
                "score": None if score is None else round(score, 4),
                "threshold": round(self._model.threshold, 4)}
