import urllib.error
import urllib.request

from app.core import health as health_module
from app.core.health import Health, start_server


def test_not_ready_until_told():
    h = Health(max_silence_s=15)
    assert not h.is_ready()
    h.set_ready(True)
    assert h.is_ready()


def test_waiting_for_a_dependency_is_not_a_freeze():
    h = Health(max_silence_s=0)        # any silence would count as stuck...
    assert h.is_alive()                # ...but we are not ready yet, so we are only waiting


def test_stuck_loop_is_reported_dead(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(health_module.time, "monotonic", lambda: now[0])
    h = Health(max_silence_s=15)
    h.set_ready(True)
    h.beat()
    now[0] += 10
    assert h.is_alive()                # recent beat
    now[0] += 10
    assert not h.is_alive()            # 20 s of silence
    h.beat()
    assert h.is_alive()                # the loop is back


def _status(port, path):
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2).status
    except urllib.error.HTTPError as error:
        return error.code


def test_http_door_answers_with_status_codes():
    h = Health(max_silence_s=15)
    server = start_server(h, 0)        # port 0: the system picks a free port
    port = server.server_address[1]
    try:
        assert _status(port, "/health") == 200
        assert _status(port, "/ready") == 503
        h.set_ready(True)
        assert _status(port, "/ready") == 200
        assert _status(port, "/nothing") == 404
    finally:
        server.shutdown()
