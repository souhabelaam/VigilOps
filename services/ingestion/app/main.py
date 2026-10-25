"""Ingestion: read raw samples from the queue, compute rates, store them in PostgreSQL."""
import logging
import signal

from app.core import config
from app.repositories.database import RateRepository
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

    conninfo = (f"host={config.POSTGRES_HOST} port={config.POSTGRES_PORT} dbname={config.POSTGRES_DB} "
                f"user={config.POSTGRES_USER} password={config.POSTGRES_PASSWORD}")
    repository = RateRepository(conninfo)
    repository.connect()
    calculator = RateCalculator(config.MAX_GAP_S)

    def handle(message: dict) -> None:
        rate = calculator.process(Sample.from_message(message))
        if rate is None:
            return
        repository.save(rate)
        log.info("%s cpu=%s%% req/s=%s reset=%s", rate.app, rate.cpu_pct, rate.req_per_s, rate.reset)

    consumer = QueueConsumer(config.RABBITMQ_HOST, config.RABBITMQ_PORT,
                             config.RABBITMQ_USER, config.RABBITMQ_PASS, config.QUEUE_NAME)
    consumer.consume(handle, lambda: running)
    log.info("ingestion stopped")


if __name__ == "__main__":
    main()
