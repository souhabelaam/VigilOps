"""Alerting: read anomaly events from the queue, send one notification per incident."""
import logging
import signal

from app.core import config
from app.core.health import Health, start_server
from app.repositories.queue import QueueConsumer
from app.services.alerter import Alerter
from app.services.notifier import ConsoleNotifier, EmailNotifier, MultiNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("alerting")

running = True


def _stop(signum, frame):
    global running
    running = False  # finish the current message, then leave


def build_notifier():
    """Console always; plus email when NOTIFIER=email and the mail settings are complete."""
    console = ConsoleNotifier()
    if config.NOTIFIER != "email":
        return console
    if not (config.SMTP_USER and config.SMTP_PASSWORD and config.MAIL_TO):
        log.error("NOTIFIER=email but SMTP_USER, SMTP_PASSWORD or MAIL_TO is empty: console only")
        return console
    log.info("email alerts go to %s", config.MAIL_TO)
    email = EmailNotifier(config.SMTP_HOST, config.SMTP_PORT, config.SMTP_USER,
                          config.SMTP_PASSWORD, config.SMTP_USER, config.MAIL_TO)
    return MultiNotifier(console, email)


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)   # docker stop
    signal.signal(signal.SIGINT, _stop)    # Ctrl+C

    health = Health(config.HEALTH_MAX_SILENCE_S)
    start_server(health, config.HEALTH_PORT)   # open the door first: Kubernetes can ask during startup

    alerter = Alerter(build_notifier(), config.COOLDOWN_S)
    consumer = QueueConsumer(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                             config.RABBITMQ_USER, config.RABBITMQ_PASS, config.QUEUE_NAME)
    health.set_ready(True)   # notifier built; the consumer connects (and retries) from here on

    def should_run() -> bool:
        health.beat()   # the consumer asks this at least once a second, even with an empty queue
        return running

    consumer.consume(alerter.handle, should_run, on_idle=alerter.check)
    log.info("alerting stopped")


if __name__ == "__main__":
    main()
