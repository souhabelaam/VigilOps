"""Retrain-and-compare gate: retrain the models, take the SAME exam as the current ones, compare.

Usage (from ml/):  python gate.py [--extra-train normal-5,normal-7] [--epochs 150] [--report gate-report.json]
                   [--keep-dir candidate-models]   (copies the candidate .pt files there when accepted)
Exit code 0 = candidate accepted, 1 = rejected (the pipeline stops, the current model stays).

  current   = the frozen models in ml/models/<app>.pt (never modified here)
  candidate = the same recipe (autoencoder.SETTINGS, 5 seeds) trained again on the DVC-tracked data,
              written to a temporary folder
  exam      = sessions that never took part in training, tuning or the threshold: faulty-2..5 + faulty-7.
              Each model uses ITS OWN scaler and threshold (they come from its own training data).
The rule that decides "worse" lives in gate_rule.py and was fixed before any result was seen.
--extra-train and --epochs exist to build a different candidate on purpose (proof runs).
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

import autoencoder
import windows
from evaluate import evaluate
from gate_rule import F1_DROP, FALSE_FACTOR, FALSE_SLACK, verdict

EXAM = ["faulty-2", "faulty-3", "faulty-4", "faulty-5", "faulty-7"]


def score_checkpoint(path, app):
    """Grade one exported model on the exam. Same steps as holdout.py, other sessions."""
    ckpt = torch.load(path)
    windows.WINDOW, windows.LOG_LATENCY = ckpt["window"], ckpt["log_latency"]
    windows.STATS, windows.MEM_DELTA = ckpt["stats"], ckpt["mem_delta"]
    windows.MEM_GROWTH = ckpt.get("mem_growth", False)
    train = ckpt.get("train_sessions", windows.TRAIN)   # models exported before the gate lack the key
    data = windows.build(app, {"train": train, "exam": EXAM})
    # the rebuilt scaler must equal the saved one, or the inputs are not the same
    assert np.allclose(data["mean"], ckpt["mean"]) and np.allclose(data["std"], ckpt["std"])
    models = []
    for sd in ckpt["state_dicts"]:
        m = autoencoder.AutoEncoder(ckpt["n_in"], ckpt["bottleneck"])
        m.load_state_dict(sd)
        models.append(m.eval())
    e = data["exam"]
    res = evaluate(autoencoder.rebuild_error(models, e["x"]), e["y"], e["t"], e["session"],
                   ckpt["threshold"])
    res["threshold"] = round(float(ckpt["threshold"]), 4)
    res["trained_on"] = train
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-train", default="", help="comma list of sessions added to the training data")
    ap.add_argument("--epochs", type=int, default=autoencoder.EPOCHS)
    ap.add_argument("--report", default="gate-report.json")
    ap.add_argument("--keep-dir", default="", help="copy the candidate models here when accepted")
    args = ap.parse_args()

    extra = [s for s in args.extra_train.split(",") if s]
    autoencoder.PARTS["train"] = windows.TRAIN + extra
    autoencoder.EPOCHS = args.epochs
    print(f"candidate: trained on {autoencoder.PARTS['train']}, {args.epochs} epochs, "
          f"{autoencoder.SEEDS} seeds\nexam     : {EXAM}\n")

    per_app = {}
    with tempfile.TemporaryDirectory() as tmp:
        for app in windows.APPS:
            autoencoder.run(app, export=True, out=Path(tmp))        # trains and writes candidate
            per_app[app] = {"current": score_checkpoint(autoencoder.MODELS / f"{app}.pt", app),
                            "candidate": score_checkpoint(Path(tmp) / f"{app}.pt", app)}
        ok, problems = verdict(per_app)
        if ok and args.keep_dir:   # the temporary folder disappears when this block ends
            shutil.copytree(tmp, args.keep_dir, dirs_exist_ok=True)
    print(f"{'app':11} {'model':10} {'F1':>6} {'precision':>9} {'recall':>7} {'false/h':>8} {'delay s':>8}")
    for app, r in per_app.items():
        for name in ("current", "candidate"):
            x = r[name]
            print(f"{app:11} {name:10} {x['f1']:6} {x['precision']:9} {x['recall']:7} "
                  f"{x['false_alerts_per_hour']!s:>8} {x['mean_delay_s']!s:>8}")
    print(f"\nrule: F1 may drop by at most {F1_DROP}; false alerts/h may grow to "
          f"current x {FALSE_FACTOR} + {FALSE_SLACK}")
    if ok:
        print("GATE: ACCEPTED - the candidate is not worse than the current models")
    else:
        print("GATE: REJECTED - the current models stay")
        for app, reasons in problems.items():
            for why in reasons:
                print(f"  {app}: {why}")

    Path(args.report).write_text(json.dumps(
        {"accepted": ok, "problems": problems, "exam": EXAM, "results": per_app}, indent=2, default=str))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
