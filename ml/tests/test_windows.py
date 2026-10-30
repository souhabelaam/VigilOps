import csv
from datetime import datetime, timedelta

import numpy as np
import pytest

import windows

T0 = datetime(2026, 10, 25, 10, 0, 0)
COLUMNS = ["app", "timestamp_utc", "cpu_pct", "req_per_s", "avg_latency_ms", "memory_mb",
           "label", "reset", "fault"]


@pytest.fixture(autouse=True)
def small_windows(monkeypatch):
    """4 rows per window and every option off, whatever a script left in the module."""
    monkeypatch.setattr(windows, "WINDOW", 4)
    for flag in ("LOG_LATENCY", "MEM_DELTA", "MEM_GROWTH", "STATS"):
        monkeypatch.setattr(windows, flag, False)


def write_session(tmp_path, monkeypatch, rows, name="s1"):
    """rows: dicts with only the fields that matter; the others get healthy defaults."""
    monkeypatch.setattr(windows, "PREPARED", tmp_path)
    with open(tmp_path / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        for r in rows:
            full = {"app": "notes-api", "cpu_pct": 1, "req_per_s": 2, "avg_latency_ms": 10,
                    "memory_mb": 50, "label": 0, "reset": 0, "fault": ""}
            full.update(r)
            w.writerow(full)
    return name


def rows(n, start=0, **extra):
    return [{"timestamp_utc": (T0 + timedelta(seconds=5 * (start + i))).isoformat(), **extra}
            for i in range(n)]


def test_empty_cell_takes_the_last_known_value():
    v = np.array([[1.0, 5.0], [np.nan, np.nan], [3.0, np.nan]])
    assert windows.fill_empty(v).tolist() == [[1.0, 5.0], [1.0, 5.0], [3.0, 5.0]]


def test_one_window_per_row_once_the_first_window_is_full(tmp_path, monkeypatch):
    s = write_session(tmp_path, monkeypatch, rows(10))
    x, y, t = windows.make_windows(s, "notes-api")
    assert x.shape == (7, 4, 4) and len(y) == 7 and len(t) == 7   # 10 - 4 + 1
    assert t[0] == T0 + timedelta(seconds=15)                     # time of the window's LAST row


def test_a_window_never_spans_a_gap(tmp_path, monkeypatch):
    # 5 rows, a 60 s hole, 5 rows: 2 windows on each side, none across the hole
    data = rows(5) + rows(5, start=17)
    x, _, _ = windows.make_windows(write_session(tmp_path, monkeypatch, data), "notes-api")
    assert len(x) == 4


def test_labels_1_2_0(tmp_path, monkeypatch):
    # rows 3 and 4 are labeled: the window ending on row 4 is 1; the window ending on row 5
    # still holds a labeled row but its last row is healthy -> 2 (ignored); later ones are 0
    data = rows(10)
    data[3]["label"] = data[4]["label"] = 1
    _, y, _ = windows.make_windows(write_session(tmp_path, monkeypatch, data), "notes-api")
    # windows end on rows 3..9
    assert y.tolist() == [1, 1, 2, 2, 2, 0, 0]


def test_crash_windows_are_skipped(tmp_path, monkeypatch):
    data = rows(10)
    data[5]["reset"] = 1                       # the windows ending on rows 5..8 hold row 5: crash windows
    x, _, t = windows.make_windows(write_session(tmp_path, monkeypatch, data), "notes-api")
    assert [(ti - T0).seconds // 5 for ti in t] == [3, 4, 9]   # the windows ending on rows 3, 4 and 9 survive


def test_only_the_asked_app_is_read(tmp_path, monkeypatch):
    data = rows(6) + [{**r, "app": "report-api"} for r in rows(6)]
    x, _, _ = windows.make_windows(write_session(tmp_path, monkeypatch, data), "report-api")
    assert len(x) == 3


def test_memory_growth_keeps_a_rise_and_ignores_a_fall(tmp_path, monkeypatch):
    monkeypatch.setattr(windows, "MEM_GROWTH", True)
    data = rows(4)
    for r, mb in zip(data, [50, 52, 49, 55]):
        r["memory_mb"] = mb
    x, _, _ = windows.make_windows(write_session(tmp_path, monkeypatch, data), "notes-api")
    assert x[0, :, windows.FEATURES.index("memory_mb")].tolist() == [0, 2, 0, 5]


def test_scaler_uses_train_statistics_and_survives_a_constant_feature():
    train = np.zeros((3, 4, 4))
    train[:, :, 0] = [[1, 2, 3, 4]] * 3          # feature 0 varies, the others are constant
    mean, std = windows.fit_scaler(train)
    assert mean[0] == 2.5 and std[1] == 1.0       # constant feature: std replaced by 1, no division by 0
    assert windows.scale(train, mean, std)[0, :, 1].tolist() == [0, 0, 0, 0]


def test_stats_mode_gives_5_numbers_per_feature(monkeypatch):
    monkeypatch.setattr(windows, "STATS", True)
    out = windows.scale(np.ones((7, 4, 4)), np.zeros(4), np.ones(4))
    assert out.shape == (7, 20)
