"""Turn prepared rate tables into scaled windows for the models.

Usage: python ml/windows.py   (prints a summary of every split)

One model per app: notes-api and report-api behave very differently,
so each app gets its own windows and its own scaler.
"""
import csv
from pathlib import Path

import numpy as np

PREPARED = Path(__file__).parent / "data" / "prepared"
FEATURES = ["cpu_pct", "req_per_s", "avg_latency_ms", "memory_mb"]
APPS = ["notes-api", "report-api"]
WINDOW = 12      # 12 rows x 5 s = 60 s of history
LOG_LATENCY = False  # log1p on latency: it is heavy-tailed (rare big spikes)
MEM_DELTA = False    # memory as change since the window start, not absolute level
STATS = False        # describe each window by mean/std/min/max/trend instead of raw rows
MAX_GAP_S = 6.0  # same rule as prepare_data.py: never join rows across a gap

TRAIN = ["normal-1", "normal-2", "normal-4"]
THRESHOLD = ["normal-3"]
TEST = ["faulty-1", "faulty-2", "faulty-3", "faulty-4", "faulty-5", "faulty-6"]


def load_rows(session, app):
    """Rows of one app in one session: (times, values[n, 4], labels, resets)."""
    from datetime import datetime
    times, values, labels, resets, crash = [], [], [], [], []
    with open(PREPARED / f"{session}.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["app"] != app:
                continue
            times.append(datetime.fromisoformat(r["timestamp_utc"]))
            # empty cell -> nan, filled later
            values.append([float(r[c]) if r[c] != "" else np.nan for c in FEATURES])
            labels.append(int(r["label"]))
            resets.append(int(r["reset"]))
            crash.append(int(r["fault"] == "crash"))
    values = np.array(values, dtype=float)
    return times, values, np.array(labels), np.array(resets), np.array(crash)


def fill_empty(values):
    """Carry the last known value forward (e.g. latency when no request came)."""
    values = values.copy()
    for j in range(values.shape[1]):
        last = np.nan
        for i in range(values.shape[0]):
            if np.isnan(values[i, j]):
                values[i, j] = last
            else:
                last = values[i, j]
    return values


def make_windows(session, app):
    """Return windows[n, WINDOW, 4] (unscaled), window labels[n], times[n].

    A window is only built from rows that follow each other without a gap.
    Crash windows are skipped (a rule handles crashes). Its label is 1 if its
    LAST row is labeled, 2 if only earlier rows are (the fault just ended), else 0;
    its time is the time of its last row (the moment the model could alarm).
    """
    times, values, labels, resets, crash = load_rows(session, app)
    values = fill_empty(values)
    if LOG_LATENCY:
        values[:, FEATURES.index("avg_latency_ms")] = np.log1p(values[:, FEATURES.index("avg_latency_ms")])
    # a reset row has no valid rates (nan, never filled at the very start): keep
    # it as a crash marker, with the previous values carried forward by fill_empty
    wins, wlabels, wtimes = [], [], []
    start = 0
    for i in range(1, len(times) + 1):
        broken = i == len(times) or (times[i] - times[i - 1]).total_seconds() > MAX_GAP_S
        if not broken:
            continue
        seg = slice(start, i)  # one gap-free stretch
        v, lab, res, t, cr = values[seg], labels[seg], resets[seg], times[seg], crash[seg]
        for k in range(WINDOW, len(v) + 1):
            w = v[k - WINDOW:k]
            if np.isnan(w).any():
                continue  # stretch begins with an empty cell: skip
            if cr[k - 1] or res[k - WINDOW:k].any():
                continue  # crash: the app is down or already restarted, a rule handles it
            wins.append(w)
            if lab[k - 1] == 1:
                wlabels.append(1)
            elif lab[k - WINDOW:k - 1].any():
                wlabels.append(2)  # fault just ended but the window still holds it: ignored
            else:
                wlabels.append(0)
            wtimes.append(t[k - 1])
        start = i
    if not wins:
        return np.empty((0, WINDOW, len(FEATURES))), np.array([], dtype=int), []
    wins = np.array(wins)
    if MEM_DELTA:
        # memory level differs between runs (container age), only its change matters
        m = FEATURES.index("memory_mb")
        wins[:, :, m] -= wins[:, :1, m]
    return wins, np.array(wlabels), wtimes


def fit_scaler(windows):
    """Mean and std per feature, from TRAIN windows only."""
    flat = windows.reshape(-1, windows.shape[-1])
    mean, std = flat.mean(axis=0), flat.std(axis=0)
    std[std == 0] = 1.0  # a constant feature must not divide by zero
    return mean, std


def scale(windows, mean, std):
    scaled = (windows - mean) / std
    if not STATS:
        return scaled
    # per feature: mean, spread, min, max, and last minus first (trend) -> 5 x 4 numbers
    return np.concatenate([scaled.mean(axis=1), scaled.std(axis=1), scaled.min(axis=1),
                           scaled.max(axis=1), scaled[:, -1] - scaled[:, 0]], axis=1)


def build(app, parts=None):
    """Everything the models need for one app, scaled with the train scaler.

    parts maps a name to a list of sessions; the default is the usual split.
    """
    parts = parts or {"train": TRAIN, "threshold": THRESHOLD, "test": TEST}
    def stack(sessions):
        parts = [make_windows(s, app) for s in sessions]
        return (np.concatenate([p[0] for p in parts]),
                np.concatenate([p[1] for p in parts]),
                [t for p in parts for t in p[2]],
                np.concatenate([[s] * len(p[1]) for s, p in zip(sessions, parts)]))

    x_tr, y_tr, t_tr, s_tr = stack(parts["train"])
    mean, std = fit_scaler(x_tr)
    out = {"mean": mean, "std": std}
    for name, sessions in parts.items():
        x, y, t, s = stack(sessions)
        out[name] = {"x": scale(x, mean, std), "y": y, "t": t, "session": s}
    return out


if __name__ == "__main__":
    for app in APPS:
        data = build(app)
        print(f"== {app}  scaler mean={np.round(data['mean'], 2)} std={np.round(data['std'], 2)}")
        for name in ["train", "threshold", "test"]:
            d = data[name]
            print(f"  {name:9} windows={len(d['y']):5} anomalous={int((d['y'] == 1).sum()):4} "
                  f"shape={d['x'].shape}")
