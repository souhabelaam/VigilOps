from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_create_and_list_note():
    response = client.post("/notes", json={"title": "hello", "content": "world"})
    assert response.status_code == 201
    note = response.json()
    assert note["title"] == "hello"

    notes = client.get("/notes").json()
    assert note["id"] in [n["id"] for n in notes]


def test_delete_note():
    note = client.post("/notes", json={"title": "to delete"}).json()
    assert client.delete(f"/notes/{note['id']}").status_code == 204
    notes = client.get("/notes").json()
    assert note["id"] not in [n["id"] for n in notes]


def test_delete_missing_note_returns_404():
    assert client.delete("/notes/999999").status_code == 404


def test_empty_title_is_rejected():
    response = client.post("/notes", json={"title": ""})
    assert response.status_code == 422


def test_metrics_records_requests_and_unmatched_label():
    client.get("/this-path-does-not-exist")
    text = client.get("/metrics").text
    assert "http_requests_total" in text
    assert 'path="unmatched"' in text
