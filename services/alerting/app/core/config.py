"""Settings, read from environment variables so Compose and Kubernetes can change them."""
import os

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "")   # no default: the password comes from .env
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "")
QUEUE_NAME = os.getenv("QUEUE_NAME", "anomalies")

# an incident is over when an app sends no anomaly event for this long
COOLDOWN_S = float(os.getenv("COOLDOWN_S", "60"))

# where alerts go: "console" or "email" (email also prints to the console)
NOTIFIER = os.getenv("NOTIFIER", "console")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")          # no default: comes from the git-ignored .env
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # for Gmail: an "app password", never the real one
MAIL_TO = os.getenv("MAIL_TO", "")
