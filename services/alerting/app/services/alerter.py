"""Turn a stream of anomaly events into ONE notification per incident."""
from datetime import datetime


class Alerter:
    """While an app keeps sending events it is the same incident; stay quiet.

    The detector sends an event every 5 s while an app looks broken. Without this,
    one 2-minute fault would send 24 messages. An incident ends when no event
    arrives for cooldown_s; the next event then starts a new incident.
    Time comes from the event itself (not the clock), so tests need no waiting.
    """

    def __init__(self, notifier, cooldown_s: float):
        self._notifier = notifier
        self._cooldown_s = cooldown_s
        self._last_event: dict[str, datetime] = {}   # app -> time of its latest event

    def handle(self, event: dict) -> bool:
        """Return True if this event started a new incident (and a message was sent)."""
        app, ts = event["app"], datetime.fromisoformat(event["ts"])
        last = self._last_event.get(app)
        self._last_event[app] = ts
        if last is not None and (ts - last).total_seconds() <= self._cooldown_s:
            return False   # same incident, already told
        self._notifier.send(self._message(event))
        return True

    @staticmethod
    def _message(event: dict) -> str:
        if event["kind"] == "crash":
            what = "restarted (crash detected)"
        else:
            what = f"behaves abnormally (score {event['score']} above threshold {event['threshold']})"
        return f"[ALERT] {event['app']} {what} at {event['ts']}"
