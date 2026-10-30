"""The detection service (plain numpy) must give the same scores as the PyTorch models.

This is the guard for ml/export_numpy.py: if someone retrains and forgets to export, or the export
drifts from the checkpoint, this test fails. It needs torch, so CI runs it as its own job.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "services" / "anomaly-detection"))

import autoencoder                                  # noqa: E402  (ml/autoencoder.py, torch)
from app.services.autoencoder import Ensemble       # noqa: E402  (the service, numpy)

SERVICE_MODELS = ROOT / "services" / "anomaly-detection" / "models"
APPS = ["notes-api", "report-api"]


def torch_models(ckpt):
    models = []
    for state in ckpt["state_dicts"]:
        m = autoencoder.AutoEncoder(ckpt["n_in"], ckpt["bottleneck"])
        m.load_state_dict(state)
        models.append(m.eval())
    return models


@pytest.mark.parametrize("app", APPS)
def test_the_exported_json_matches_the_checkpoint(app):
    ckpt = torch.load(autoencoder.MODELS / f"{app}.pt")
    exported = json.loads((SERVICE_MODELS / f"{app}.json").read_text())
    for key in ["window", "log_latency", "stats", "mem_delta", "mem_growth", "n_in", "bottleneck"]:
        assert exported[key] == ckpt[key], key
    assert exported["threshold"] == pytest.approx(ckpt["threshold"])
    assert exported["mean"] == pytest.approx(ckpt["mean"])
    assert exported["std"] == pytest.approx(ckpt["std"])


@pytest.mark.parametrize("app", APPS)
def test_numpy_scores_equal_torch_scores(app):
    ckpt = torch.load(autoencoder.MODELS / f"{app}.pt")
    rng = np.random.default_rng(0)
    # healthy-looking inputs and very unusual ones (x10): both must agree
    x = np.concatenate([rng.normal(size=(40, ckpt["n_in"])), 10 * rng.normal(size=(10, ckpt["n_in"]))])
    expected = autoencoder.rebuild_error(torch_models(ckpt), x)
    service = Ensemble.load(SERVICE_MODELS / f"{app}.json")
    actual = np.array([service.score(row) for row in x])
    np.testing.assert_allclose(actual, expected, rtol=1e-4)
