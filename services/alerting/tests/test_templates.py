from app.services import templates

MODEL = {"ts": "2026-10-30T10:05:00+01:00", "app": "notes-api", "kind": "model", "score": 900.0, "threshold": 2.78}
CRASH = {"ts": "2026-10-30T09:05:00+00:00", "app": "report-api", "kind": "crash", "score": None, "threshold": 2.8}


def test_model_alert_has_severity_time_in_utc_and_links():
    subject, body = templates.alert(MODEL)
    assert subject == "[ALERT] notes-api behaves abnormally"
    assert "2026-10-30 09:05:00 UTC" in body              # converted from +01:00
    assert "score 900.0 vs threshold 2.78 (324x above normal)" in body
    assert "docker compose logs notes-api" in body and "http://127.0.0.1:8001/metrics" in body


def test_crash_alert_says_restarted_and_uses_the_right_port():
    subject, body = templates.alert(CRASH)
    assert subject == "[ALERT] report-api crashed and restarted"
    assert "went back to zero" in body and "http://127.0.0.1:8002/metrics" in body


def test_unknown_app_has_no_metrics_link():
    _, body = templates.alert({**CRASH, "app": "other-api"})
    assert "docker compose logs other-api" in body and "127.0.0.1" not in body


def test_zero_threshold_does_not_divide_by_zero():
    _, body = templates.alert({**MODEL, "threshold": 0})
    assert "above normal" not in body


def test_resolved_message():
    subject, body = templates.resolved("notes-api")
    assert subject == "[RESOLVED] notes-api looks normal again" and "incident is over" in body
