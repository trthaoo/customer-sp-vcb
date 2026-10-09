import pytest
from fastapi.testclient import TestClient
from src.web.app import app
import src.config as config_module
import src.web.app as app_module

@pytest.fixture
def client():
    return TestClient(app)

def test_posthog_static_script_exists(client):
    """Verify posthog-init.js is accessible via static files mount."""
    response = client.get("/static/posthog-init.js")
    assert response.status_code == 200
    assert "PostHog Analytics & Session Recording Initializer" in response.text
    assert "startSessionRecording" in response.text
    assert "maskAllInputs: false" in response.text

def test_posthog_config_endpoint(client, monkeypatch):
    """Verify /api/posthog/config endpoint returns configuration."""
    monkeypatch.setattr(app_module, "POSTHOG_API_KEY", "phc_test123456789")
    monkeypatch.setattr(app_module, "POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setattr(app_module, "POSTHOG_ENABLE_RECORDING", True)

    response = client.get("/api/posthog/config")
    assert response.status_code == 200
    data = response.json()
    assert data["apiKey"] == "phc_test123456789"
    assert data["apiHost"] == "https://us.i.posthog.com"
    assert data["enableRecording"] is True
    assert data["enabled"] is True

def test_posthog_html_injection(client, monkeypatch):
    """Verify runtime PostHog config is injected into HTML <head>."""
    monkeypatch.setattr(app_module, "POSTHOG_API_KEY", "phc_live_sample")
    monkeypatch.setattr(app_module, "POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setattr(app_module, "POSTHOG_ENABLE_RECORDING", True)

    # Playground page
    resp_playground = client.get("/playground")
    assert resp_playground.status_code == 200
    assert "window.__POSTHOG_CONFIG__" in resp_playground.text
    assert "phc_live_sample" in resp_playground.text
    assert "/static/posthog-init.js" in resp_playground.text

    # Dashboard root page (follows redirect to /playground)
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "window.__POSTHOG_CONFIG__" in resp_root.text
    assert "/static/posthog-init.js" in resp_root.text

    # Ops console page
    resp_ops = client.get("/ops")
    assert resp_ops.status_code == 200
    assert "window.__POSTHOG_CONFIG__" in resp_ops.text
    assert "/static/posthog-init.js" in resp_ops.text

def test_posthog_config_public_under_basic_auth(client, monkeypatch):
    """Verify /api/posthog/config remains public when basic auth is active."""
    monkeypatch.setattr(app_module, "_AUTH_PASS", "secretpassword")
    monkeypatch.setattr(app_module, "_AUTH_HEADER", "Basic dXNlcjpwYXNz")

    # Public endpoint should succeed without auth
    resp = client.get("/api/posthog/config")
    assert resp.status_code == 200

def test_session_rating_records_posthog_replay_url(client, monkeypatch, tmp_path):
    """Verify posthog_replay_url is preserved when rating playground sessions."""
    from src.storage.test_cases import TestCaseManager
    from src.storage.database import EventStore

    test_mgr = TestCaseManager(golden_file=tmp_path / "golden.json", failed_file=tmp_path / "failed.json")
    test_store = EventStore(str(tmp_path / "test.db"))

    monkeypatch.setattr("src.web.app.get_test_case_manager", lambda: test_mgr)
    monkeypatch.setattr("src.web.app.get_event_store", lambda: test_store)

    replay_url = "https://us.posthog.com/project/123/replay/sess-abc-789"

    # Pass rating
    pass_payload = {
        "session_id": "test_ph_sess_1",
        "rating": "pass",
        "channel": "meta",
        "platform": "ig",
        "surface": "dm",
        "title": "Golden Replay Test",
        "turns": [{"turn_index": 1, "customer_message": "hi", "bot_reply": "hello"}],
        "posthog_replay_url": replay_url
    }
    resp_pass = client.post("/api/playground/session/rate", json=pass_payload)
    assert resp_pass.status_code == 200
    assert resp_pass.json()["success"] is True

    # Fail rating
    fail_payload = {
        "session_id": "test_ph_sess_2",
        "rating": "fail",
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "error_category": "wrong_product_link",
        "root_cause": "Incorrect SKU returned",
        "turns": [{"turn_index": 1, "customer_message": "buy ring", "bot_reply": "wrong link"}],
        "posthog_replay_url": replay_url
    }
    resp_fail = client.post("/api/playground/session/rate", json=fail_payload)
    assert resp_fail.status_code == 200
    assert resp_fail.json()["success"] is True
