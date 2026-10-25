"""Settings, read from environment variables so Compose and Kubernetes can change them."""
import os


def _targets() -> dict[str, str]:
    """TARGETS="notes-api=http://notes-api:8001,report-api=http://report-api:8002"."""
    raw = os.getenv(
        "TARGETS",
        "notes-api=http://notes-api:8001,report-api=http://report-api:8002",
    )
    pairs = (item.split("=", 1) for item in raw.split(",") if item.strip())
    return {name.strip(): url.strip() for name, url in pairs}


TARGETS = _targets()
SCRAPE_INTERVAL_S = float(os.getenv("SCRAPE_INTERVAL_S", "5"))
SCRAPE_TIMEOUT_S = float(os.getenv("SCRAPE_TIMEOUT_S", "3"))

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "")   # no default: the password comes from .env
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "")
QUEUE_NAME = os.getenv("QUEUE_NAME", "raw-metrics")
