"""Do healthy-but-different conditions cause false alarms? (found live, not in the recorded sessions)

Usage: python ml/robustness.py
For each way of encoding memory, train on the usual train sessions, take the threshold from
normal-3 as usual, then probe with HEALTHY normal-3 changed the way we saw live:
  level -20 MB : the container simply runs at a lower memory level (notes-api: 23 MB vs 50 MB)
  drop  -8 MB  : memory falls by itself in the middle of the session (report-api, 40 -> 32 MB)
  idle         : requests, cpu and latency go to ~0 for the middle third (load generator stopped)
Reported: share of healthy windows that raise an alarm after debouncing (should stay near the base).
Then the usual grades on tune / final / holdout, to make sure detection is not lost.
Probes are only for comparing variants; thresholds are never taken from them.
"""
import numpy as np

import autoencoder
import windows
from debounce import debounce
from evaluate import evaluate, pick_threshold

PARTS = {"train": windows.TRAIN, "threshold": windows.THRESHOLD,
         "tune": ["faulty-1", "faulty-6"],
         "final": ["faulty-2", "faulty-3", "faulty-4", "faulty-5"], "holdout": ["faulty-7"]}
KS = {"notes-api": 2, "report-api": 1}
VARIANTS = {"absolute": (False, False), "delta": (True, False), "growth": (False, True)}
ORIGINAL_LOAD_ROWS = windows.load_rows


def probe(kind):
    """Make load_rows return a changed copy of the healthy threshold session."""
    def load_rows(session, app):
        times, values, labels, resets, crash = ORIGINAL_LOAD_ROWS(session, app)
        if session in windows.THRESHOLD and kind != "base":
            values = values.copy()
            n, m = len(values), windows.FEATURES.index("memory_mb")
            if kind == "level -20MB":
                values[:, m] -= 20
            elif kind == "drop -8MB":
                values[n // 2:, m] -= 8
            elif kind == "idle":
                idle = slice(n // 3, 2 * n // 3)
                for name in ("cpu_pct", "req_per_s"):
                    values[idle, windows.FEATURES.index(name)] = 0.2
                values[idle, windows.FEATURES.index("avg_latency_ms")] = np.nan
        return times, values, labels, resets, crash
    windows.load_rows = load_rows


def alarm_share(models, threshold, app, k):
    data = windows.build(app, {"train": windows.TRAIN, "threshold": windows.THRESHOLD})
    d = data["threshold"]
    sc = debounce(autoencoder.rebuild_error(models, d["x"]), d["t"], d["session"], k)
    return float((sc > threshold).mean())


if __name__ == "__main__":
    for app in windows.APPS:
        cfg = dict(autoencoder.SETTINGS[app])
        k = KS[app]
        print(f"\n== {app} (k={k})  share of HEALTHY windows alarming, then detection quality")
        for name, (delta, growth) in VARIANTS.items():
            windows.load_rows = ORIGINAL_LOAD_ROWS
            windows.WINDOW, windows.LOG_LATENCY = cfg["window"], cfg["log_latency"]
            windows.STATS, windows.MEM_DELTA, windows.MEM_GROWTH = cfg["stats"], delta, growth
            data = windows.build(app, PARTS)
            x = autoencoder.tensor(data["train"]["x"])
            models = [autoencoder.train_one(x, cfg["bottleneck"], s) for s in range(autoencoder.SEEDS)]
            thr = pick_threshold(autoencoder.rebuild_error(models, data["threshold"]["x"]), cfg["quantile"])
            shares = {}
            for kind in ["base", "level -20MB", "drop -8MB", "idle"]:
                probe(kind)
                shares[kind] = round(alarm_share(models, thr, app, k), 3)
            windows.load_rows = ORIGINAL_LOAD_ROWS
            graded = {}
            for part in ["tune", "final", "holdout"]:
                d = data[part]
                graded[part] = evaluate(debounce(autoencoder.rebuild_error(models, d["x"]), d["t"], d["session"], k),
                                        d["y"], d["t"], d["session"], thr)
            print(f"  {name:8} false-alarm share {shares}")
            for part, r in graded.items():
                print(f"           {part:8} F1 {r['f1']}  recall {r['recall']}  found {r['detected']}/{r['incidents']}"
                      f"  false/h {r['false_alerts_per_hour']}")
