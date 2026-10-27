"""Offline test of the alert debounce rule on the FROZEN models.

Usage: python ml/debounce.py
Rule: raise an alarm only when k windows in a row are above the saved threshold
(a run never spans a time gap). The models and thresholds in ml/models/*.pt are
not changed. k is chosen on the tuning sessions only (faulty-1+6):
the smallest k whose false alerts/h is at most half of k=1's, with every
incident still detected; otherwise k=1. Then every part is reported for that k.
"""
import numpy as np
import torch

import autoencoder
import windows
from evaluate import STEP_S, evaluate

KS = [1, 2, 3, 4]
PARTS = {"train": windows.TRAIN, "tune": ["faulty-1", "faulty-6"],
         "final": ["faulty-2", "faulty-3", "faulty-4", "faulty-5"], "holdout": ["faulty-7"]}


def debounce(scores, times, sessions, k):
    """min of the last k scores inside one gap-free run of windows of one session."""
    out = scores.copy()
    for s in np.unique(sessions):
        idx = np.where(sessions == s)[0]
        run = 0
        for j, i in enumerate(idx):
            gap = j > 0 and (times[i] - times[idx[j - 1]]).total_seconds() > STEP_S * 1.5
            run = 1 if gap or j == 0 else run + 1
            lo = j - min(run, k) + 1
            out[i] = scores[idx[lo:j + 1]].min()
    return out


def load(app):
    ckpt = torch.load(autoencoder.MODELS / f"{app}.pt")
    windows.WINDOW, windows.LOG_LATENCY = ckpt["window"], ckpt["log_latency"]
    windows.STATS, windows.MEM_DELTA = ckpt["stats"], ckpt["mem_delta"]
    data = windows.build(app, PARTS)
    assert np.allclose(data["mean"], ckpt["mean"]) and np.allclose(data["std"], ckpt["std"])
    models = []
    for sd in ckpt["state_dicts"]:
        m = autoencoder.AutoEncoder(ckpt["n_in"], ckpt["bottleneck"])
        m.load_state_dict(sd)
        models.append(m.eval())
    return ckpt, data, models


def grade(part, scores, thr, k):
    return evaluate(debounce(scores, part["t"], part["session"], k),
                    part["y"], part["t"], part["session"], thr)


if __name__ == "__main__":
    for app in windows.APPS:
        ckpt, data, models = load(app)
        thr = ckpt["threshold"]
        scores = {p: autoencoder.rebuild_error(models, data[p]["x"]) for p in ["tune", "final", "holdout"]}
        res = {(p, k): grade(data[p], scores[p], thr, k) for p in scores for k in KS}

        base = res[("tune", 1)]["false_alerts_per_hour"]
        chosen = 1
        for k in KS:
            r = res[("tune", k)]
            if r["detected"] == r["incidents"] and r["false_alerts_per_hour"] <= base / 2:
                chosen = k
                break
        print(f"\n== {app}: k chosen on faulty-1+6 = {chosen}  (alarm after {chosen} windows in a row)")
        print(f"  {'part':8} {'k':>2} {'prec':>6} {'recall':>6} {'F1':>6} {'found':>6} {'delay_s':>8} {'false/h':>8}")
        for p in ["tune", "final", "holdout"]:
            for k in KS:
                r = res[(p, k)]
                mark = "  <- chosen" if k == chosen else ""
                print(f"  {p:8} {k:>2} {r['precision']:>6} {r['recall']:>6} {r['f1']:>6} "
                      f"{r['detected']}/{r['incidents']:>3} {str(r['mean_delay_s']):>8} "
                      f"{str(r['false_alerts_per_hour']):>8}{mark}")
