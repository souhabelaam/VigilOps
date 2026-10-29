"""Settings, read from environment variables so Compose and Kubernetes can change them."""
import os

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "")   # no default: the password comes from .env
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "")
QUEUE_NAME = os.getenv("QUEUE_NAME", "anomalies")

# an incident is over when an app sends no anomaly event for this long
COOLDOWN_S = float(os.getenv("COOLDOWN_S", "60"))
