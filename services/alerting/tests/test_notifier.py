import smtplib

from app.services.notifier import EmailNotifier, MultiNotifier


class FakeSMTP:
    """Stands in for smtplib.SMTP and remembers what it was asked to do."""
    sent, calls, fail = [], [], None

    def __init__(self, host, port, timeout):
        FakeSMTP.calls.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        FakeSMTP.calls.append(("starttls",))

    def login(self, user, password):
        if FakeSMTP.fail:
            raise FakeSMTP.fail
        FakeSMTP.calls.append(("login", user))

    def send_message(self, mail):
        FakeSMTP.sent.append(mail)


def make():
    FakeSMTP.sent, FakeSMTP.calls, FakeSMTP.fail = [], [], None
    return EmailNotifier("smtp.example.com", 587, "me@example.com", "app-password",
                         "me@example.com", "you@example.com", smtp_class=FakeSMTP)


def test_email_has_subject_and_body():
    make().send("[ALERT] notes-api behaves abnormally", "App:        notes-api\nDetected:   2026-10-29 12:00:00 UTC")
    mail = FakeSMTP.sent[0]
    assert mail["To"] == "you@example.com" and mail["From"] == "me@example.com"
    assert mail["Subject"] == "[VigilOps] [ALERT] notes-api behaves abnormally"
    assert "2026-10-29 12:00:00 UTC" in mail.get_content()


def test_connection_is_encrypted_before_login():
    make().send("[ALERT] x", "body")
    assert [c[0] for c in FakeSMTP.calls] == ["connect", "starttls", "login"]


def test_a_mail_failure_never_stops_alerting(caplog):
    notifier = make()
    FakeSMTP.fail = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    notifier.send("[ALERT] x", "body")          # must not raise
    assert FakeSMTP.sent == [] and "email NOT sent" in caplog.text
    assert "app-password" not in caplog.text


def test_unreachable_server_is_survived(caplog):
    class Down(FakeSMTP):
        def __init__(self, *a, **k):
            raise ConnectionRefusedError("no route")
    EmailNotifier("h", 587, "u", "p", "u", "t", smtp_class=Down).send("[ALERT] x", "body")
    assert "email NOT sent" in caplog.text


def test_multi_notifier_sends_to_all():
    got = []
    class Spy:
        def send(self, subject, body): got.append((subject, body))
    MultiNotifier(Spy(), Spy()).send("hello", "world")
    assert got == [("hello", "world")] * 2
