"""Alerting: read anomaly events from the queue, send one notification per incident."""
import logging
import signal

from app.core import config
from app.repositories.queue import QueueConsumer
from app.services.alerter import Alerter
from app.services.notifier import ConsoleNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("alerting")

running = True


def _stop(signum, frame):
    global running
    running = False  # finish the current message, then leave


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)   # docker stop
    signal.signal(signal.SIGINT, _stop)    # Ctrl+C

    alerter = Alerter(ConsoleNotifier(), config.COOLDOWN_S)
    consumer = QueueConsumer(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                             config.RABBITMQ_USER, config.RABBITMQ_PASS, config.QUEUE_NAME)
    consumer.consume(alerter.handle, lambda: running)
    log.info("alerting stopped")


if __name__ == "__main__":
    main()
