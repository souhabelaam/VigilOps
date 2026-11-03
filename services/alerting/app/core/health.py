"""Health door for a worker with no web server: Kubernetes asks /health and /ready."""
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("health")


class Health:
    """The notepad: the main loop writes on it, the HTTP door only reads it."""

    def __init__(self, max_silence_s: float):
        self._max_silence_s = max_silence_s
        self._last_beat = time.monotonic()
        self._ready = False

    def beat(self) -> None:
        """Called by the main loop: 'I am still going round'."""
        self._last_beat = time.monotonic()

    def set_ready(self, ready: bool) -> None:
        self._ready = ready

    def is_alive(self) -> bool:
        """Not stuck. While not ready we are still waiting for a dependency, which is not a freeze."""
        return not self._ready or time.monotonic() - self._last_beat < self._max_silence_s

    def is_ready(self) -> bool:
        return self._ready


def start_server(health: Health, port: int) -> ThreadingHTTPServer:
    """Serve GET /health (liveness) and GET /ready (readiness) from a background thread."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            checks = {"/health": health.is_alive, "/ready": health.is_ready}
            check = checks.get(self.path)
            if check is None:
                self.send_response(404)
                self.end_headers()
                return
            ok = check()
            body = b"ok" if ok else b"not ok"
            self.send_response(200 if ok else 503)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # Kubernetes asks every few seconds: do not fill the logs

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("health door open on port %s", port)
    return server
