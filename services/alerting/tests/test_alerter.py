from datetime import datetime, timedelta, timezone

from app.services.alerter import Alerter

T0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, subject, body):
        self.sent.append(subject)   # the subject is enough here, test_templates checks the bodies


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


def test_new_fault_90_seconds_after_the_last_event_is_announced():
    # live test: a second fault started 91 s after the first one's last event and was never announced
    notifier = FakeNotifier()
    alerter = Alerter(notifier, 60)
    alerter.handle(event(0))
    alerter.handle(event(91))
    assert len(notifier.sent) == 2


def test_crash_is_announced_even_during_a_model_alarm():
    # live test: notes-api had a stuck false alarm, and the real crash was never announced
    notifier = FakeNotifier()
    alerter = Alerter(notifier, 60)
    alerter.handle(event(0))
    alerter.handle(event(5))
    alerter.handle(event(10, kind="crash"))
    assert len(notifier.sent) == 2 and "restarted" in notifier.sent[1]


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_incident_is_resolved_after_the_quiet_period():
    notifier, clock = FakeNotifier(), FakeClock()
    alerter = Alerter(notifier, 60, clock)
    alerter.handle(event(0))
    clock.now = 30
    assert alerter.check() == []                      # only 30 s of silence
    clock.now = 61
    assert len(alerter.check()) == 1 and "[RESOLVED] notes-api" in notifier.sent[-1]
    assert alerter.check() == []                      # told once, not again


def test_events_keep_the_incident_open():
    notifier, clock = FakeNotifier(), FakeClock()
    alerter = Alerter(notifier, 60, clock)
    for i in range(20):
        clock.now = 5 * i
        alerter.handle(event(5 * i))
        assert alerter.check() == []
    assert len(notifier.sent) == 1                    # one alert, no resolved


def test_after_resolved_the_next_fault_alerts_again():
    notifier, clock = FakeNotifier(), FakeClock()
    alerter = Alerter(notifier, 60, clock)
    alerter.handle(event(0))
    clock.now = 100
    alerter.check()
    alerter.handle(event(100))
    assert [m.split()[0] for m in notifier.sent] == ["[ALERT]", "[RESOLVED]", "[ALERT]"]


def test_a_crash_has_no_resolved_message():
    notifier, clock = FakeNotifier(), FakeClock()
    alerter = Alerter(notifier, 60, clock)
    alerter.handle(event(0, kind="crash"))
    clock.now = 100
    assert alerter.check() == [] and len(notifier.sent) == 1
