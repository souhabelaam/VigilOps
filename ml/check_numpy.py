"""Proof that the detection service gives the same scores as PyTorch.

Usage: python ml/check_numpy.py [session]     (default: faulty-7)
Two paths over the same recorded session:
  A) ml/windows.py + the torch networks   (how the models were trained and graded)
  B) the service code: rows arrive one by one -> WindowBuilder -> numpy Ensemble
The scores must match on every window that path A also has.
"""
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

import autoencoder
import windows

sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "anomaly-detection"))
from app.services.autoencoder import Ensemble          # noqa: E402
from app.services.windows import WindowBuilder         # noqa: E402

SESSION = sys.argv[1] if len(sys.argv) > 1 else "faulty-7"
SERVICE_MODELS = Path(__file__).parent.parent / "services" / "anomaly-detection" / "models"


def torch_scores(app):
    ckpt = torch.load(autoencoder.MODELS / f"{app}.pt")
    windows.WINDOW, windows.LOG_LATENCY = ckpt["window"], ckpt["log_latency"]
    windows.STATS, windows.MEM_DELTA = ckpt["stats"], ckpt["mem_delta"]
    data = windows.build(app, {"train": windows.TRAIN, "check": [SESSION]})
    models = []
    for sd in ckpt["state_dicts"]:
        m = autoencoder.AutoEncoder(ckpt["n_in"], ckpt["bottleneck"])
        m.load_state_dict(sd)
        models.append(m.eval())
    c = data["check"]
    return dict(zip(c["t"], autoencoder.rebuild_error(models, c["x"])))


def service_scores(app):
    model = Ensemble.load(SERVICE_MODELS / f"{app}.json")
    builder = WindowBuilder(model, windows.MAX_GAP_S)
    import csv
    scores = {}
    with open(windows.PREPARED / f"{SESSION}.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["app"] != app:
                continue
            rate = {name: (float(r[name]) if r[name] != "" else None) for name in windows.FEATURES}
            rate.update(ts=r["timestamp_utc"], reset=r["reset"] == "1")
            x = builder.add(rate)
            if x is not None:
                scores[datetime.fromisoformat(r["timestamp_utc"])] = model.score(x)
    return scores


if __name__ == "__main__":
    for app in windows.APPS:
        a, b = torch_scores(app), service_scores(app)
        common = sorted(set(a) & set(b))
        diff = max(abs(a[t] - b[t]) / max(a[t], 1e-9) for t in common)
        print(f"{app}: torch windows={len(a)} service windows={len(b)} compared={len(common)} "
              f"missing in service={len(set(a) - set(b))} max relative difference={diff:.2e}")
