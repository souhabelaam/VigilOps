"""Scoring of an anomaly detector: the same code grades every model.

A model gives one anomaly score per window (higher = more unusual).
The threshold comes from healthy validation data only, never from test data.
"""
import numpy as np

STEP_S = 5  # seconds between two windows


def pick_threshold(val_scores, quantile=0.99):
    """Alarm level: the score that 99% of healthy validation windows stay under."""
    return float(np.quantile(val_scores, quantile))


def runs(mask):
    """Start/end indexes of each stretch of True in a boolean array."""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        if not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def evaluate(scores, y, times, sessions, threshold):
    """Window metrics + incident metrics. Arrays are in time order per session."""
    # y: 1 = incident, 0 = healthy, 2 = fault just ended (ignored: neither hit nor false alarm)
    alarm = scores > threshold
    tp = int((alarm & (y == 1)).sum())
    fp = int((alarm & (y == 0)).sum())
    fn = int((~alarm & (y == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    # incidents = stretches of anomalous windows inside one session
    detected, delays, false_events = 0, [], 0
    normal_seconds = int((y == 0).sum()) * STEP_S
    for s in np.unique(sessions):
        idx = np.where(sessions == s)[0]
        ys, al, ts = y[idx], alarm[idx], [times[i] for i in idx]
        for a, b in runs(ys == 1):
            hit = np.where(al[a:b + 1])[0]
            if len(hit):
                detected += 1
                delays.append((ts[a + hit[0]] - ts[a]).total_seconds())
        false_events += len(runs(al & (ys == 0)))
    n_inc = sum(len(runs(y[sessions == s] == 1)) for s in np.unique(sessions))
    hours = normal_seconds / 3600
    return {
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "incidents": n_inc, "detected": detected,
        "mean_delay_s": round(float(np.mean(delays)), 1) if delays else None,
        "false_alerts_per_hour": round(false_events / hours, 1) if hours else None,
    }
