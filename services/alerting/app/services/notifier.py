"""Where a notification goes. Every notifier has one method: send(message)."""
import logging
import smtplib
from email.message import EmailMessage

log = logging.getLogger("alerting")


class ConsoleNotifier:
    def send(self, message: str) -> None:
        log.warning(message)   # visible with: docker compose logs alerting


class EmailNotifier:
    """Send the message by email over SMTP with STARTTLS (works with Gmail on port 587).

    A mail server can be slow or down. That must never stop alerting, so every
    failure is logged and swallowed: the console notifier still shows the alert.
    """

    def __init__(self, host: str, port: int, user: str, password: str,
                 sender: str, recipient: str, timeout: float = 10, smtp_class=smtplib.SMTP):
        self._host, self._port, self._timeout = host, port, timeout
        self._user, self._password = user, password
        self._sender, self._recipient = sender, recipient
        self._smtp_class = smtp_class   # replaced by a fake in the tests

    def send(self, message: str) -> None:
        mail = EmailMessage()
        mail["From"], mail["To"] = self._sender, self._recipient
        mail["Subject"] = "[VigilOps] " + message.split(" at ")[0][:120]   # "[ALERT] notes-api behaves ..."
        mail.set_content(message)
        try:
            with self._smtp_class(self._host, self._port, timeout=self._timeout) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.send_message(mail)
            log.info("email sent to %s", self._recipient)
        except (OSError, smtplib.SMTPException) as error:
            # never log the password; the error text of smtplib does not contain it
            log.error("email NOT sent (%s: %s)", type(error).__name__, error)


class MultiNotifier:
    """Send the same message to several notifiers."""

    def __init__(self, *notifiers):
        self._notifiers = notifiers

    def send(self, message: str) -> None:
        for notifier in self._notifiers:
            notifier.send(message)
