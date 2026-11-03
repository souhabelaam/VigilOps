"""Anomaly detection: read rates from the queue, score them, publish anomaly events."""
import logging
import signal

from app.core import config
from app.core.health import Health, start_server
from app.repositories.publisher import QueuePublisher
from app.repositories.queue import QueueConsumer
from app.services.autoencoder import Ensemble
from app.services.detector import AppDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("detection")

running = True


def _stop(signum, frame):
    global running
    running = False  # finish the current message, then leave


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)   # docker stop
    signal.signal(signal.SIGINT, _stop)    # Ctrl+C

    health = Health(config.HEALTH_MAX_SILENCE_S)
    start_server(health, config.HEALTH_PORT)   # open the door first: Kubernetes can ask during startup

    detectors = {app: AppDetector(Ensemble.load(config.MODELS_DIR / f"{app}.json"),
                                  config.K[app], config.MAX_GAP_S)
                 for app in config.APPS}
    publisher = QueuePublisher(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                               config.RABBITMQ_USER, config.RABBITMQ_PASS, config.OUTPUT_QUEUE)
    publisher.connect()
    health.set_ready(True)   # models are loaded and the output queue is connected

    def handle(rate: dict) -> None:
        detector = detectors.get(rate["app"])
        if detector is None:
            return   # an app we have no model for
        event = detector.process(rate)
        if event:
            publisher.publish(event)
            log.warning("ANOMALY %s %s score=%s threshold=%s",
                        event["app"], event["kind"], event["score"], event["threshold"])

    consumer = QueueConsumer(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                             config.RABBITMQ_USER, config.RABBITMQ_PASS, config.INPUT_QUEUE)
    def should_run() -> bool:
        health.beat()   # the consumer asks this at least once a second, even with an empty queue
        return running

    consumer.consume(handle, should_run)
    publisher.close()
    log.info("detection stopped")


if __name__ == "__main__":
    main()
