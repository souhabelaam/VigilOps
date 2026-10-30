from datetime import datetime, timedelta

import numpy as np

import evaluate

T0 = datetime(2026, 10, 25, 10, 0, 0)


def times(n):
    return [T0 + timedelta(seconds=5 * i) for i in range(n)]


def test_threshold_is_the_99th_percentile_of_healthy_scores():
    assert evaluate.pick_threshold(np.arange(1, 101)) == np.quantile(np.arange(1, 101), 0.99)
    assert 99 < evaluate.pick_threshold(np.arange(1, 101)) < 100


def test_runs_finds_each_stretch_of_true():
    assert evaluate.runs(np.array([False, True, True, False, True])) == [(1, 2), (4, 4)]
    assert evaluate.runs(np.array([False, False])) == []


def test_perfect_detector():
    y = np.array([0, 0, 1, 1, 0, 0])
    scores = np.array([1, 1, 9, 9, 1, 1])
    r = evaluate.evaluate(scores, y, times(6), np.array(["s"] * 6), threshold=5)
    assert (r["precision"], r["recall"], r["f1"]) == (1.0, 1.0, 1.0)
    assert r["incidents"] == 1 and r["detected"] == 1 and r["mean_delay_s"] == 0.0
    assert r["false_alerts_per_hour"] == 0.0


def test_false_alarm_lowers_precision_and_counts_per_hour():
    y = np.array([0, 0, 1, 1, 0, 0])
    scores = np.array([9, 1, 9, 9, 1, 1])          # alarm on a healthy window
    r = evaluate.evaluate(scores, y, times(6), np.array(["s"] * 6), threshold=5)
    assert r["precision"] == 0.667 and r["recall"] == 1.0
    # 4 healthy windows = 20 s = 1/180 h, one false event -> 180 per hour
    assert r["false_alerts_per_hour"] == 180.0


def test_detection_delay_is_time_to_the_first_alarm_inside_the_incident():
    y = np.array([0, 1, 1, 1, 0])
    scores = np.array([1, 1, 1, 9, 1])             # first alarm 2 windows after the incident starts
    r = evaluate.evaluate(scores, y, times(5), np.array(["s"] * 5), threshold=5)
    assert r["detected"] == 1 and r["mean_delay_s"] == 10.0


def test_missed_incident_counts_as_not_detected():
    y = np.array([0, 1, 1, 0])
    r = evaluate.evaluate(np.ones(4), y, times(4), np.array(["s"] * 4), threshold=5)
    assert r["recall"] == 0.0 and r["detected"] == 0 and r["mean_delay_s"] is None


def test_label_2_is_neither_hit_nor_false_alarm():
    # label 2 = the fault just ended: an alarm there must not count as a false alarm
    y = np.array([0, 1, 2, 2, 0])
    scores = np.array([1, 9, 9, 9, 1])
    r = evaluate.evaluate(scores, y, times(5), np.array(["s"] * 5), threshold=5)
    assert r["precision"] == 1.0 and r["false_alerts_per_hour"] == 0.0
