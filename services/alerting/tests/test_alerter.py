from datetime import datetime, timedelta, timezone

from app.services.alerter import Alerter

T0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def event(second, app="notes-api", kind="model"):
    return {"ts": (T0 + timedelta(seconds=second)).isoformat(), "app": app, "kind": kind,
            "score": 5.0 if kind == "model" else None, "threshold": 2.8}


def test_first_event_sends_one_message():
    notifier = FakeNotifier()
    assert Alerter(notifier, 120).handle(event(0)) is True
    assert len(notifier.sent) == 1 and "notes-api" in notifier.sent[0] and "abnormally" in notifier.sent[0]


def test_events_every_5_seconds_are_one_incident():
    notifier = FakeNotifier()
    alerter = Alerter(notifier, 120)
    for i in range(24):                       # 2 minutes of continuous events
        alerter.handle(event(5 * i))
    assert len(notifier.sent) == 1


def test_quiet_period_ends_the_incident():
    notifier = FakeNotifier()
    alerter = Alerter(notifier, 120)
    alerter.handle(event(0))
    alerter.handle(event(5))
    alerter.handle(event(300))                # 295 s of silence: a new incident
    assert len(notifier.sent) == 2


def test_each_app_has_its_own_incident():
    notifier = FakeNotifier()
    alerter = Alerter(notifier, 120)
    alerter.handle(event(0, "notes-api"))
    alerter.handle(event(1, "report-api"))
    assert len(notifier.sent) == 2


def test_crash_message_says_restarted():
    notifier = FakeNotifier()
    Alerter(notifier, 120).handle(event(0, kind="crash"))
    assert "restarted" in notifier.sent[0]
