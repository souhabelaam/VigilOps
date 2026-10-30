"""Tune the autoencoder without touching the final test data.

Usage: python ml/tune.py
Split: train normal-1+2+4 | threshold normal-3 | tuning faulty-1+6 | final test faulty-2..5.
Settings are chosen on the tuning sessions only; the final ones are scored once, for the winner.
The baseline is graded on the same final split.
"""
import itertools

import numpy as np
import torch
from sklearn.ensemble import IsolationForest

import windows
from autoencoder import train_one, rebuild_error
from evaluate import evaluate, pick_threshold

SEEDS = 5
PARTS = {"train": windows.TRAIN, "threshold": windows.THRESHOLD,
         "tune": ["faulty-1", "faulty-6"],
         "final": ["faulty-2", "faulty-3", "faulty-4", "faulty-5"]}
GRID = {"window": [6, 12, 24], "bottleneck": [3, 6], "log": [False, True], "stats": [False, True], "memdelta": [False, True], "k": [1, 2, 3],
        "quantile": [0.95, 0.99, 0.999]}


def train_scores(data, bottleneck, parts):
    """Average rebuild error over several seeds (an ensemble) for each part."""
    x_train = torch.tensor(data["train"]["x"].reshape(len(data["train"]["x"]), -1),
                           dtype=torch.float32)
    models = [train_one(x_train, bottleneck, seed) for seed in range(SEEDS)]
    return {p: rebuild_error(models, data[p]["x"]) for p in parts}


def smooth(scores, sessions, k):
    """Alarm only after k windows in a row are high: min over the last k scores."""
    out = scores.copy()
    if k == 1:
        return out
    for s in np.unique(sessions):
        idx = np.where(sessions == s)[0]
        v = scores[idx]
        for i in range(len(v)):
            out[idx[i]] = v[max(0, i - k + 1):i + 1].min()
    return out


def grade(sc, data, part, k, q):
    d = data[part]
    thr = pick_threshold(smooth(sc["threshold"], data["threshold"]["session"], k), q)
    return evaluate(smooth(sc[part], d["session"], k), d["y"], d["t"], d["session"], thr)


def baseline(app):
    windows.WINDOW = 12
    data = windows.build(app, PARTS)

    def flat(x):
        return x.reshape(len(x), -1)

    m = IsolationForest(n_estimators=100, random_state=0).fit(flat(data["train"]["x"]))
    sc = {p: -m.score_samples(flat(data[p]["x"])) for p in ["threshold", "final"]}
    thr = pick_threshold(sc["threshold"])
    d = data["final"]
    return evaluate(sc["final"], d["y"], d["t"], d["session"], thr)


if __name__ == "__main__":
    for app in windows.APPS:
        best = None
        cache = {}
        for w, b, lg, st, md in itertools.product(GRID["window"], GRID["bottleneck"],
                                                  GRID["log"], GRID["stats"], GRID["memdelta"]):
            windows.WINDOW, windows.LOG_LATENCY, windows.STATS, windows.MEM_DELTA = w, lg, st, md
            data = windows.build(app, PARTS)
            sc = train_scores(data, b, ["threshold", "tune", "final"])
            cache[(w, b, lg, st, md)] = (data, sc)
            for k, q in itertools.product(GRID["k"], GRID["quantile"]):
                r = grade(sc, data, "tune", k, q)
                key = (r["f1"], -r["false_alerts_per_hour"])
                if best is None or key > best[0]:
                    best = (key, (w, b, lg, st, md, k, q), r)
        _, (w, b, lg, st, md, k, q), r_tune = best
        data, sc = cache[(w, b, lg, st, md)]
        final = grade(sc, data, "final", k, q)
        windows.LOG_LATENCY = windows.STATS = windows.MEM_DELTA = False  # baseline: default input
        print(f"\n{app}: chosen window={w} bottleneck={b} log_latency={lg} stats={st} "
              f"mem_delta={md} k={k} quantile={q}")
        print("  tuning (faulty-1+6):", r_tune)
        print("  FINAL autoencoder (faulty-2..5):", final)
        print("  FINAL baseline    (faulty-2..5):", baseline(app))
