import time

from fastapi.testclient import TestClient

from app.core.faults import faults
from app.main import app

client = TestClient(app)


def test_faults_are_hidden_by_default(monkeypatch):
    monkeypatch.delenv("FAULTS_ENABLED", raising=False)
    assert client.get("/faults").status_code == 404
    assert client.post("/faults/cpu").status_code == 404


def test_latency_fault_slows_requests_but_not_health(monkeypatch):
    monkeypatch.setenv("FAULTS_ENABLED", "true")
    assert client.post("/faults/latency?delay_ms=300").json()["latency_ms"] == 300
    try:
        start = time.perf_counter()
        client.get("/notes")
        assert time.perf_counter() - start >= 0.25  # sleep may end a bit early

        start = time.perf_counter()
        client.get("/health")
        assert time.perf_counter() - start < 0.2  # tooling endpoints exempt
    finally:
        client.delete("/faults/latency")
    assert faults.status()["latency_ms"] == 0


def test_cpu_fault_starts_and_stops(monkeypatch):
    monkeypatch.setenv("FAULTS_ENABLED", "true")
    assert client.post("/faults/cpu").json()["cpu"] is True
    assert client.delete("/faults/cpu").json()["cpu"] is False


def test_memory_fault_leaks_then_frees(monkeypatch):
    monkeypatch.setenv("FAULTS_ENABLED", "true")
    client.post("/faults/memory")
    time.sleep(1.2)
    assert client.get("/faults").json()["memory_leaked_mb"] >= 1
    status = client.delete("/faults/memory").json()
    assert status["memory"] is False
    assert status["memory_leaked_mb"] == 0


def test_invalid_latency_is_rejected(monkeypatch):
    monkeypatch.setenv("FAULTS_ENABLED", "true")
    assert client.post("/faults/latency?delay_ms=0").status_code == 422
