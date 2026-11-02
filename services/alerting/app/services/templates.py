"""The wording of every notification. Each function returns (subject, body)."""
from datetime import datetime, timezone

from app.core import config


def _when(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _check_lines(app: str) -> str:
    lines = f"Check:      {config.LOG_HINT.format(app=app)}"
    port = config.APP_PORTS.get(app)
    if port:
        lines += f"\n            http://127.0.0.1:{port}/metrics"
    return lines


def alert(event: dict) -> tuple[str, str]:
    app, when = event["app"], _when(event["ts"])
    if event["kind"] == "crash":
        subject = f"[ALERT] {app} crashed and restarted"
        body = (f"App:        {app}\n"
                f"Detected:   {when}\n"
                f"Meaning:    its counters went back to zero, so the process restarted\n"
                f"{_check_lines(app)}")
    else:
        score, threshold = event["score"], event["threshold"]
        times = f" ({score / threshold:.0f}x above normal)" if threshold else ""
        subject = f"[ALERT] {app} behaves abnormally"
        body = (f"App:        {app}\n"
                f"Detected:   {when}\n"
                f"Severity:   score {score} vs threshold {threshold}{times}\n"
                f"Meaning:    its metrics no longer look like a healthy {app}\n"
                f"{_check_lines(app)}")
    return subject, body


def resolved(app: str) -> tuple[str, str]:
    subject = f"[RESOLVED] {app} looks normal again"
    body = (f"App:        {app}\n"
            f"Meaning:    no anomaly for {config.COOLDOWN_S:.0f} s, the incident is over")
    return subject, body
