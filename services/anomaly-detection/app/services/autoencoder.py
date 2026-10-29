"""The trained autoencoders, run with plain numpy (the same maths as ml/autoencoder.py)."""
import json
from pathlib import Path

import numpy as np


class Network:
    """One small network: squeeze the input to a few numbers, then rebuild it."""

    def __init__(self, weights: dict):
        w = {name: np.array(values, dtype=np.float32) for name, values in weights.items()}
        self._layers = [(w["encoder.0.weight"], w["encoder.0.bias"], True),
                        (w["encoder.2.weight"], w["encoder.2.bias"], False),
                        (w["decoder.0.weight"], w["decoder.0.bias"], True),
                        (w["decoder.2.weight"], w["decoder.2.bias"], False)]

    def rebuild(self, x: np.ndarray) -> np.ndarray:
        for weight, bias, relu in self._layers:
            x = x @ weight.T + bias
            if relu:
                x = np.maximum(x, 0)
        return x


class Ensemble:
    """The 5 networks of one app plus everything needed to prepare their input."""

    def __init__(self, data: dict):
        self.app = data["app"]
        self.window = data["window"]
        self.log_latency = data["log_latency"]
        self.stats = data["stats"]
        self.mem_delta = data["mem_delta"]
        self.features = data["features"]
        self.mean = np.array(data["mean"])
        self.std = np.array(data["std"])
        self.threshold = data["threshold"]
        self._networks = [Network(n) for n in data["networks"]]

    @classmethod
    def load(cls, path: Path) -> "Ensemble":
        return cls(json.loads(Path(path).read_text()))

    def score(self, x: np.ndarray) -> float:
        """Mean squared rebuild error of one prepared input, averaged over the networks."""
        x = x.astype(np.float32)
        return float(sum(((n.rebuild(x) - x) ** 2).mean() for n in self._networks) / len(self._networks))
