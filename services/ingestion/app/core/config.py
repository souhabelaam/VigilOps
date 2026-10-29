"""Settings, read from environment variables so Compose and Kubernetes can change them."""
import os

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "")   # no default: the password comes from .env
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "")
QUEUE_NAME = os.getenv("QUEUE_NAME", "raw-metrics")      # input: raw counters
RATES_QUEUE = os.getenv("RATES_QUEUE", "rates")          # output: one rate per app per 5 s

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "vigilops")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# two samples further apart than this are never subtracted (same rule as ml/prepare_data.py)
MAX_GAP_S = float(os.getenv("MAX_GAP_S", "6"))
