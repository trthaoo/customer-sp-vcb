import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from src.web.app import app
from src.knowledge.loader import KnowledgeBase
from src.storage.database import EventStore
from src.config import KNOWLEDGE_DIR
from src.adapters.model import ModelAdapter
from src.pipeline.orchestrator import PipelineOrchestrator
import src.pipeline.orchestrator as orch_module

def get_test_client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_attachments.db"
    store = EventStore(str(test_db))
    monkeypatch.setattr("src.web.app.get_event_store", lambda: store)
    monkeypatch.setattr("src.pipeline.orchestrator.get_event_store", lambda: store)

    kb = KnowledgeBase(KNOWLEDGE_DIR)
    monkeypatch.setattr("src.web.app.get_knowledge_base", lambda: kb)
    monkeypatch.setattr("src.pipeline.orchestrator.get_knowledge_base", lambda: kb)

    test_orchestrator = PipelineOrchestrator(kb=kb, store=store)
    monkeypatch.setattr(orch_module, "_orchestrator", test_orchestrator)
    monkeypatch.setattr("src.web.app.get_orchestrator", lambda: test_orchestrator)
    monkeypatch.setattr("src.pipeline.orchestrator.get_orchestrator", lambda: test_orchestrator)

    mock_adapter = ModelAdapter(api_key="", base_url="", model_name="gemini-1.5-flash")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_adapter)

    return TestClient(app)

def test_chat_with_link_attachment(tmp_path, monkeypatch):
    client = get_test_client(tmp_path, monkeypatch)
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "dm",
        "text": "Shop ơi cho mình hỏi nhẫn này giá bao nhiêu?",
        "attachment_url": "https://vienchibao.com/products/spinning-ring",
        "attachment_type": "link",
        "attachment_name": "Nhẫn Cỏ 4 Lá Xoay Trầm Hương"
    }
    resp = client.post("/api/playground/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["attachment_url"] == "https://vienchibao.com/products/spinning-ring"
    assert data["attachment_type"] == "link"
    assert data["attachment_name"] == "Nhẫn Cỏ 4 Lá Xoay Trầm Hương"
    assert data["decision"] in ("auto_reply", "fallback", "escalate")

def test_chat_with_image_upload(tmp_path, monkeypatch):
    client = get_test_client(tmp_path, monkeypatch)

    # Create dummy image
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    # Upload image
    up_resp = client.post(
        "/api/playground/upload_media",
        files={"files": ("test_ring.jpg", buf.getvalue(), "image/jpeg")}
    )
    assert up_resp.status_code == 200
    up_data = up_resp.json()
    assert "media_cache_id" in up_data
    assert up_data["frame_count"] >= 1
    assert up_data["media_type"] == "image"
    assert up_data["preview_url"] is not None

    # Test file serving endpoint
    media_resp = client.get(up_data["preview_url"])
    assert media_resp.status_code == 200
    assert media_resp.headers["content-type"] == "image/jpeg"

    # Chat with this uploaded image
    chat_resp = client.post("/api/playground/chat", json={
        "channel": "meta",
        "platform": "ig",
        "surface": "dm",
        "text": "Cái này giá bao nhiêu?",
        "chat_media_cache_id": up_data["media_cache_id"],
        "attachment_type": "image",
        "attachment_name": "test_ring.jpg",
        "attachment_url": up_data["preview_url"]
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["attached_frames_count"] >= 1
    assert chat_data["attachment_type"] == "image"

def test_chat_with_image_only_no_text(tmp_path, monkeypatch):
    client = get_test_client(tmp_path, monkeypatch)
    chat_resp = client.post("/api/playground/chat", json={
        "channel": "meta",
        "platform": "ig",
        "surface": "dm",
        "text": "[Khách gửi 1 hình ảnh sản phẩm]",
        "attachment_type": "image",
        "attachment_url": "/static/products/N0006-07-S-WH.jpg",
        "attachment_name": "N0006-07-S-WH.jpg"
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["attachment_type"] == "image"
