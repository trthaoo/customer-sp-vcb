import base64
import pytest
from fastapi.testclient import TestClient
import src.web.app as app_module


def _basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "_AUTH_PASS", "tpass")
    monkeypatch.setattr(app_module, "_AUTH_HEADER", _basic("tester", "tpass"))
    monkeypatch.setattr(app_module, "_ADMIN_PASS", "apass")
    monkeypatch.setattr(app_module, "_ADMIN_HEADER", _basic("admin", "apass"))
    return TestClient(app_module.app)


@pytest.mark.parametrize("path", ["/ops", "/api/chat-sessions", "/api/chat-backups/stats", "/api/metrics?channel=meta"])
def test_logs_need_admin_login(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": _basic("tester", "tpass")}).status_code == 401
    assert client.get(path, headers={"Authorization": _basic("admin", "apass")}).status_code == 200


def test_tester_and_admin_both_open_playground(client):
    assert client.get("/playground").status_code == 401
    for auth in (_basic("tester", "tpass"), _basic("admin", "apass")):
        assert client.get("/playground", headers={"Authorization": auth}).status_code == 200
