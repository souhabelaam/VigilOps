from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_create_report_returns_correct_count():
    response = client.post("/reports", json={"limit": 1000})
    assert response.status_code == 201
    body = response.json()
    assert body["limit"] == 1000
    assert body["prime_count"] == 168  # known: 168 primes below 1000
    assert body["duration_seconds"] >= 0


def test_list_reports_contains_created_report():
    created = client.post("/reports", json={"limit": 50}).json()
    reports = client.get("/reports").json()
    assert created["id"] in [r["id"] for r in reports]


def test_limit_above_maximum_is_rejected():
    response = client.post("/reports", json={"limit": 1_000_001})
    assert response.status_code == 422


def test_limit_below_minimum_is_rejected():
    response = client.post("/reports", json={"limit": 1})
    assert response.status_code == 422


def test_metrics_records_requests_and_unmatched_label():
    client.get("/this-path-does-not-exist")
    text = client.get("/metrics").text
    assert "http_requests_total" in text
    assert 'path="unmatched"' in text
