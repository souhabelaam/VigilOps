"""Convert the PyTorch checkpoints in ml/models/*.pt to plain JSON for the detection service.

Usage: python ml/export_numpy.py
The service container has no PyTorch (too big for our 8 GB laptop), so it only needs
the numbers: the weights of the 5 networks, the scaler and the threshold.
"""
import json
from pathlib import Path

import torch

MODELS = Path(__file__).parent / "models"
OUT = Path(__file__).parent.parent / "services" / "anomaly-detection" / "models"

KEEP = ["app", "window", "log_latency", "stats", "mem_delta", "features",
        "n_in", "hidden", "bottleneck", "mean", "std", "threshold"]

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for path in sorted(MODELS.glob("*.pt")):
        ckpt = torch.load(path)
        data = {key: ckpt[key] for key in KEEP}
        data["networks"] = [{name: tensor.tolist() for name, tensor in sd.items()}
                            for sd in ckpt["state_dicts"]]
        (OUT / f"{ckpt['app']}.json").write_text(json.dumps(data))
        print(f"{path.name} -> {ckpt['app']}.json  ({len(data['networks'])} networks)")
