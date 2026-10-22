from fastapi.testclient import TestClient

import main
from tests.conftest import TEST_SERVICE_TOKEN

client = TestClient(main.app)


def test_health_is_public():
    assert client.get("/health").status_code == 200


def test_missing_or_wrong_token_is_rejected():
    assert client.get("/tools").status_code == 401
    assert client.get("/tools", headers={"X-Service-Token": "wrong"}).status_code == 401
    assert client.post("/analyze", json={}).status_code == 401
    assert client.get("/openapi.json").status_code == 401


def test_correct_token_is_accepted():
    assert client.get("/tools", headers={"X-Service-Token": TEST_SERVICE_TOKEN}).status_code == 200


def test_fails_closed_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_TOKEN")
    response = client.get("/tools", headers={"X-Service-Token": ""})
    assert response.status_code == 503

    monkeypatch.setenv("AI_SERVICE_TOKEN", "short")
    assert client.get("/tools", headers={"X-Service-Token": "short"}).status_code == 503
