"""PyTorch autoencoder detector, one per app: train, grade, export.

Usage: python ml/autoencoder.py
The network squeezes a window into a few numbers and rebuilds it. It only ever
sees healthy windows, so it rebuilds unusual windows badly: that error is the score.
Settings per app were chosen by ml/tune.py on faulty-1+6 (not on the final test).
Exports ml/models/<app>.pt (weights, scaler, threshold) for the detection service.
"""
from pathlib import Path

import mlflow
import torch
from torch import nn

import baseline
import windows
from evaluate import evaluate, pick_threshold

EPOCHS = 150
LR = 1e-3
HIDDEN = 24
SEEDS = 5  # the score is the average of 5 networks trained from different seeds
MODELS = Path(__file__).parent / "models"
# chosen by tune.py; k (alarms in a row) stayed 1 for both apps.
# mem_growth replaced absolute / delta memory after ml/robustness.py (live false alarms)
SETTINGS = {
    "notes-api": {"window": 24, "bottleneck": 3, "log_latency": True, "stats": True,
                  "mem_delta": False, "mem_growth": True, "quantile": 0.999},
    "report-api": {"window": 24, "bottleneck": 6, "log_latency": False, "stats": True,
                   "mem_delta": False, "mem_growth": True, "quantile": 0.99},
}
# final test = sessions the tuning never used
PARTS = {"train": windows.TRAIN, "threshold": windows.THRESHOLD,
         "final": ["faulty-2", "faulty-3", "faulty-4", "faulty-5"]}


class AutoEncoder(nn.Module):
    def __init__(self, n_in, bottleneck):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(n_in, HIDDEN), nn.ReLU(),
                                     nn.Linear(HIDDEN, bottleneck))
        self.decoder = nn.Sequential(nn.Linear(bottleneck, HIDDEN), nn.ReLU(),
                                     nn.Linear(HIDDEN, n_in))

    def forward(self, x):
        return self.decoder(self.encoder(x))


def tensor(x):
    return torch.tensor(x.reshape(len(x), -1), dtype=torch.float32)


def train_one(x_train, bottleneck, seed):
    torch.manual_seed(seed)
    model = AutoEncoder(x_train.shape[1], bottleneck)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = ((model(x_train) - x_train) ** 2).mean()
        loss.backward()
        opt.step()
    return model


def rebuild_error(models, x):
    """Mean squared rebuild error per window, averaged over the networks."""
    x = tensor(x)
    with torch.no_grad():
        return sum(((m(x) - x) ** 2).mean(dim=1).numpy() for m in models) / len(models)


def run(app, export=True, seed0=0):
    cfg = SETTINGS[app]
    windows.WINDOW, windows.LOG_LATENCY = cfg["window"], cfg["log_latency"]
    windows.STATS, windows.MEM_DELTA = cfg["stats"], cfg["mem_delta"]
    windows.MEM_GROWTH = cfg["mem_growth"]
    data = windows.build(app, PARTS)
    x_train = tensor(data["train"]["x"])
    models = [train_one(x_train, cfg["bottleneck"], s) for s in range(seed0, seed0 + SEEDS)]

    threshold = pick_threshold(rebuild_error(models, data["threshold"]["x"]), cfg["quantile"])
    f = data["final"]
    result = evaluate(rebuild_error(models, f["x"]), f["y"], f["t"], f["session"], threshold)
    result["threshold"] = round(threshold, 4)

    if export:
        MODELS.mkdir(exist_ok=True)
        torch.save({"app": app, "window": cfg["window"], "log_latency": cfg["log_latency"],
                    "stats": cfg["stats"], "mem_delta": cfg["mem_delta"],
                    "mem_growth": cfg["mem_growth"], "features": windows.FEATURES,
                    "n_in": x_train.shape[1], "hidden": HIDDEN, "bottleneck": cfg["bottleneck"],
                    "state_dicts": [m.state_dict() for m in models],
                    "mean": data["mean"].tolist(), "std": data["std"].tolist(),
                    "threshold": threshold}, MODELS / f"{app}.pt")
    return result


def run_baseline(app):
    """The baseline graded on the same final sessions, default settings."""
    windows.WINDOW, windows.LOG_LATENCY, windows.STATS, windows.MEM_DELTA = 12, False, False, False
    windows.MEM_GROWTH = False
    data = windows.build(app, PARTS)
    from sklearn.ensemble import IsolationForest
    flat = lambda x: x.reshape(len(x), -1)
    m = IsolationForest(n_estimators=100, random_state=0).fit(flat(data["train"]["x"]))
    thr = pick_threshold(-m.score_samples(flat(data["threshold"]["x"])))
    f = data["final"]
    return evaluate(-m.score_samples(flat(f["x"])), f["y"], f["t"], f["session"], thr)


if __name__ == "__main__":
    mlflow.set_tracking_uri(f"sqlite:///{(Path(__file__).parent / 'mlflow.db').as_posix()}")
    mlflow.set_experiment("vigilops-anomaly")
    for app in windows.APPS:
        for name, fn in [("isolation_forest", run_baseline), ("autoencoder", run)]:
            with mlflow.start_run(run_name=f"{name}-{app}"):
                params = {"model": name, "app": app, "final_sessions": "faulty-2..5"}
                if name == "autoencoder":
                    params.update(SETTINGS[app])
                mlflow.log_params(params)
                res = fn(app)
                mlflow.log_metrics({k: v for k, v in res.items() if v is not None})
                print(f"{app:10} {name:17} {res}")
