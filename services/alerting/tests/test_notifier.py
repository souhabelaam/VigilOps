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
    make().send("[ALERT] notes-api behaves abnormally (score 5.0 above threshold 2.8) at 2026-10-29T12:00:00+00:00")
    mail = FakeSMTP.sent[0]
    assert mail["To"] == "you@example.com" and mail["From"] == "me@example.com"
    assert mail["Subject"] == "[VigilOps] [ALERT] notes-api behaves abnormally (score 5.0 above threshold 2.8)"
    assert "2026-10-29T12:00:00" in mail.get_content()


def test_connection_is_encrypted_before_login():
    make().send("[ALERT] x at y")
    assert [c[0] for c in FakeSMTP.calls] == ["connect", "starttls", "login"]


def test_a_mail_failure_never_stops_alerting(caplog):
    notifier = make()
    FakeSMTP.fail = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    notifier.send("[ALERT] x at y")          # must not raise
    assert FakeSMTP.sent == [] and "email NOT sent" in caplog.text
    assert "app-password" not in caplog.text


def test_unreachable_server_is_survived(caplog):
    class Down(FakeSMTP):
        def __init__(self, *a, **k):
            raise ConnectionRefusedError("no route")
    EmailNotifier("h", 587, "u", "p", "u", "t", smtp_class=Down).send("[ALERT] x at y")
    assert "email NOT sent" in caplog.text


def test_multi_notifier_sends_to_all():
    got = []
    class Spy:
        def send(self, message): got.append(message)
    MultiNotifier(Spy(), Spy()).send("hello")
    assert got == ["hello", "hello"]
