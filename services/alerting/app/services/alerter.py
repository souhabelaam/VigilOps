"""Turn a stream of anomaly events into ONE notification per incident, and tell when it is over."""
import time
from datetime import datetime

from app.services import templates


class Alerter:
    """While an app keeps sending events it is the same incident; stay quiet.

    The detector sends an event every 5 s while an app looks broken. Without this,
    one 2-minute fault would send 24 messages. An incident ends when no event
    arrives for cooldown_s; the next event then starts a new incident.
    Crashes and model alarms count separately: a model alarm that never stops
    (a false alarm stuck on) must not hide a real crash.

    Two clocks, on purpose:
    - handle() compares the TIMES INSIDE the events (so tests need no waiting);
    - check() measures real silence with clock() (nothing arrives when all is quiet,
      so there is no event time to compare with).
    """

    def __init__(self, notifier, cooldown_s: float, clock=time.monotonic):
        self._notifier = notifier
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._last_event: dict[tuple[str, str], datetime] = {}   # (app, kind) -> time of its latest event
        self._last_arrival: dict[tuple[str, str], float] = {}    # (app, kind) -> clock() when it arrived

    def handle(self, event: dict) -> bool:
        """Return True if this event started a new incident (and a message was sent)."""
        app, ts = event["app"], datetime.fromisoformat(event["ts"])
        key = (app, event["kind"])
        last = self._last_event.get(key)
        self._last_event[key] = ts
        self._last_arrival[key] = self._clock()
        if last is not None and (ts - last).total_seconds() <= self._cooldown_s:
            return False   # same incident, already told
        self._notifier.send(*templates.alert(event))
        return True

    def check(self) -> list[str]:
        """Call regularly. Close incidents that were silent for cooldown_s; return the subjects sent."""
        now, sent = self._clock(), []
        for key, arrived in list(self._last_arrival.items()):
            if now - arrived <= self._cooldown_s:
                continue
            del self._last_arrival[key], self._last_event[key]   # the next event is a NEW incident
            app, kind = key
            if kind == "model":   # a crash is a single moment, there is nothing to resolve
                subject, body = templates.resolved(app)
                self._notifier.send(subject, body)
                sent.append(subject)
        return sent
