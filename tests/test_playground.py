import pytest
import io
import re
import csv
from fastapi.testclient import TestClient
from src.web.app import app
from src.knowledge.loader import get_knowledge_base, KnowledgeBase
from src.storage.database import get_event_store, EventStore
from src.config import KNOWLEDGE_DIR
from src.adapters.model import ModelAdapter, get_model_adapter
from src.pipeline.orchestrator import PipelineOrchestrator
import src.pipeline.orchestrator as orch_module

@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "playground_test_events.db"
    store = EventStore(str(test_db))
    monkeypatch.setattr("src.web.app.get_event_store", lambda: store)
    monkeypatch.setattr("src.pipeline.orchestrator.get_event_store", lambda: store)
    
    # Reload fresh knowledge base with products.json
    kb = KnowledgeBase(KNOWLEDGE_DIR)
    monkeypatch.setattr("src.web.app.get_knowledge_base", lambda: kb)
    monkeypatch.setattr("src.pipeline.orchestrator.get_knowledge_base", lambda: kb)

    # Reset orchestrator singleton with test kb & store
    test_orchestrator = PipelineOrchestrator(kb=kb, store=store)
    monkeypatch.setattr(orch_module, "_orchestrator", test_orchestrator)
    monkeypatch.setattr("src.web.app.get_orchestrator", lambda: test_orchestrator)
    monkeypatch.setattr("src.pipeline.orchestrator.get_orchestrator", lambda: test_orchestrator)

    # Ensure no API key for default tests
    mock_adapter = ModelAdapter(api_key="", base_url="", model_name="gemini-1.5-flash")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_adapter)

    # Isolate test cases storage
    from src.storage.test_cases import TestCaseManager
    test_manager = TestCaseManager(
        golden_file=tmp_path / "test_golden.json",
        failed_file=tmp_path / "test_failed.json"
    )
    monkeypatch.setattr("src.web.app.get_test_case_manager", lambda: test_manager)

    return TestClient(app)

# 1. /playground route renders with optimized US Market layout (badge removed)
def test_playground_page_renders(client):
    response = client.get("/playground")
    assert response.status_code == 200
    assert "PHIÊN TEST, KHÔNG PHẢI SỐ LIVE" not in response.text
    assert "Vien Chi Bao" in response.text
    assert "Pipeline Diagnostics" in response.text

# 2. source=brand_test never calls Zernio and never leaks into live dashboard or handover
def test_playground_source_brand_test_isolation(client):
    # Verify initial live metrics are 0
    m_before = client.get("/api/metrics?channel=meta").json()
    assert m_before["inbound_count"] == 0

    # Post message via playground chat
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "Nhẫn cỏ bốn lá giá bao nhiêu ạ?",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["reply_sent"] is False
    assert data["status_badge"] in ("handled", "fallback")
    assert data["matched_product"] is not None
    assert data["matched_product"]["id"] == "N0044-09-S-WH"

    # Verify live dashboard metrics remain 0 (brand_test excluded)
    m_after = client.get("/api/metrics?channel=meta").json()
    assert m_after["inbound_count"] == 0
    assert m_after["auto_replied_count"] == 0

    # Verify handover queue remains empty
    queue = client.get("/api/handover?channel=meta").json()
    assert len(queue["queue"]) == 0

# 3. No model key shows "chưa gắn API model" and does not invent a reply
def test_playground_no_model_key_shows_chua_gan_api_model(client):
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "Dây chuyền nơ hồ điệp chất liệu gì vậy shop?",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["reply"] == "chưa gắn API model"
    assert data["status_badge"] == "handled"
    assert data["model_called"] is False
    assert data["decision"] == "auto_reply"
    assert data["flag"] == "auto_reply"

# 4. Missing fact returns fallback from fallbacks.md + handover flag, never invents price
def test_playground_missing_fact_returns_fallback_and_handover(client):
    # Query product with null price (VCB_SP_TEST_NOPRICE)
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "cho em xin giá nhẫn thạch anh với ạ",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "fallback"
    assert data["flag"] == "handover"
    assert data["status_badge"] == "fallback"
    assert data["needs_human"] is True
    assert "catalogue.price" in data["missing_fields"]
    # Ensures fallback text is returned, not invented numbers
    assert data["reply"] == "Let me double-check this exact piece with our studio workshop and get right back to you! ✨"
    assert not re.search(r'\d+[\.,]?\d*\s*(?:đ|vnd|\$)', data["reply"], re.IGNORECASE)

# 5. Edge case matches before a general rule, example_good_reply is a sample not the fact source
def test_playground_edge_case_beats_general_rule(client):
    payload = {
        "channel": "meta",
        "platform": "fb",
        "surface": "comment",
        "text": "Nhẫn cỏ 4 lá này shop lừa đảo à hàng vừa nhận đã méo xệch hoàn tiền gấp!",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["matched_edge_case"] == "meta_edge_angry_complaint"
    assert data["decision"] == "escalate"
    assert data["flag"] == "handover"
    assert data["status_badge"] == "handover"
    assert data["needs_human"] is True
    # example_good_reply is provided as side-by-side sample for brand review
    assert data["example_good_reply"] is not None
    assert "quản lý" in data["example_good_reply"]

# 6. Multi-turn conversation preserves history across turns
def test_playground_multi_turn_history(client):
    history = [
        {"role": "user", "content": "Em chào shop"},
        {"role": "assistant", "content": "Dạ em chào anh/chị ạ! Em có thể tư vấn mẫu nào cho mình nha?"}
    ]
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "dm",
        "text": "Shop có mẫu nhẫn cỏ 4 lá không ạ?",
        "history": history
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["matched_product"] is not None
    assert data["matched_product"]["id"] == "N0044-09-S-WH"

# 7. Model API with active key generates reply with Brand Voice
def test_playground_with_configured_model(client, monkeypatch):
    class MockActiveAdapter(ModelAdapter):
        def is_available(self):
            return True
        def generate_reply(self, system_prompt, messages):
            assert "Viễn Chí Bảo" in system_prompt
            assert "The Mindful Studio Host" in system_prompt
            return "Dạ nhẫn xoay cỏ bốn lá bên em chế tác từ Bạc Thái S925 có giá 650.000đ ạ! ✨"

    mock_active = MockActiveAdapter(api_key="mock_key", model_name="gemini-1.5-flash")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_active)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_active)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_active)

    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "nhẫn cỏ bốn lá giá bao nhiêu ạ",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["model_called"] is True
    assert "650.000đ" in data["reply"]
    assert data["status_badge"] == "handled"

# 8. Edge cases endpoint returns list for channel
def test_playground_edge_cases_endpoint(client):
    res_meta = client.get("/api/playground/edge_cases?channel=meta")
    assert res_meta.status_code == 200
    data_meta = res_meta.json()
    assert data_meta["channel"] == "meta"
    assert len(data_meta["edge_cases"]) >= 2

    res_tiktok = client.get("/api/playground/edge_cases?channel=tiktok")
    assert res_tiktok.status_code == 200
    data_tiktok = res_tiktok.json()
    assert data_tiktok["channel"] == "tiktok"
    assert len(data_tiktok["edge_cases"]) >= 2

# 9. Export CSV endpoint returns valid CSV with UTF-8 BOM
def test_playground_export_csv(client):
    payload = {
        "session_id": "sess_test_123",
        "turns": [
            {
                "turn_index": 1,
                "timestamp": "10:00:00",
                "channel": "meta",
                "platform": "ig",
                "surface": "comment",
                "post_context": "Caption test",
                "customer_message": "Nhẫn cỏ 4 lá giá bao nhiêu?",
                "bot_reply": "chưa gắn API model",
                "status_badge": "handled",
                "matched_product": "Nhẫn Xoay Cỏ Bốn Lá (VCB_SP01)",
                "matched_rule": "meta_ask_price_comment",
                "files_used": ["catalogue/products.json", "meta/rules.md"],
                "missing_fields": [],
                "reason": "Khớp quy tắc meta_ask_price_comment",
                "example_good_reply": "",
                "decision": "auto_reply",
                "flag": "auto_reply"
            }
        ]
    }
    response = client.post("/api/playground/export_csv", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=" in response.headers["content-disposition"]
    
    content = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 2  # Header + 1 turn
    assert rows[0][0] == "Turn #"
    assert rows[1][6] == "Nhẫn cỏ 4 lá giá bao nhiêu?"
    assert rows[1][8] == "handled"

# 10. Media Upload Endpoint creates frames and timestamps
def test_playground_media_upload_endpoint(client, tmp_path):
    from PIL import Image
    test_img = tmp_path / "test_slide.jpg"
    im = Image.new("RGB", (640, 480), color="blue")
    im.save(test_img, "JPEG")

    with open(test_img, "rb") as f:
        files = [("files", ("slide1.jpg", f.read(), "image/jpeg"))]
        response = client.post("/api/playground/upload_media", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["media_cache_id"].startswith("upload_")
    assert data["frame_count"] == 1
    assert data["timestamps"] == ["t=0.0s"]
    assert len(data["frames"]) == 1
    assert data["frames"][0]["base64_data"] != ""

def test_upload_filename_cannot_escape_upload_dir(client):
    from src.pipeline.media import get_media_processor
    cache_dir = get_media_processor().cache_dir
    escaped = cache_dir.parent / "escape_probe.txt"
    files = [("files", ("../../escape_probe.txt", b"x", "text/plain"))]
    data = client.post("/api/playground/upload_media", files=files).json()
    assert not escaped.exists()
    assert (cache_dir / data["media_cache_id"] / "escape_probe.txt").exists()

def test_webhook_rejected_when_secret_unset(client, monkeypatch):
    monkeypatch.setattr("src.adapters.zernio.ZERNIO_WEBHOOK_SECRET", "")
    response = client.post("/webhooks/zernio", json={"event": "comment.created"})
    assert response.status_code == 401

# 11. Deictic comment resolution using caption + frames
def test_deictic_resolution_with_caption(client, monkeypatch):
    class MockVisionAdapter(ModelAdapter):
        def is_available(self):
            return True
        def is_vision_capable(self):
            return True
        def generate_reply(self, system_prompt, messages, frames=None):
            # Grounding check: system prompt must include caption and allowed facts
            assert "$279.00" in system_prompt
            return "Dạ mẫu nhẫn xoay cỏ bốn lá may mắn này của bên em có giá $279 ạ! ✨ [REASON: product=N0044-09-S-WH, frame=t=0.0s, chunks=catalogue/meta_ask_price_comment]"

    mock_adapter = MockVisionAdapter(api_key="mock_key", model_name="gemini-1.5-flash")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_adapter)

    # Attach dummy frame
    from src.models import MediaFrame
    test_frame = MediaFrame(timestamp=0.0, label="t=0.0s", base64_data="abc", mime_type="image/jpeg")
    from src.pipeline.media import get_media_processor
    processor = get_media_processor()
    monkeypatch.setattr(processor, "process_media", lambda **kwargs: ([test_frame], False))

    # Customer uses deictic "cái này bao nhiêu" with attached video frame & post caption mentioning "nhẫn cỏ bốn lá"
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "cái này bao nhiêu vậy shop?",
        "post_context": "BST Nhẫn Xoay Cỏ Bốn Lá Bạc Thái S925 may mắn bình an.",
        "media_cache_id": "test_deictic_vid",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["matched_product"] is not None
    assert data["matched_product"]["id"] == "N0044-09-S-WH"
    assert "$279" in data["reply"]
    assert "[REASON:" not in data["reply"]  # Chain-of-thought stripped from customer reply!
    assert "N0044-09-S-WH" in data["short_reason"]  # Short reason retained for playground panel!

# 12. A frame never fills a null field (Strict knowledge fact guardrail)
def test_frame_never_fills_null_field(client, monkeypatch):
    class MockVisionAdapter(ModelAdapter):
        def is_available(self):
            return True
        def is_vision_capable(self):
            return True
        def generate_reply(self, system_prompt, messages, frames=None):
            return "999.000đ"  # Model attempts to invent a price

    mock_adapter = MockVisionAdapter(api_key="mock_key", model_name="gemini-1.5-flash")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_adapter)

    # VCB_SP_TEST_NOPRICE has price = null in catalogue/products.json
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "nhẫn thạch anh tóc vàng này giá bao nhiêu?",
        "post_context": "Nhẫn Đá Thạch Anh Tóc Vàng Bạc Thái S925",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must fallback and handover; frame/model NEVER invents 999.000đ!
    assert data["decision"] == "fallback"
    assert data["flag"] == "handover"
    assert data["status_badge"] == "fallback"
    assert "999.000đ" not in data["reply"]
    assert "catalogue.price" in data["missing_fields"]

# 13. Product visible but not in catalogue = say so and handover
def test_product_visible_not_in_catalogue_handovers(client, monkeypatch):
    class MockUnlistedAdapter(ModelAdapter):
        def is_available(self):
            return True
        def is_vision_capable(self):
            return True
        def generate_reply(self, system_prompt, messages, frames=None):
            if "TASK:" in system_prompt:
                # Visual inspect step flags unlisted product
                return "MATCH_ID: NONE\nGUESS: Lắc tay kim cương vàng trắng\nFRAME: t=2.0s\nUNLISTED: TRUE"
            return "Dạ shop chào bạn"

    mock_adapter = MockUnlistedAdapter(api_key="mock_key", model_name="gemini-1.5-flash")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_adapter)

    # Attach dummy frame
    from src.models import MediaFrame
    test_frame = MediaFrame(timestamp=2.0, label="t=2.0s", base64_data="abc", mime_type="image/jpeg")

    # Mock media extraction
    from src.pipeline.media import get_media_processor
    processor = get_media_processor()
    monkeypatch.setattr(processor, "process_media", lambda **kwargs: ([test_frame], False))

    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "mẫu trong video này bao nhiêu tiền vậy shop?",
        "media_cache_id": "test_unlisted_vid",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "fallback"
    assert data["flag"] == "handover"
    assert data["status_badge"] == "handover"
    assert data["needs_human"] is True
    # Says so politely to customer!
    assert "chưa có trong danh mục niêm yết" in data["reply"]
    assert data["catalogue_id_matched"] is None
    assert data["visual_product_guess"] == "Lắc tay kim cương vàng trắng"

# 14. Context missing handover when comment depends on video
def test_context_missing_comment_handovers(client):
    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "cái này bên trái bao nhiêu vậy ạ?",
        # No post_context and no media_cache_id -> context_missing = True
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["context_missing"] is True
    assert data["decision"] == "fallback"
    assert data["flag"] == "handover"
    assert data["status_badge"] == "handover"
    assert "Context missing" in data["short_reason"]

# 15. Vision unsupported handover when comment needs video
def test_vision_unsupported_handovers_when_comment_needs_video(client, monkeypatch):
    class MockNonVisionAdapter(ModelAdapter):
        def is_available(self):
            return True
        def is_vision_capable(self):
            return False  # Non-vision model (e.g. text-only)
        def generate_reply(self, system_prompt, messages, frames=None):
            return "Text reply"

    mock_adapter = MockNonVisionAdapter(api_key="mock_key", model_name="text-davinci-003")
    monkeypatch.setattr("src.web.app.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.adapters.model.get_model_adapter", lambda: mock_adapter)
    monkeypatch.setattr("src.pipeline.composer.get_model_adapter", lambda: mock_adapter)

    # Attach dummy frame
    from src.models import MediaFrame
    test_frame = MediaFrame(timestamp=0.0, label="t=0.0s", base64_data="abc", mime_type="image/jpeg")
    from src.pipeline.media import get_media_processor
    processor = get_media_processor()
    monkeypatch.setattr(processor, "process_media", lambda **kwargs: ([test_frame], False))

    payload = {
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "mẫu trong video giá bao nhiêu shop?",
        "media_cache_id": "test_nv_vid",
        "history": []
    }
    response = client.post("/api/playground/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["vision_unsupported"] is True
    assert data["decision"] == "fallback"
    assert data["flag"] == "handover"
    assert data["status_badge"] == "handover"
    assert "Vision unsupported" in data["short_reason"]

# 16. Session Rating: "pass" correctly saves Golden Example with turns and metadata
def test_session_rating_pass_saves_golden_example(client):
    payload = {
        "session_id": "session_test_pass_001",
        "rating": "pass",
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "title": "Hỏi giá Nhẫn cỏ 4 lá và ship US",
        "notes": "Bot trả lời xuất sắc $48 USD và bạc S925",
        "tags": ["clover_ring", "usd_price", "us_market"],
        "turns": [
            {
                "turn_index": 1,
                "customer_message": "How much is the Four-Leaf Clover Spinning Ring?",
                "bot_reply": "Our Four-Leaf Clover Spinning Ring in S925 sterling silver is $48.00 USD ✨",
                "status_badge": "handled",
                "matched_product": {"id": "N0044-09-S-WH", "name": "Four-Leaf Clover Spinning Ring"}
            }
        ]
    }
    response = client.post("/api/playground/session/rate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["rating"] == "pass"
    assert data["case"]["title"] == "Hỏi giá Nhẫn cỏ 4 lá và ship US"
    assert data["case"]["turn_count"] == 1

    # Verify retrieval via /api/playground/session/cases
    cases_res = client.get("/api/playground/session/cases")
    assert cases_res.status_code == 200
    cases_data = cases_res.json()
    assert cases_data["stats"]["golden_count"] == 1
    assert cases_data["golden_examples"][0]["id"] == data["case"]["id"]

# 17. Session Rating: "fail" requires error_category and root_cause
def test_session_rating_fail_validation(client):
    # Missing error_category
    payload_no_cat = {
        "session_id": "session_test_fail_001",
        "rating": "fail",
        "turns": []
    }
    res = client.post("/api/playground/session/rate", json=payload_no_cat)
    assert res.status_code == 400
    assert "error_category" in res.json()["detail"]

    # Missing root_cause
    payload_no_cause = {
        "session_id": "session_test_fail_002",
        "rating": "fail",
        "error_category": "sai_chinh_sach",
        "turns": []
    }
    res2 = client.post("/api/playground/session/rate", json=payload_no_cause)
    assert res2.status_code == 400
    assert "root_cause" in res2.json()["detail"]

# 18. Session Rating: "fail" records root cause, suggested fix, and target file
def test_session_rating_fail_saves_audit_and_fix(client):
    payload = {
        "session_id": "session_test_fail_003",
        "rating": "fail",
        "channel": "meta",
        "platform": "fb",
        "surface": "dm",
        "error_category": "sai_chinh_sach",
        "failed_turn_index": 1,
        "root_cause": "Bot báo cho phép đổi trả trong 30 ngày trong khi chính sách HuyK Jewelry chỉ chấp nhận trong 7 ngày đối với hàng lỗi.",
        "suggested_fix": "Cập nhật rule trong knowledge/policies/returns.md nhấn mạnh quy định 7 ngày, cấm tuyệt đối nhắc 30 ngày.",
        "target_file_to_fix": "knowledge/policies/returns.md",
        "turns": [
            {
                "turn_index": 1,
                "customer_message": "Chính sách đổi trả thế nào shop?",
                "bot_reply": "Dạ shop hỗ trợ đổi trả trong 30 ngày ạ!",
                "status_badge": "handled"
            }
        ]
    }
    response = client.post("/api/playground/session/rate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["rating"] == "fail"
    case = data["case"]
    assert case["error_category"] == "sai_chinh_sach"
    assert case["status"] == "open"
    assert case["target_file_to_fix"] == "knowledge/policies/returns.md"

    # Verify retrieval
    cases_res = client.get("/api/playground/session/cases")
    cases_data = cases_res.json()
    assert cases_data["stats"]["failed_count"] == 1
    assert cases_data["stats"]["open_failed_count"] == 1
    assert cases_data["stats"]["fixed_failed_count"] == 0

# 19. Case Hub: Update status of failed case (Mark as fixed & Reopen)
def test_failed_case_status_toggle(client):
    # First create a fail case
    payload = {
        "session_id": "session_fail_status_test",
        "rating": "fail",
        "error_category": "sai_san_pham",
        "root_cause": "Báo sai giá sản phẩm",
        "suggested_fix": "Cập nhật giá $48 trong products.json",
        "turns": []
    }
    create_res = client.post("/api/playground/session/rate", json=payload)
    case_id = create_res.json()["case"]["id"]

    # Mark as fixed
    patch_res = client.patch(f"/api/playground/session/cases/{case_id}/status", json={"status": "fixed", "fixed_notes": "Đã sửa file products.json"})
    assert patch_res.status_code == 200
    assert patch_res.json()["case"]["status"] == "fixed"
    assert patch_res.json()["case"]["fixed_at"] is not None

    # Verify stats
    cases_data = client.get("/api/playground/session/cases").json()
    assert cases_data["stats"]["fixed_failed_count"] == 1
    assert cases_data["stats"]["open_failed_count"] == 0

    # Reopen
    reopen_res = client.patch(f"/api/playground/session/cases/{case_id}/status", json={"status": "open"})
    assert reopen_res.status_code == 200
    assert reopen_res.json()["case"]["status"] == "open"

# 20. Case Hub: Delete case item
def test_delete_case_item(client):
    # Create golden
    payload = {
        "session_id": "session_to_delete",
        "rating": "pass",
        "title": "To be deleted",
        "turns": []
    }
    res = client.post("/api/playground/session/rate", json=payload)
    case_id = res.json()["case"]["id"]

    # Delete
    del_res = client.delete(f"/api/playground/session/cases/golden/{case_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Delete non-existent
    del_res_404 = client.delete("/api/playground/session/cases/golden/non_existent_id")
    assert del_res_404.status_code == 404

# 21. Playground page contains rating buttons and modals
def test_playground_page_renders_rating_controls(client):
    response = client.get("/playground")
    assert response.status_code == 200
    html = response.text
    assert "btn-rate-pass-hdr" in html
    assert "btn-rate-fail-hdr" in html
    assert "btn-case-hub" in html
    assert "session-rating-bar" in html
    assert "modal-rate-pass" in html
    assert "modal-rate-fail" in html
    assert "modal-case-hub" in html


