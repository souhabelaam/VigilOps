"""Ingestion: read raw samples from the queue, compute rates, store them in PostgreSQL
and publish them to the rates queue for anomaly detection."""
import logging
import signal

from app.core import config
from app.core.health import Health, start_server
from app.repositories.database import RateRepository
from app.repositories.publisher import QueuePublisher
from app.repositories.queue import QueueConsumer
from app.schemas.sample import Sample
from app.services.rates import RateCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion")

running = True


def _stop(signum, frame):
    global running
    running = False  # finish the current message, then leave


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)   # docker stop
    signal.signal(signal.SIGINT, _stop)    # Ctrl+C

    health = Health(config.HEALTH_MAX_SILENCE_S)
    start_server(health, config.HEALTH_PORT)   # open the door first: Kubernetes can ask during startup

    conninfo = (f"host={config.POSTGRES_HOST} port={config.POSTGRES_PORT} dbname={config.POSTGRES_DB} "
                f"user={config.POSTGRES_USER} password={config.POSTGRES_PASSWORD}")
    repository = RateRepository(conninfo)
    repository.connect()
    calculator = RateCalculator(config.MAX_GAP_S)
    publisher = QueuePublisher(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                               config.RABBITMQ_USER, config.RABBITMQ_PASS, config.RATES_QUEUE)
    publisher.connect()
    health.set_ready(True)   # database and output queue are both connected

    def handle(message: dict) -> None:
        rate = calculator.process(Sample.from_message(message))
        if rate is None:
            return
        repository.save(rate)
        publisher.publish(rate.to_message())
        log.info("%s cpu=%s%% req/s=%s reset=%s", rate.app, rate.cpu_pct, rate.req_per_s, rate.reset)

    consumer = QueueConsumer(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                             config.RABBITMQ_USER, config.RABBITMQ_PASS, config.QUEUE_NAME)
    def should_run() -> bool:
        health.beat()   # the consumer asks this at least once a second, even with an empty queue
        return running

    consumer.consume(handle, should_run)
    publisher.close()
    log.info("ingestion stopped")


if __name__ == "__main__":
    main()
