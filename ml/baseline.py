"""Baseline detector: IsolationForest from scikit-learn, one per app.

Usage: python ml/baseline.py
Trains on healthy windows only, picks the threshold on normal-3, grades on faulty-*.
"""
from sklearn.ensemble import IsolationForest

import windows
from evaluate import evaluate, pick_threshold


def flat(x):
    return x.reshape(len(x), -1)  # 12 x 4 window -> 48 numbers


def run(app):
    data = windows.build(app)
    model = IsolationForest(n_estimators=100, random_state=0)
    model.fit(flat(data["train"]["x"]))
    score = lambda part: -model.score_samples(flat(data[part]["x"]))  # higher = odder
    threshold = pick_threshold(score("threshold"))
    t = data["test"]
    return evaluate(score("test"), t["y"], t["t"], t["session"], threshold)


if __name__ == "__main__":
    for app in windows.APPS:
        print(app, run(app))
