"""How stable is the autoencoder score? Repeat the whole run with different seeds.

Usage: python ml/seed_spread.py
Each repeat trains a new ensemble of 5 networks (seeds 0-4, 5-9, ...), picks the
threshold on normal-3 and grades on the final sessions. Nothing is exported, so
the saved models in ml/models/ are not touched. Settings are NOT changed.
"""
from statistics import mean, stdev

import autoencoder
import windows

REPEATS = 5

if __name__ == "__main__":
    for app in windows.APPS:
        rows = [autoencoder.run(app, export=False, seed0=r * autoencoder.SEEDS)
                for r in range(REPEATS)]
        print(f"\n{app}: {REPEATS} independent ensembles of {autoencoder.SEEDS} networks")
        for r, res in enumerate(rows):
            print(f"  repeat {r}: {res}")
        for key in ("precision", "recall", "f1", "false_alerts_per_hour"):
            vals = [res[key] for res in rows]
            print(f"  {key:22} mean {mean(vals):.3f}  std {stdev(vals):.3f}  "
                  f"min {min(vals):.3f}  max {max(vals):.3f}")
