import io
import os
import base64
import secrets
import csv
import json
import uuid
import shutil
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Literal
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import (
    ZERNIO_WEBHOOK_SECRET,
    BASE_DIR,
    POSTHOG_API_KEY,
    POSTHOG_HOST,
    POSTHOG_ENABLE_RECORDING,
    POSTHOG_PROJECT_ID
)
from src.adapters.zernio import ZernioClient
from src.adapters.model import get_model_adapter
from src.knowledge.loader import get_knowledge_base
from src.storage.database import get_event_store
from src.pipeline.normalizer import MessageNormalizer
from src.pipeline.orchestrator import get_orchestrator
from src.pipeline.media import get_media_processor
from src.models import HandoverStateType, InboundMessage

app = FastAPI(title="Customer Service Auto-Reply Gateway", version="1.0.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Password-protect everything except the health check (Render/UptimeRobot), the
# Zernio webhook (it has its own HMAC check), and public telemetry config. Disabled when BASIC_AUTH_PASS is unset.
_AUTH_PASS = os.getenv("BASIC_AUTH_PASS", "")
_AUTH_HEADER = "Basic " + base64.b64encode(f"{os.getenv('BASIC_AUTH_USER', '')}:{_AUTH_PASS}".encode()).decode()
_PUBLIC_PATHS = {"/api/health", "/webhooks/zernio", "/api/posthog/config"}

def _inject_posthog_runtime(html_content: str) -> str:
    """Inject runtime PostHog configuration script tag into HTML head."""
    cfg = {
        "apiKey": POSTHOG_API_KEY,
        "apiHost": POSTHOG_HOST,
        "enableRecording": POSTHOG_ENABLE_RECORDING,
        "projectId": POSTHOG_PROJECT_ID
    }
    script = f'<script>window.__POSTHOG_CONFIG__ = {json.dumps(cfg)};</script>'
    if "</head>" in html_content:
        return html_content.replace("</head>", f"  {script}\n</head>", 1)
    return script + html_content

@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if _AUTH_PASS and request.url.path not in _PUBLIC_PATHS:
        given = request.headers.get("authorization", "").encode()
        if not secrets.compare_digest(given, _AUTH_HEADER.encode()):
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="vcb"'})
    return await call_next(request)

class HandoverStateUpdate(BaseModel):
    state: HandoverStateType
    notes: Optional[str] = ""

class PlaygroundChatRequest(BaseModel):
    channel: Literal["meta", "tiktok"]
    platform: Literal["ig", "fb", "tiktok"]
    surface: Literal["comment", "dm"]
    text: str
    post_context: Optional[str] = None
    media_cache_id: Optional[str] = None
    thread_id: Optional[str] = None
    session_id: Optional[str] = None
    user_name: Optional[str] = "Khách Hàng (Brand Test)"
    history: List[Dict[str, str]] = Field(default_factory=list)
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None  # 'image', 'video', 'link'
    attachment_name: Optional[str] = None
    chat_media_cache_id: Optional[str] = None

class ExportTurnItem(BaseModel):
    turn_index: int
    timestamp: str
    channel: str
    platform: str
    surface: str
    post_context: Optional[str] = ""
    customer_message: str
    bot_reply: str
    status_badge: str
    matched_product: Optional[str] = ""
    matched_rule: Optional[str] = ""
    files_used: Optional[List[str]] = Field(default_factory=list)
    missing_fields: Optional[List[str]] = Field(default_factory=list)
    reason: Optional[str] = ""
    example_good_reply: Optional[str] = ""
    decision: Optional[str] = ""
    flag: Optional[str] = ""

from src.storage.test_cases import get_test_case_manager

class SessionRatingRequest(BaseModel):
    session_id: str
    rating: Literal["pass", "fail"]
    channel: str = "meta"
    platform: str = "ig"
    surface: str = "comment"
    turns: List[Dict[str, Any]] = Field(default_factory=list)
    title: Optional[str] = None
    notes: Optional[str] = ""
    tags: Optional[List[str]] = Field(default_factory=list)
    error_category: Optional[str] = None
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    target_file_to_fix: Optional[str] = ""
    failed_turn_index: Optional[int] = None
    posthog_replay_url: Optional[str] = None

class CaseStatusUpdateRequest(BaseModel):
    status: Literal["open", "fixed"]
    fixed_notes: Optional[str] = ""

class PlaygroundExportRequest(BaseModel):
    session_id: str
    turns: List[ExportTurnItem] = Field(default_factory=list)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "vcb-concierge"}

@app.post("/webhooks/zernio")
async def handle_zernio_webhook(
    request: Request,
    x_zernio_signature: Optional[str] = Header(None, alias="X-Zernio-Signature"),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature")
):
    raw_body = await request.body()
    sig = x_zernio_signature or x_webhook_signature

    client = ZernioClient()
    if not client.verify_webhook_signature(raw_body, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    inbound = MessageNormalizer.normalize_webhook(payload, env="prod", source="live")
    if not inbound:
        # Ignored event or outgoing echo
        return {"status": "ignored"}

    orchestrator = get_orchestrator()
    result = orchestrator.process(inbound)

    # Save to persistent chat sessions
    try:
        store = get_event_store()
        sess_id = inbound.thread_id or f"thread_{inbound.user_id or inbound.id}"
        turn_data = {
            "turn_index": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_message": inbound.text,
            "bot_reply": result.draft_reply,
            "decision": result.decision,
            "flag": result.flag,
            "status_badge": result.status_badge,
            "matched_product": result.matched_product.name if result.matched_product else None,
            "matched_rule": result.matched_rule or result.matched_edge_case,
            "intent": result.intent,
            "knowledge_files": result.knowledge_files,
            "reply_sent": result.reply_sent
        }
        store.save_session_turn(
            session_id=sess_id,
            channel=inbound.channel,
            platform=inbound.platform,
            surface=inbound.surface,
            user_message=inbound.text,
            reply=result.draft_reply,
            turn_data=turn_data,
            thread_id=inbound.thread_id,
            user_id=inbound.user_id,
            user_name=inbound.user_name,
            status="handover" if result.flag == "handover" else "active"
        )
    except Exception as e:
        print(f"Warning: Failed to log chat session turn: {e}")

    return {
        "status": "processed",
        "event_id": inbound.id,
        "decision": result.decision,
        "flag": result.flag,
        "reply_sent": result.reply_sent
    }

@app.get("/api/metrics")
async def get_metrics(
    channel: str = Query("meta", pattern="^(meta|tiktok)$"),
    platform: Optional[str] = Query("all", pattern="^(all|ig|fb|tiktok)$")
):
    store = get_event_store()
    data = store.get_metrics(channel=channel, platform_filter=platform)
    return data

@app.get("/api/handover")
async def get_handover_queue(
    channel: Optional[str] = Query(None),
    state: Optional[str] = Query("all")
):
    store = get_event_store()
    data = store.get_handover_queue(channel=channel, state_filter=state)
    return {"queue": data}

@app.get("/api/handover/badge")
async def get_handover_badge():
    store = get_event_store()
    badge_count = store.get_handover_badge_count()
    return {"badge_count": badge_count}

@app.post("/api/handover/{event_id}/state")
async def update_handover_state(event_id: str, body: HandoverStateUpdate):
    store = get_event_store()
    if body.state == "resolved":
        success = store.resolve_handover(event_id, operator_notes=body.notes or "")
    else:
        success = store.update_handover_state(event_id, body.state)

    if not success:
        raise HTTPException(status_code=404, detail="Handover case not found or not updateable")
    return {"success": True, "event_id": event_id, "new_state": body.state}

@app.get("/api/events")
async def get_events(
    channel: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    limit: int = Query(50, le=100)
):
    store = get_event_store()
    events = store.get_recent_events(channel=channel, platform=platform, limit=limit)
    return {"events": events}

@app.get("/api/chat-sessions")
async def list_chat_sessions(
    channel: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    rating: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    store = get_event_store()
    sessions = store.get_chat_sessions(
        channel=channel, platform=platform, rating=rating, search=search, limit=limit, offset=offset
    )
    return {"sessions": sessions, "count": len(sessions)}

@app.get("/api/chat-sessions/{session_id}")
async def get_chat_session_detail(session_id: str):
    store = get_event_store()
    sess = store.get_chat_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return sess

@app.delete("/api/chat-sessions/{session_id}")
async def delete_chat_session(session_id: str):
    store = get_event_store()
    success = store.delete_chat_session(session_id)
    broadcast_sse({
        "type": "chat_session_deleted",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return {"success": success}

@app.get("/api/chat-backups/stats")
async def get_chat_backup_statistics():
    """Returns disk backup statistics from data/chat_logs/."""
    from src.storage.chat_backup import get_chat_backup_stats
    return get_chat_backup_stats()

@app.get("/api/chat-backups/{session_id}")
async def download_chat_backup(session_id: str, format: Literal["json", "md"] = "json"):
    """Downloads disk backup of session in JSON or Markdown format."""
    from src.storage.chat_backup import get_chat_logs_dir, save_chat_backup_to_disk
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in session_id)
    target_file = get_chat_logs_dir() / f"{safe_name}.{format}"
    if not target_file.exists():
        store = get_event_store()
        sess = store.get_chat_session(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên chat này")
        save_chat_backup_to_disk(sess)
    
    media_type = "application/json" if format == "json" else "text/markdown; charset=utf-8"
    return FileResponse(
        target_file,
        media_type=media_type,
        filename=f"chat_backup_{safe_name}.{format}"
    )

_sse_subscribers: List[asyncio.Queue] = []

def broadcast_sse(event_data: dict):
    for q in list(_sse_subscribers):
        try:
            q.put_nowait(event_data)
        except Exception:
            pass

@app.get("/api/events/stream")
async def stream_events(request: Request):
    """Server-Sent Events stream for real-time live updates without full page reload."""
    q: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.append(q)

    async def event_generator():
        store = get_event_store()
        last_id = ""
        try:
            # Yield initial connection confirmation
            init_msg = json.dumps({"type": "connected", "timestamp": datetime.now(timezone.utc).isoformat()})
            yield f"data: {init_msg}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
                    recent = store.get_recent_events(limit=1)
                    if recent:
                        latest = recent[0]
                        if latest["id"] != last_id:
                            last_id = latest["id"]
                            yield f"data: {json.dumps(latest)}\n\n"
        finally:
            if q in _sse_subscribers:
                _sse_subscribers.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/api/posthog/config")
async def get_posthog_config():
    """Returns public PostHog telemetry and recording config."""
    return {
        "apiKey": POSTHOG_API_KEY,
        "apiHost": POSTHOG_HOST,
        "enableRecording": POSTHOG_ENABLE_RECORDING,
        "projectId": POSTHOG_PROJECT_ID,
        "enabled": bool(POSTHOG_API_KEY)
    }

@app.get("/playground")
async def playground_page():
    playground_file = STATIC_DIR / "playground.html"
    if playground_file.exists():
        with open(playground_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=_inject_posthog_runtime(f.read()))
    return HTMLResponse("<h3>Playground UI not installed yet.</h3>")

@app.get("/api/playground/media/{session_id}/{filename}")
async def get_playground_media(session_id: str, filename: str):
    processor = get_media_processor()
    safe_session = re.sub(r'[^a-zA-Z0-9_\-]', '_', session_id)
    safe_file = Path(filename).name
    file_path = processor.cache_dir / safe_session / safe_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")
    ext = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    return FileResponse(file_path, media_type=media_types.get(ext, "application/octet-stream"))

@app.post("/api/playground/upload_media")
async def playground_upload_media(
    files: List[UploadFile] = File(...)
):
    processor = get_media_processor()
    session_id = f"upload_{uuid.uuid4().hex[:10]}"
    upload_temp_dir = processor.cache_dir / session_id
    upload_temp_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: List[Path] = []
    for f in files:
        # Keep only the base name: the client controls filename and could send "../../x".
        file_path = upload_temp_dir / (Path(f.filename or "").name or "upload.raw")
        with open(file_path, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved_paths.append(file_path)

    frames, context_missing = processor.process_media(
        post_id=session_id,
        local_files=saved_paths
    )

    primary_file = saved_paths[0] if saved_paths else None
    ext = primary_file.suffix.lower() if primary_file else ""
    is_video = ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")
    media_type = "video" if is_video else "image"
    preview_url = f"/api/playground/media/{session_id}/{primary_file.name}" if primary_file else None

    return {
        "media_cache_id": session_id,
        "media_type": media_type,
        "filename": primary_file.name if primary_file else "upload",
        "preview_url": preview_url,
        "frame_count": len(frames),
        "timestamps": [f.label for f in frames],
        "context_missing": context_missing,
        "frames": [
            {
                "label": f.label,
                "timestamp": f.timestamp,
                "mime_type": f.mime_type,
                "base64_data": f.base64_data
            }
            for f in frames
        ]
    }

@app.post("/api/playground/chat")
async def playground_chat(body: PlaygroundChatRequest):
    orchestrator = get_orchestrator()
    processor = get_media_processor()
    msg_id = f"brand_test_{int(datetime.now(timezone.utc).timestamp()*1000)}"

    frames = []
    context_missing = False

    # 1. Post media context (if provided in top config bar)
    if body.media_cache_id:
        post_frames, c_missing = processor.process_media(post_id=body.media_cache_id)
        frames.extend(post_frames)
        if c_missing:
            context_missing = True
    elif body.surface == "comment":
        context_missing = True

    # 2. Chat message media attachment (customer sends photo/video/link in chat turn)
    if body.chat_media_cache_id:
        chat_frames, _ = processor.process_media(post_id=body.chat_media_cache_id)
        if chat_frames:
            frames.extend(chat_frames)
            context_missing = False
    elif body.attachment_url and body.attachment_type in ("image", "video"):
        chat_frames, _ = processor.process_media(
            media_url=body.attachment_url,
            media_type=body.attachment_type
        )
        if chat_frames:
            frames.extend(chat_frames)
            context_missing = False

    # 3. Handle link in text: if user provided link attachment, ensure text references it
    effective_text = body.text
    if body.attachment_url and body.attachment_type == "link":
        if body.attachment_url not in effective_text:
            effective_text = f"{effective_text} {body.attachment_url}".strip()

    inbound = InboundMessage(
        id=msg_id,
        platform=body.platform,
        channel=body.channel,
        surface=body.surface,
        text=effective_text,
        post_context=body.post_context,
        media_url=body.attachment_url,
        media_type=body.attachment_type,
        frames=frames,
        context_missing=context_missing,
        thread_id=body.thread_id or f"th_{int(datetime.now(timezone.utc).timestamp())}",
        user_id="brand_tester_01",
        user_name=body.user_name or "Khách Hàng (Brand Test)",
        env="test",
        source="brand_test",
        history=body.history
    )
    result = orchestrator.process(inbound)

    # Save turn to chat_sessions store
    try:
        store = get_event_store()
        sess_id = body.session_id or body.thread_id or f"sess_{inbound.id}"
        turn_idx = (len(body.history) // 2) + 1
        turn_data = {
            "turn_index": turn_idx,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_message": body.text,
            "attachment_url": body.attachment_url,
            "attachment_type": body.attachment_type,
            "attachment_name": body.attachment_name,
            "chat_media_cache_id": body.chat_media_cache_id,
            "bot_reply": result.draft_reply,
            "decision": result.decision,
            "flag": result.flag,
            "status_badge": result.status_badge,
            "matched_product": result.matched_product.name if result.matched_product else None,
            "matched_rule": result.matched_rule or result.matched_edge_case,
            "intent": result.intent,
            "knowledge_files": result.knowledge_files,
            "missing_fields": result.missing_fields,
            "attached_image_url": result.attached_image_url,
            "model_used": result.model_used,
            "attached_frames_count": len(frames)
        }
        store.save_session_turn(
            session_id=sess_id,
            channel=body.channel,
            platform=body.platform,
            surface=body.surface,
            user_message=body.text,
            reply=result.draft_reply,
            turn_data=turn_data,
            thread_id=body.thread_id or sess_id,
            user_id="brand_tester_01",
            user_name=body.user_name or "Khách Hàng (Brand Test)",
            status="handover" if result.flag == "handover" else "active"
        )
        broadcast_sse({
            "type": "chat_session_updated",
            "session_id": sess_id,
            "channel": body.channel,
            "platform": body.platform,
            "last_message": body.text,
            "last_reply": result.draft_reply,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"Warning: Failed to save playground session turn: {e}")

    return {
        "id": inbound.id,
        "reply": result.draft_reply,
        "decision": result.decision,
        "flag": result.flag,
        "status_badge": result.status_badge,
        "needs_human": result.needs_human,
        "escalate_reason": result.escalate_reason,
        "matched_product": result.matched_product.model_dump() if result.matched_product else None,
        "ambiguous_products": [p.model_dump() for p in result.ambiguous_products],
        "matched_rule": result.matched_rule,
        "matched_edge_case": result.matched_edge_case,
        "intent": result.intent,
        "knowledge_files": result.knowledge_files,
        "knowledge_facts": result.knowledge_facts,
        "retrieved_chunks": result.retrieved_chunks,
        "missing_fields": result.missing_fields,
        "example_good_reply": result.example_good_reply,
        "model_called": result.model_called,
        "model_used": result.model_used,
        "reply_sent": result.reply_sent,
        "attached_image_url": result.attached_image_url,
        # Chat turn attachment info
        "attachment_url": body.attachment_url,
        "attachment_type": body.attachment_type,
        "attachment_name": body.attachment_name,
        "attached_frames_count": len(frames),
        # Panel & Visual Diagnostics
        "caption": result.caption,
        "frame_count": result.frame_count,
        "frame_timestamps": result.frame_timestamps,
        "visual_product_guess": result.visual_product_guess,
        "catalogue_id_matched": result.catalogue_id_matched,
        "frame_used": result.frame_used,
        "context_missing": result.context_missing,
        "vision_unsupported": result.vision_unsupported,
        "short_reason": result.short_reason,
        "frames": [
            {
                "label": f.label,
                "timestamp": f.timestamp,
                "base64_data": f.base64_data
            }
            for f in result.frames
        ]
    }

@app.get("/api/playground/edge_cases")
async def get_playground_edge_cases(channel: Literal["meta", "tiktok"] = "meta"):
    kb = get_knowledge_base()
    cases = kb.meta_edge_cases if channel == "meta" else kb.tiktok_edge_cases
    return {
        "channel": channel,
        "edge_cases": [ec.model_dump() for ec in cases]
    }

@app.get("/api/playground/config")
async def get_playground_config():
    adapter = get_model_adapter()
    return adapter.get_info()

@app.get("/api/playground/products")
async def get_playground_products():
    kb = get_knowledge_base()
    return {"products": [p.model_dump() for p in kb.products]}

@app.post("/api/playground/export_csv")
async def export_playground_csv(body: PlaygroundExportRequest):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Turn #",
        "Timestamp",
        "Channel",
        "Platform",
        "Surface",
        "Post Context",
        "Customer Message (Brand)",
        "Bot Reply (Page Staff)",
        "Status Badge",
        "Matched Product",
        "Matched Rule / Edge Case",
        "Files & Chunks Used",
        "Missing Fields",
        "Decision Reason",
        "Example Good Reply (Sample)",
        "Decision",
        "Flag"
    ])
    for t in body.turns:
        writer.writerow([
            t.turn_index,
            t.timestamp,
            t.channel,
            t.platform,
            t.surface,
            t.post_context or "",
            t.customer_message,
            t.bot_reply,
            t.status_badge,
            t.matched_product or "",
            t.matched_rule or "",
            "; ".join(t.files_used or []),
            "; ".join(t.missing_fields or []),
            t.reason or "",
            t.example_good_reply or "",
            t.decision or "",
            t.flag or ""
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename = f"playground_session_{body.session_id}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.post("/api/playground/session/rate")
async def rate_playground_session(body: SessionRatingRequest):
    manager = get_test_case_manager()
    store = get_event_store()
    if body.rating == "pass":
        record = manager.save_golden_example(
            session_id=body.session_id,
            channel=body.channel,
            platform=body.platform,
            surface=body.surface,
            turns=body.turns,
            title=body.title,
            notes=body.notes or "",
            tags=body.tags
        )
        rating_data = {
            "case_id": record.get("id"),
            "rating": "pass",
            "title": record.get("title"),
            "notes": record.get("notes"),
            "tags": record.get("tags") or [],
            "rated_at": record.get("created_at"),
            "turn_count": len(body.turns),
            "posthog_replay_url": body.posthog_replay_url
        }
        store.update_session_rating(body.session_id, "pass", rating_data)
        broadcast_sse({
            "type": "case_rated",
            "session_id": body.session_id,
            "rating": "pass",
            "case": record,
            "rating_data": rating_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return {
            "success": True,
            "rating": "pass",
            "message": "Đã lưu phiên chat thành Golden Example chuẩn!",
            "case": record
        }
    else:
        if not body.error_category:
            raise HTTPException(status_code=400, detail="Vui lòng chọn loại lỗi (error_category) cho case không đạt")
        if not body.root_cause or not body.root_cause.strip():
            raise HTTPException(status_code=400, detail="Vui lòng cung cấp phân tích nguyên nhân không đạt (root_cause)")
        
        record = manager.save_failed_case(
            session_id=body.session_id,
            channel=body.channel,
            platform=body.platform,
            surface=body.surface,
            turns=body.turns,
            error_category=body.error_category,
            root_cause=body.root_cause,
            suggested_fix=body.suggested_fix or "",
            target_file_to_fix=body.target_file_to_fix or "",
            failed_turn_index=body.failed_turn_index,
            notes=body.notes or ""
        )
        rating_data = {
            "case_id": record.get("id"),
            "rating": "fail",
            "error_category": record.get("error_category"),
            "error_category_label": record.get("error_category_label"),
            "failed_turn_index": record.get("failed_turn_index"),
            "root_cause": record.get("root_cause"),
            "suggested_fix": record.get("suggested_fix"),
            "target_file_to_fix": record.get("target_file_to_fix"),
            "status": record.get("status", "open"),
            "fixed_at": record.get("fixed_at"),
            "fixed_notes": record.get("fixed_notes"),
            "notes": record.get("notes"),
            "rated_at": record.get("created_at"),
            "turn_count": len(body.turns),
            "posthog_replay_url": body.posthog_replay_url
        }
        store.update_session_rating(body.session_id, "fail", rating_data)
        broadcast_sse({
            "type": "case_rated",
            "session_id": body.session_id,
            "rating": "fail",
            "case": record,
            "rating_data": rating_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return {
            "success": True,
            "rating": "fail",
            "message": "Đã ghi nhận Case Lỗi cùng phân tích nguyên nhân và giải pháp!",
            "case": record
        }

@app.get("/api/playground/session/cases")
async def get_playground_cases():
    manager = get_test_case_manager()
    return manager.get_all_cases()

@app.patch("/api/playground/session/cases/{case_id}/status")
async def update_failed_case_status(case_id: str, body: CaseStatusUpdateRequest):
    manager = get_test_case_manager()
    updated = manager.update_failed_case_status(case_id, body.status, body.fixed_notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy case lỗi với ID này")

    sess_id = updated.get("session_id")
    if sess_id:
        store = get_event_store()
        sess = store.get_chat_session(sess_id)
        if sess:
            rdata = sess.get("rating_data") or {}
            rdata["status"] = body.status
            rdata["fixed_at"] = updated.get("fixed_at")
            rdata["fixed_notes"] = body.fixed_notes or ""
            store.update_session_rating(sess_id, "fail", rdata)

    broadcast_sse({
        "type": "case_updated",
        "case_id": case_id,
        "session_id": sess_id,
        "status": body.status,
        "case": updated,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return {"success": True, "case": updated}

@app.delete("/api/playground/session/cases/{case_type}/{case_id}")
async def delete_playground_case(case_type: Literal["golden", "failed"], case_id: str):
    manager = get_test_case_manager()
    cases = manager.get_all_cases()
    target_list = cases["golden_examples"] if case_type == "golden" else cases["failed_cases"]
    matching = next((c for c in target_list if c.get("id") == case_id), None)
    sess_id = matching.get("session_id") if matching else None

    deleted = manager.delete_case(case_type, case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy case cần xóa")

    if sess_id:
        store = get_event_store()
        store.update_session_rating(sess_id, None, {})

    broadcast_sse({
        "type": "case_deleted",
        "case_type": case_type,
        "case_id": case_id,
        "session_id": sess_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return {"success": True, "case_id": case_id}

class RagSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    category: Optional[str] = None
    channel: Optional[str] = None
    min_score: Optional[float] = 0.3

class RagReindexRequest(BaseModel):
    force: Optional[bool] = False

@app.get("/api/rag/stats")
async def get_rag_stats():
    from src.knowledge.rag_service import get_rag_service
    rag = get_rag_service()
    return rag.get_stats()

@app.post("/api/rag/reindex")
async def reindex_rag(body: Optional[RagReindexRequest] = None):
    from src.knowledge.rag_service import get_rag_service
    rag = get_rag_service()
    force = body.force if body else False
    result = rag.index_all(force=force)
    return result

@app.post("/api/rag/search")
async def search_rag(body: RagSearchRequest):
    from src.knowledge.rag_service import get_rag_service
    rag = get_rag_service()
    results = rag.search(
        query=body.query,
        top_k=body.top_k or 5,
        category=body.category,
        channel=body.channel,
        min_score=body.min_score or 0.3
    )
    return {"query": body.query, "results": results, "count": len(results)}

@app.get("/")
@app.get("/dashboard")
@app.get("/logs")
@app.get("/sessions")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=_inject_posthog_runtime(f.read()))
    return HTMLResponse("<h3>Customer Service Auto-Reply Gateway</h3><p>Dashboard UI not installed yet.</p>")
