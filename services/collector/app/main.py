"""Collector: every few seconds, read each app's /metrics and publish the raw numbers."""
import logging
import signal
import time

from app.core import config
from app.core.health import Health, start_server
from app.repositories.queue import QueuePublisher
from app.services.scraper import scrape

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("collector")

running = True


def _stop(signum, frame):
    global running
    running = False  # finish the current round, then leave the loop


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)   # docker stop
    signal.signal(signal.SIGINT, _stop)    # Ctrl+C

    health = Health(config.HEALTH_MAX_SILENCE_S)
    start_server(health, config.HEALTH_PORT)   # open the door first: Kubernetes can ask during startup

    queue = QueuePublisher(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                           config.RABBITMQ_USER, config.RABBITMQ_PASS, config.QUEUE_NAME)
    queue.connect()
    health.set_ready(True)   # only now can we really publish

    next_tick = time.monotonic()
    while running:
        for app, url in config.TARGETS.items():
            sample = scrape(app, url, config.SCRAPE_TIMEOUT_S)
            queue.publish(sample.to_dict())
            log.info("%s up=%s requests=%.0f", app, sample.up, sample.requests_total)
        health.beat()

        # wait for the next tick on a fixed schedule so the 5 s spacing does not drift
        next_tick += config.SCRAPE_INTERVAL_S
        while running and time.monotonic() < next_tick:
            health.beat()
            time.sleep(0.2)

    queue.close()
    log.info("collector stopped")


if __name__ == "__main__":
    main()
