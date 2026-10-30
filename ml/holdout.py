"""Score the FROZEN exported models on a session recorded after they were exported.

Usage: python ml/holdout.py [session]      (default: faulty-7)
Nothing is trained or tuned here: weights, scaler and threshold come from
ml/models/<app>.pt. Also grades the crash rule (counter reset or up=0 inside a crash label).
"""
import csv
import sys
from datetime import datetime

import numpy as np
import torch

import autoencoder
import windows
from evaluate import evaluate

SESSION = sys.argv[1] if len(sys.argv) > 1 else "faulty-7"


def score_autoencoder(app):
    ckpt = torch.load(autoencoder.MODELS / f"{app}.pt")
    windows.WINDOW, windows.LOG_LATENCY = ckpt["window"], ckpt["log_latency"]
    windows.STATS, windows.MEM_DELTA = ckpt["stats"], ckpt["mem_delta"]
    windows.MEM_GROWTH = ckpt.get("mem_growth", False)
    data = windows.build(app, {"train": windows.TRAIN, "holdout": [SESSION]})
    # the rebuilt scaler must equal the saved one, or the inputs are not the same
    assert np.allclose(data["mean"], ckpt["mean"]) and np.allclose(data["std"], ckpt["std"])
    models = []
    for sd in ckpt["state_dicts"]:
        m = autoencoder.AutoEncoder(ckpt["n_in"], ckpt["bottleneck"])
        m.load_state_dict(sd)
        models.append(m.eval())
    h = data["holdout"]
    scores = autoencoder.rebuild_error(models, h["x"])
    res = evaluate(scores, h["y"], h["t"], h["session"], ckpt["threshold"])
    res["windows"], res["anomalous"] = len(h["y"]), int((h["y"] == 1).sum())
    return res


def score_baseline(app):
    autoencoder.PARTS["final"] = [SESSION]
    res = autoencoder.run_baseline(app)
    return res


def crash_rule(app):
    """Did a counter reset or an up=0 row fall inside each crash label of this app?"""

    def t(s):
        return datetime.fromisoformat(s)

    with open(windows.PREPARED / f"{SESSION}.csv", newline="") as f:
        resets = [t(r["timestamp_utc"]) for r in csv.DictReader(f)
                  if r["app"] == app and r["reset"] == "1"]
    with open(autoencoder.Path(windows.PREPARED).parent / SESSION / "metrics.csv", newline="") as f:
        down = [t(r["timestamp_utc"]) for r in csv.DictReader(f)
                if r["app"] == app and r["up"] == "0"]
    with open(autoencoder.Path(windows.PREPARED).parent / SESSION / "labels.csv", newline="") as f:
        crashes = [(t(r["start_utc"]), t(r["end_utc"])) for r in csv.DictReader(f)
                   if r["target"] == app and r["fault"] == "crash"]
    caught = sum(any(a <= x <= b for x in resets + down) for a, b in crashes)
    return {"crashes": len(crashes), "caught_by_rule": caught}


if __name__ == "__main__":
    for app in windows.APPS:
        print(f"== {app} on {SESSION}")
        print("  autoencoder (frozen):", score_autoencoder(app))
        print("  isolation forest    :", score_baseline(app))
        print("  crash rule          :", crash_rule(app))
