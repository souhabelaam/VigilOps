"""Where a notification goes. Console now; email will be a second class with the same send()."""
import logging

log = logging.getLogger("alerting")


class ConsoleNotifier:
    def send(self, message: str) -> None:
        log.warning(message)   # visible with: docker compose logs alerting
