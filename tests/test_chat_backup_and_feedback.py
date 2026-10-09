import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.web.app import app
from src.config import BASE_DIR
from src.storage.chat_backup import get_chat_logs_dir, save_chat_backup_to_disk, get_chat_backup_stats

client = TestClient(app)

def test_chat_turn_creates_disk_backup_files():
    session_id = "test_auto_backup_sess_99"
    payload = {
        "session_id": session_id,
        "channel": "meta",
        "platform": "ig",
        "surface": "dm",
        "text": "Hello shop, nhẫn cỏ 4 lá bạc S925 này giá bao nhiêu USD?",
        "history": []
    }
    res = client.post("/api/playground/chat", json=payload)
    assert res.status_code == 200

    backup_dir = get_chat_logs_dir()
    json_backup = backup_dir / f"{session_id}.json"
    md_backup = backup_dir / f"{session_id}.md"

    assert json_backup.exists(), "JSON backup file was not created on disk"
    assert md_backup.exists(), "Markdown backup file was not created on disk"

    # Verify JSON content
    data = json.loads(json_backup.read_text(encoding="utf-8"))
    assert data["session_id"] == session_id
    assert data["channel"] == "meta"
    assert len(data["turns"]) >= 1
    assert data["turns"][0]["customer_message"] == payload["text"]

    # Verify Markdown content
    md_content = md_backup.read_text(encoding="utf-8")
    assert f"Chat Transcript Backup: {session_id}" in md_content
    assert payload["text"] in md_content


def test_rating_updates_chat_sessions_and_disk_backup():
    session_id = "test_rate_sync_sess_88"
    # Create turn first
    client.post("/api/playground/chat", json={
        "session_id": session_id,
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "text": "Shop ơi có bảo hành không?",
        "history": []
    })

    # Rate as FAIL
    rate_payload = {
        "session_id": session_id,
        "rating": "fail",
        "channel": "meta",
        "platform": "ig",
        "surface": "comment",
        "error_category": "sai_chinh_sach",
        "root_cause": "Bot trả lời bảo hành trọn đời thay vì bảo hành miễn phí xi mạ trong 6 tháng",
        "suggested_fix": "Cập nhật rule trong warranty.md nêu rõ chính sách 6 tháng",
        "target_file_to_fix": "knowledge/policies/warranty.md",
        "failed_turn_index": 1,
        "turns": [
            {
                "customer_message": "Shop ơi có bảo hành không?",
                "bot_reply": "Bảo hành trọn đời ạ."
            }
        ]
    }
    rate_res = client.post("/api/playground/session/rate", json=rate_payload)
    assert rate_res.status_code == 200
    case_id = rate_res.json()["case"]["id"]

    # Verify GET /api/chat-sessions/{session_id} includes rating & feedback
    sess_res = client.get(f"/api/chat-sessions/{session_id}")
    assert sess_res.status_code == 200
    sess_data = sess_res.json()
    assert sess_data["rating"] == "fail"
    assert sess_data["rating_data"]["error_category"] == "sai_chinh_sach"
    assert sess_data["rating_data"]["target_file_to_fix"] == "knowledge/policies/warranty.md"
    assert sess_data["rating_data"]["status"] == "open"

    # Verify disk backup was updated with rating feedback
    backup_dir = get_chat_logs_dir()
    json_backup = backup_dir / f"{session_id}.json"
    md_backup = backup_dir / f"{session_id}.md"

    b_json = json.loads(json_backup.read_text(encoding="utf-8"))
    assert b_json["rating"] == "fail"
    assert b_json["rating_data"]["case_id"] == case_id

    b_md = md_backup.read_text(encoding="utf-8")
    assert "FAIL (CẦN KHẮC PHỤC)" in b_md
    assert "warranty.md" in b_md


def test_toggle_case_status_updates_session_and_backup():
    session_id = "test_toggle_sess_77"
    client.post("/api/playground/chat", json={
        "session_id": session_id,
        "channel": "tiktok",
        "platform": "tiktok",
        "surface": "dm",
        "text": "Ring size 6 US còn hàng không?",
        "history": []
    })

    rate_res = client.post("/api/playground/session/rate", json={
        "session_id": session_id,
        "rating": "fail",
        "channel": "tiktok",
        "platform": "tiktok",
        "surface": "dm",
        "error_category": "sai_san_pham",
        "root_cause": "Nhầm size",
        "suggested_fix": "Fix catalogue",
        "target_file_to_fix": "knowledge/catalogue/products.json",
        "turns": [{"customer_message": "Size 6 US", "bot_reply": "Reply"}]
    })
    case_id = rate_res.json()["case"]["id"]

    # Toggle to fixed
    patch_res = client.patch(f"/api/playground/session/cases/{case_id}/status", json={
        "status": "fixed",
        "fixed_notes": "Đã sửa file products.json chuẩn size US"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["case"]["status"] == "fixed"

    # Verify SQLite session is updated
    sess_res = client.get(f"/api/chat-sessions/{session_id}")
    assert sess_res.json()["rating_data"]["status"] == "fixed"

    # Verify disk backup shows fixed
    backup_dir = get_chat_logs_dir()
    b_json = json.loads((backup_dir / f"{session_id}.json").read_text(encoding="utf-8"))
    assert b_json["rating_data"]["status"] == "fixed"

    b_md = (backup_dir / f"{session_id}.md").read_text(encoding="utf-8")
    assert "🟢 ĐÃ FIX" in b_md


def test_chat_backup_download_and_stats_endpoints():
    stats_res = client.get("/api/chat-backups/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "session_count" in stats
    assert "md_count" in stats
    assert stats["session_count"] >= 1

    # Test downloading JSON backup
    sess_id = "test_auto_backup_sess_99"
    dl_json = client.get(f"/api/chat-backups/{sess_id}?format=json")
    assert dl_json.status_code == 200
    assert "application/json" in dl_json.headers["content-type"]

    # Test downloading Markdown backup
    dl_md = client.get(f"/api/chat-backups/{sess_id}?format=md")
    assert dl_md.status_code == 200
    assert "text/markdown" in dl_md.headers["content-type"]


def test_rating_filter_in_list_chat_sessions():
    # Filter by rating=pass
    res_pass = client.get("/api/chat-sessions?rating=pass")
    assert res_pass.status_code == 200
    for s in res_pass.json()["sessions"]:
        assert s["rating"] == "pass"

    # Filter by rating=fail
    res_fail = client.get("/api/chat-sessions?rating=fail")
    assert res_fail.status_code == 200
    for s in res_fail.json()["sessions"]:
        assert s["rating"] == "fail"
