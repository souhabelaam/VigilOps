"""Settings, read from environment variables so Compose and Kubernetes can change them."""
import os
from pathlib import Path

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "")   # no default: the password comes from .env
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "")
INPUT_QUEUE = os.getenv("INPUT_QUEUE", "rates")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE", "anomalies")

# health door for Kubernetes probes (liveness /health, readiness /ready)
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))
HEALTH_MAX_SILENCE_S = float(os.getenv("HEALTH_MAX_SILENCE_S", "15"))

MODELS_DIR = Path(os.getenv("MODELS_DIR", "models"))
APPS = ["notes-api", "report-api"]

# same rule as ml/windows.py: rows further apart than this are never joined
MAX_GAP_S = float(os.getenv("MAX_GAP_S", "6"))

# alarm only after k windows in a row above the threshold; chosen by ml/debounce.py
K = {"notes-api": int(os.getenv("K_NOTES_API", "2")),
     "report-api": int(os.getenv("K_REPORT_API", "1"))}
