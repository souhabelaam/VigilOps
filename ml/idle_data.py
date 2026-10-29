"""Does training on sessions with idle periods reduce false alarms? (decided before running)

Usage: python ml/idle_data.py
A = current training sessions, B = A + normal-5 + normal-7 (traffic on/off cycles, long idle).
Same settings, same seeds, threshold from normal-3 for both. Tests never used for training:
  normal-6   : healthy, traffic on/off, has one 313 s gap (laptop slept)
  live-idle  : healthy episode taken from the live stack (idle ~16 min, then traffic), exported from PostgreSQL
Adopt B only if it has fewer false alarms on those two tests (and no more on the other) and no F1 on
tune/final/holdout drops by more than 0.03 for either app.
"""
import autoencoder
import windows
from debounce import debounce
from evaluate import evaluate, pick_threshold

KS = {"notes-api": 2, "report-api": 1}
EXTRA = ["normal-5", "normal-7"]
TESTS = {"normal-6": ["normal-6"], "live-idle": ["live-idle"]}
GRADED = {"tune": ["faulty-1", "faulty-6"], "final": ["faulty-2", "faulty-3", "faulty-4", "faulty-5"],
          "holdout": ["faulty-7"]}


def share(models, data, part, thr, k):
    d = data[part]
    if not len(d["y"]):
        return None, 0
    sc = debounce(autoencoder.rebuild_error(models, d["x"]), d["t"], d["session"], k)
    return round(float((sc > thr).mean()), 3), len(d["y"])


if __name__ == "__main__":
    for app in windows.APPS:
        cfg, k = autoencoder.SETTINGS[app], KS[app]
        windows.WINDOW, windows.LOG_LATENCY = cfg["window"], cfg["log_latency"]
        windows.STATS, windows.MEM_DELTA, windows.MEM_GROWTH = cfg["stats"], cfg["mem_delta"], cfg["mem_growth"]
        print(f"\n== {app} (k={k})")
        for name, train in [("A current", windows.TRAIN), ("B + idle sessions", windows.TRAIN + EXTRA)]:
            parts = {"train": train, "threshold": windows.THRESHOLD, **TESTS, **GRADED}
            data = windows.build(app, parts)
            x = autoencoder.tensor(data["train"]["x"])
            models = [autoencoder.train_one(x, cfg["bottleneck"], s) for s in range(autoencoder.SEEDS)]
            thr = pick_threshold(autoencoder.rebuild_error(models, data["threshold"]["x"]), cfg["quantile"])
            shares = {t: share(models, data, t, thr, k) for t in ["threshold", *TESTS]}
            print(f"  {name:18} train windows {len(data['train']['y'])}  threshold {thr:.3f}")
            print("     false-alarm share (windows):", {t: f"{s} of {n}" for t, (s, n) in shares.items()})
            for part in GRADED:
                d = data[part]
                r = evaluate(debounce(autoencoder.rebuild_error(models, d["x"]), d["t"], d["session"], k),
                             d["y"], d["t"], d["session"], thr)
                print(f"     {part:8} F1 {r['f1']}  recall {r['recall']}  found {r['detected']}/{r['incidents']}"
                      f"  false/h {r['false_alerts_per_hour']}")
