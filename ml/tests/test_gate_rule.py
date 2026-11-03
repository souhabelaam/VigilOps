"""The gate's decision rule: what it accepts and what it rejects (no data, no torch)."""
from gate_rule import F1_DROP, judge, verdict


def r(f1, false_per_h):
    return {"f1": f1, "false_alerts_per_hour": false_per_h}


def test_identical_model_passes():
    assert judge(r(0.95, 5.0), r(0.95, 5.0)) == (True, [])


def test_better_model_passes():
    assert judge(r(0.90, 8.0), r(0.97, 2.0))[0]


def test_small_f1_drop_inside_the_noise_passes():
    assert judge(r(0.95, 5.0), r(0.95 - F1_DROP + 0.01, 5.0))[0]


def test_big_f1_drop_is_rejected():
    ok, reasons = judge(r(0.95, 5.0), r(0.80, 5.0))
    assert not ok and "F1" in reasons[0]


def test_more_false_alerts_is_rejected():
    ok, reasons = judge(r(0.95, 5.0), r(0.95, 15.0))   # limit is 5 * 1.5 + 2 = 9.5
    assert not ok and "false alerts" in reasons[0]


def test_one_extra_alert_on_a_tiny_base_is_not_a_rejection():
    assert judge(r(0.95, 0.0), r(0.95, 1.5))[0]


def test_missing_false_rate_counts_as_zero():
    assert judge(r(0.95, None), r(0.95, None))[0]


def test_both_problems_are_both_reported():
    ok, reasons = judge(r(0.95, 1.0), r(0.70, 20.0))
    assert not ok and len(reasons) == 2


def test_one_bad_app_rejects_the_whole_candidate():
    ok, problems = verdict({
        "notes-api": {"current": r(0.95, 2.0), "candidate": r(0.96, 2.0)},
        "report-api": {"current": r(0.95, 2.0), "candidate": r(0.60, 2.0)},
    })
    assert not ok and list(problems) == ["report-api"]


def test_all_apps_fine_passes():
    ok, problems = verdict({"notes-api": {"current": r(0.9, 1.0), "candidate": r(0.9, 1.0)}})
    assert ok and problems == {}
