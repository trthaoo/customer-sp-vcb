import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from src.config import BASE_DIR

DEFAULT_CHAT_LOGS_DIR = Path(BASE_DIR) / "data" / "chat_logs"


def get_chat_logs_dir() -> Path:
    custom_dir = os.environ.get("CHAT_LOGS_DIR")
    if custom_dir:
        p = Path(custom_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    if os.environ.get("PYTEST_CURRENT_TEST"):
        p = Path(BASE_DIR) / ".pytest_cache" / "test_chat_logs"
        p.mkdir(parents=True, exist_ok=True)
        return p
    DEFAULT_CHAT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CHAT_LOGS_DIR


def _escape_md(text: str) -> str:
    if not text:
        return ""
    return str(text).replace("\r\n", "\n")


def format_markdown_transcript(session_data: Dict[str, Any]) -> str:
    sess_id = session_data.get("id") or session_data.get("session_id", "unknown")
    channel = (session_data.get("channel") or "meta").upper()
    platform = (session_data.get("platform") or "ig").upper()
    surface = session_data.get("surface") or "comment"
    user_name = session_data.get("user_name") or "Khách Hàng (Brand Test)"
    created_at = session_data.get("created_at") or datetime.now(timezone.utc).isoformat()
    updated_at = session_data.get("updated_at") or created_at
    rating = session_data.get("rating")
    rating_data = session_data.get("rating_data") or session_data.get("feedback") or {}
    turns = session_data.get("turns") or []

    lines: List[str] = []
    lines.append(f"# 📜 Chat Transcript Backup: {sess_id}")
    lines.append("")
    lines.append(f"- **Kênh / Kịch bản:** `{channel}` / `{platform}` (`{surface}`)")
    lines.append(f"- **Người chat:** {user_name}")
    lines.append(f"- **Khởi tạo:** {created_at}")
    lines.append(f"- **Cập nhật cuối:** {updated_at}")
    lines.append(f"- **Tổng số lượt (Turns):** {len(turns)}")

    # Rating feedback header
    if rating == "pass":
        title = rating_data.get("title") or "Mẫu chuẩn đạt yêu cầu"
        notes = rating_data.get("notes") or ""
        tags = ", ".join(rating_data.get("tags") or [])
        lines.append(f"- **Đánh giá:** 🌟 **ĐẠT - GOLDEN EXAMPLE (Mẫu chuẩn benchmark)**")
        lines.append(f"  - **Tiêu đề:** {title}")
        if notes:
            lines.append(f"  - **Ghi chú:** {notes}")
        if tags:
            lines.append(f"  - **Tags:** `{tags}`")
    elif rating == "fail":
        category = rating_data.get("error_category_label") or rating_data.get("error_category") or "Lỗi chưa phân loại"
        root_cause = rating_data.get("root_cause") or "Chưa phân tích nguyên nhân"
        suggested_fix = rating_data.get("suggested_fix") or "Chưa có đề xuất"
        target_file = rating_data.get("target_file_to_fix") or "Chưa chỉ định"
        status = rating_data.get("status") or "open"
        status_label = "🟢 ĐÃ FIX" if status == "fixed" else "🔴 CHỜ FIX (OPEN)"
        failed_turn = rating_data.get("failed_turn_index")
        failed_turn_str = f"Turn #{failed_turn}" if failed_turn else "Toàn phiên"

        lines.append(f"- **Đánh giá:** ⚠️ **FAIL (CẦN KHẮC PHỤC) [{status_label}]**")
        lines.append(f"  - **Nhóm lỗi:** `{category}` (Lượt lỗi: {failed_turn_str})")
        lines.append(f"  - **Nguyên nhân bot sai:** {root_cause}")
        lines.append(f"  - **Giải pháp / Rule cần sửa:** {suggested_fix}")
        lines.append(f"  - **File kiến thức mục tiêu:** `{target_file}`")
        if rating_data.get("fixed_notes"):
            lines.append(f"  - **Ghi chú đã fix:** {rating_data.get('fixed_notes')}")
    else:
        lines.append(f"- **Đánh giá:** ⚪ *Chưa có đánh giá (Unrated)*")

    lines.append("")
    lines.append("---")
    lines.append("")

    if not turns:
        lines.append("*Chưa có lượt tin nhắn nào.*")
    else:
        for idx, t in enumerate(turns):
            turn_no = t.get("turn_index") or (idx + 1)
            ts = t.get("timestamp") or ""
            cust_msg = t.get("customer_message") or t.get("customerMessage") or t.get("user_message") or ""
            bot_reply = t.get("bot_reply") or t.get("botReply") or t.get("reply") or ""
            badge = t.get("status_badge") or ""
            product = t.get("matched_product")
            if isinstance(product, dict):
                product_name = f"{product.get('name')} ({product.get('id')})"
            else:
                product_name = str(product or "")
            rule = t.get("matched_rule") or ""
            decision = t.get("decision") or ""
            attachment = t.get("attachment_name") or t.get("attachment_url")

            lines.append(f"### 💬 Turn #{turn_no} ({ts})")
            if attachment:
                lines.append(f"- **Đính kèm:** 📎 `{attachment}` ({t.get('attachment_type', 'file')})")
            lines.append(f"- **👤 Khách:** {cust_msg}")
            lines.append(f"- **🤖 Bot ({surface}):**")
            lines.append(f"  > {_escape_md(bot_reply).replace(chr(10), chr(10) + '  > ')}")
            
            diag_items = []
            if badge:
                diag_items.append(f"Badge: `{badge}`")
            if decision:
                diag_items.append(f"Decision: `{decision}`")
            if product_name and product_name != "None":
                diag_items.append(f"SP: `{product_name}`")
            if rule:
                diag_items.append(f"Rule: `{rule}`")
            if diag_items:
                lines.append(f"- **Diagnostics:** {' | '.join(diag_items)}")
            lines.append("")

    return "\n".join(lines)


def save_chat_backup_to_disk(session_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Saves full conversation session to dedicated backup folder:
    1. data/chat_logs/{session_id}.json
    2. data/chat_logs/{session_id}.md
    3. Appends turn to data/chat_logs/all_chats_stream.jsonl
    """
    logs_dir = get_chat_logs_dir()
    sess_id = session_data.get("id") or session_data.get("session_id", "unknown")
    # Clean file name
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in sess_id)

    json_file = logs_dir / f"{safe_name}.json"
    md_file = logs_dir / f"{safe_name}.md"

    # 1. Write formatted JSON
    temp_json = json_file.with_suffix(".tmp")
    temp_json.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_json.replace(json_file)

    # 2. Write Markdown transcript
    md_content = format_markdown_transcript(session_data)
    temp_md = md_file.with_suffix(".tmp")
    temp_md.write_text(md_content, encoding="utf-8")
    temp_md.replace(md_file)

    # 3. Append to JSONL stream
    try:
        stream_entry = {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "session_id": sess_id,
            "channel": session_data.get("channel"),
            "platform": session_data.get("platform"),
            "surface": session_data.get("surface"),
            "turn_count": len(session_data.get("turns") or []),
            "rating": session_data.get("rating"),
            "last_message": session_data.get("last_message"),
            "last_reply": session_data.get("last_reply"),
        }
        stream_file = logs_dir / "all_chats_stream.jsonl"
        with open(stream_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(stream_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Warning: Failed to append to chat stream log: {e}")

    return {
        "json_path": str(json_file),
        "md_path": str(md_file)
    }


def get_chat_backup_stats() -> Dict[str, Any]:
    logs_dir = get_chat_logs_dir()
    json_files = list(logs_dir.glob("*.json"))
    md_files = list(logs_dir.glob("*.md"))
    
    total_turns = 0
    rated_pass = 0
    rated_fail = 0

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            total_turns += len(data.get("turns") or [])
            r = data.get("rating")
            if r == "pass":
                rated_pass += 1
            elif r == "fail":
                rated_fail += 1
        except Exception:
            pass

    return {
        "folder_path": str(logs_dir),
        "session_count": len(json_files),
        "md_count": len(md_files),
        "total_turns": total_turns,
        "rated_pass": rated_pass,
        "rated_fail": rated_fail,
        "unrated": max(0, len(json_files) - rated_pass - rated_fail)
    }
