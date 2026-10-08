import pytest
import re
from pathlib import Path
from src.models import Product, InboundMessage, EventRecord
from src.knowledge.loader import KnowledgeBase, strip_example_blocks
from src.storage.database import EventStore
from src.pipeline.matcher import ProductMatcher
from src.pipeline.intent import IntentClassifier
from src.pipeline.engine import FunnelEngine
from src.pipeline.composer import ReplyComposer
from src.pipeline.orchestrator import PipelineOrchestrator
from src.adapters.zernio import ZernioClient
from src.config import BASE_DIR, KNOWLEDGE_DIR

@pytest.fixture
def test_kb(tmp_path):
    kb = KnowledgeBase(KNOWLEDGE_DIR)
    return kb

@pytest.fixture
def test_store(tmp_path):
    db_file = tmp_path / "test_events.db"
    return EventStore(str(db_file))

# 1. Missing price does not invent a number
def test_missing_price_does_not_invent_a_number(test_kb, test_store):
    prod_no_price = Product(
        id="SP_TEST_NOPRICE",
        name="Nhẫn Đá Thạch Anh",
        aliases=["nhẫn thạch anh"],
        price=None,
        material="Bạc S925",
        in_stock=True
    )
    test_kb.products = [prod_no_price]
    
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)
    inbound = InboundMessage(
        id="dry_test_noprice",
        platform="ig",
        channel="meta",
        surface="comment",
        text="cho em xin giá nhẫn thạch anh với ạ",
        source="dry_run"
    )
    
    result = orchestrator.process(inbound)
    
    assert result.decision == "fallback"
    assert result.flag == "handover"
    assert result.needs_human is True
    # Ensure reply does not contain numbers / invented prices
    assert not re.search(r'\d+[\.,]?\d*\s*(?:đ|vnd|\$)', result.draft_reply, re.IGNORECASE)
    assert result.draft_reply == test_kb.default_fallback

# 2. Meta rule does not fire on TikTok
def test_meta_rule_does_not_fire_on_tiktok(test_kb, test_store):
    prod = Product(
        id="SP_TEST_TIKTOK",
        name="Vòng Tay Chuông Bạc",
        aliases=["vòng tay chuông"],
        price=350000,
        currency="VND",
        material="Bạc S925",
        in_stock=True
    )
    test_kb.products = [prod]
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)

    inbound = InboundMessage(
        id="dry_test_tiktok",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="vòng tay chuông bao nhiêu tiền vậy shop",
        source="dry_run"
    )

    result = orchestrator.process(inbound)

    assert result.inbound.channel == "tiktok"
    # Matched rule MUST be a TikTok rule or None, NEVER a Meta rule!
    if result.matched_rule:
        assert result.matched_rule.startswith("tiktok_")
        assert not result.matched_rule.startswith("meta_")

# 3. Edge case beats a general rule
def test_edge_case_beats_a_general_rule(test_kb, test_store):
    prod = Product(
        id="SP_TEST_EDGE",
        name="Nhẫn Bạc Trơn",
        aliases=["nhẫn trơn"],
        price=200000,
        material="Bạc",
        in_stock=True
    )
    test_kb.products = [prod]
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)

    # Message contains both product name/price inquiry AND angry complaint/scam trigger
    inbound = InboundMessage(
        id="dry_test_edge",
        platform="fb",
        channel="meta",
        surface="comment",
        text="nhẫn trơn này shop lừa đảo à hàng nhận bị hỏng hoàn tiền cho tôi gấp",
        source="dry_run"
    )

    result = orchestrator.process(inbound)

    assert result.matched_edge_case is not None
    assert "angry" in result.matched_edge_case or "scam" in result.matched_edge_case
    assert result.decision == "escalate"
    assert result.flag == "handover"
    assert result.needs_human is True

# 4. Empty knowledge returns fallback + handover, reply_sent false when HOLD_ON_HANDOVER=true
def test_empty_knowledge_returns_fallback_and_handover(test_kb, test_store):
    # Ensure policies.shipping is empty
    test_kb.policies["shipping"] = ""
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)

    inbound = InboundMessage(
        id="dry_test_empty_know",
        platform="ig",
        channel="meta",
        surface="dm",
        text="shop có giao hàng về Đà Nẵng không, phí ship thế nào ạ",
        source="dry_run"
    )

    result = orchestrator.process(inbound)

    assert result.decision == "fallback"
    assert result.flag == "handover"
    assert result.needs_human is True
    assert result.reply_sent is False

# 5. Two product aliases match => no guessed product
def test_two_product_aliases_match_no_guessed_product(test_kb, test_store):
    p1 = Product(
        id="SP01",
        name="Nhẫn Bạc Hoa Tuyết",
        aliases=["nhẫn hoa", "hoa tuyết"],
        price=500000,
        in_stock=True
    )
    p2 = Product(
        id="SP02",
        name="Nhẫn Bạc Hoa Sen",
        aliases=["nhẫn hoa", "hoa sen"],
        price=600000,
        in_stock=True
    )
    test_kb.products = [p1, p2]
    matcher = ProductMatcher(test_kb.products)

    matched, ambiguous = matcher.match("mẫu nhẫn hoa này giá sao ạ")

    # Ambiguous match: should not guess
    assert matched is None
    assert len(ambiguous) == 2

    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)
    inbound = InboundMessage(
        id="dry_test_ambig",
        platform="ig",
        channel="meta",
        surface="dm",
        text="mẫu nhẫn hoa này giá sao ạ",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_product is None
    assert result.flag == "handover"

# 6. EXAMPLE_DELETE_ME text never appears in a reply
def test_example_delete_me_never_appears_in_reply(test_kb, test_store):
    # Collect all text inside EXAMPLE_DELETE_ME across all knowledge markdown files
    example_snippets = []
    for md_file in KNOWLEDGE_DIR.glob("**/*.md"):
        with open(md_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        matches = re.findall(r'<!--\s*EXAMPLE_DELETE_ME\s*-->\s*(.*?)\s*<!--\s*/EXAMPLE_DELETE_ME\s*-->', content, re.DOTALL)
        for m in matches:
            clean_m = m.strip()
            if clean_m:
                example_snippets.append(clean_m)

    assert len(example_snippets) > 0, "There should be EXAMPLE_DELETE_ME blocks in knowledge files"

    prod = Product(
        id="SP_SAMPLE",
        name="Dây Chuyền Trái Tim",
        aliases=["dây chuyền tim"],
        price=450000,
        currency="VND",
        material="Bạc Ý 925",
        in_stock=True
    )
    test_kb.products = [prod]
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)

    test_queries = [
        "dây chuyền tim giá nhiêu ạ",
        "dây chuyền tim chất liệu gì vậy shop",
        "shop có ship toàn quốc không",
        "chính sách bảo hành như thế nào",
        "shop lừa đảo à",
        "chào shop"
    ]

    for q in test_queries:
        inbound = InboundMessage(
            id=f"dry_test_ex_{abs(hash(q))}",
            platform="ig",
            channel="meta",
            surface="comment",
            text=q,
            source="dry_run"
        )
        res = orchestrator.process(inbound)
        reply = res.draft_reply
        for snippet in example_snippets:
            # None of the example snippets should appear in the reply
            assert snippet not in reply
            # Substrings of the snippet (like specific old addresses or fake old promos) should not appear
            for line in snippet.splitlines():
                line = line.strip().strip('"').strip("'")
                if len(line) > 10 and not line.startswith("```"):
                    assert line not in reply

# 7. Dry-run does not increase dashboard reply_count
def test_dry_run_does_not_increase_dashboard_reply_count(test_kb, test_store):
    m_before = test_store.get_metrics(channel="meta")
    initial_inbound = m_before["inbound_count"]
    initial_replied = m_before["auto_replied_count"]

    prod = Product(
        id="SP_DRY",
        name="Lắc Tay Vàng",
        aliases=["lắc tay vàng"],
        price=1200000,
        currency="VND",
        material="Vàng",
        in_stock=True
    )
    test_kb.products = [prod]
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)

    # Process message with source="dry_run"
    inbound = InboundMessage(
        id="dry_run_9999",
        platform="ig",
        channel="meta",
        surface="comment",
        text="giá lắc tay vàng bao nhiêu",
        source="dry_run"
    )
    res = orchestrator.process(inbound)

    m_after = test_store.get_metrics(channel="meta")
    assert m_after["inbound_count"] == initial_inbound
    assert m_after["auto_replied_count"] == initial_replied

# 8. Test handover does not appear on the Handover tab
def test_test_handover_does_not_appear_on_handover_tab(test_kb, test_store):
    # Insert a test handover event
    test_event = EventRecord(
        id="test_handover_item_01",
        ts="2026-10-07T12:00:00Z",
        env="prod",
        source="test",  # NOT live
        channel="meta",
        platform="ig",
        surface="dm",
        intent="complaint_angry",
        product_id=None,
        matched_rule=None,
        knowledge_files=[],
        decision="escalate",
        flag="handover",
        handover_state="open",
        reply_sent=False,
        user_message="Test message from unit test"
    )
    test_store.insert_event(test_event)

    queue = test_store.get_handover_queue()
    ids_in_queue = [item["id"] for item in queue]
    assert "test_handover_item_01" not in ids_in_queue

# 9. AUTO_SEND=false never calls Zernio send
def test_auto_send_false_never_calls_zernio_send(test_kb, test_store):
    prod = Product(
        id="SP_AUTOSEND",
        name="Hoa Tai Bạc Ngọc Trai",
        aliases=["hoa tai ngọc trai"],
        price=400000,
        currency="VND",
        material="Bạc và ngọc trai",
        in_stock=True
    )
    test_kb.products = [prod]

    # Client with auto_send=False
    zernio_client = ZernioClient(auto_send=False)
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store, zernio=zernio_client)

    inbound = InboundMessage(
        id="live_msg_001",
        platform="ig",
        channel="meta",
        surface="comment",
        post_id="post_12345",
        text="hoa tai ngọc trai giá bn ạ",
        source="live"
    )

    result = orchestrator.process(inbound)

    # Even though it's auto_reply decision and live source, reply_sent is False because AUTO_SEND=False
    assert result.decision == "auto_reply"
    assert result.flag == "auto_reply"
    assert result.reply_sent is False

# 10. Webhook normalizer extracts media URL, carousel media, and sets context_missing if absent
def test_normalizer_webhook_media_and_context_missing():
    from src.pipeline.normalizer import MessageNormalizer

    # Case A: Payload WITH mediaUrl
    payload_with_media = {
        "event": "comment.received",
        "id": "evt_001",
        "comment": {
            "id": "cmt_001",
            "platform": "instagram",
            "text": "cái này đẹp quá shop",
            "postId": "post_media_01",
            "postCaption": "BST Nhẫn Kim Cô",
            "mediaUrl": "https://cdn.example.com/video.mp4",
            "mediaType": "video",
            "author": {"id": "user_1", "name": "Ngọc Mai"}
        }
    }
    # Mock media extraction to avoid actual network download
    from src.pipeline.media import get_media_processor
    from src.models import MediaFrame
    processor = get_media_processor()
    orig_process = processor.process_media
    processor.process_media = lambda **kwargs: ([MediaFrame(timestamp=0.0, label="t=0.0s")], False)
    try:
        inbound_with = MessageNormalizer.normalize_webhook(payload_with_media)
        assert inbound_with.media_url == "https://cdn.example.com/video.mp4"
        assert inbound_with.post_context == "BST Nhẫn Kim Cô"
        assert inbound_with.context_missing is False
        assert len(inbound_with.frames) == 1
    finally:
        processor.process_media = orig_process

    # Case B: Payload WITHOUT mediaUrl (No URL = mark context_missing)
    payload_no_media = {
        "event": "comment.received",
        "id": "evt_002",
        "comment": {
            "id": "cmt_002",
            "platform": "instagram",
            "text": "cái này bao nhiêu tiền",
            "postId": "post_no_media_02",
            "author": {"id": "user_2", "name": "Thanh Tùng"}
        }
    }
    inbound_without = MessageNormalizer.normalize_webhook(payload_no_media)
    assert inbound_without.media_url is None
    assert inbound_without.context_missing is True
    assert len(inbound_without.frames) == 0

# 11. MediaProcessor caching by post_id
def test_media_processor_cache_by_post_id(tmp_path):
    from PIL import Image
    from src.pipeline.media import MediaProcessor

    cache_dir = tmp_path / "media_cache"
    processor = MediaProcessor(cache_dir=cache_dir)

    test_img = tmp_path / "slide.jpg"
    Image.new("RGB", (300, 300), color="green").save(test_img, "JPEG")

    # First call: process from local file with post_id
    frames_1, missing_1 = processor.process_media(
        post_id="post_test_cache_001",
        local_files=[test_img]
    )
    assert len(frames_1) == 1
    assert missing_1 is False

    cached_folder = cache_dir / "post_test_cache_001"
    assert cached_folder.exists()
    assert (cached_folder / "frame_00.jpg").exists()

    # Second call: with same post_id (no local files needed, loads from cache!)
    frames_2, missing_2 = processor.process_media(post_id="post_test_cache_001")
    assert len(frames_2) == 1
    assert missing_2 is False
    assert frames_2[0].label == "Slide 1" or frames_2[0].label == "t=0.0s"

# 12. No script / template: reply_guide is a constraint, not the sentence to send
def test_no_script_canned_reply_guardrail(test_kb, test_store):
    prod = Product(
        id="SP_TEST_SCRIPT",
        name="Nhẫn Bạc Thái Nam Kim Cô",
        aliases=["nhẫn kim cô"],
        price=580000,
        currency="VND",
        material="Bạc Thái S925",
        in_stock=True
    )
    test_kb.products = [prod]

    # Verify no "{price}" literal exists in the generated prompt or reply
    orchestrator = PipelineOrchestrator(kb=test_kb, store=test_store)
    inbound = InboundMessage(
        id="dry_test_noscript",
        platform="ig",
        channel="meta",
        surface="comment",
        text="nhẫn kim cô giá bao nhiêu",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert "{price}" not in result.draft_reply
    assert "{material}" not in result.draft_reply
    assert "{stock}" not in result.draft_reply

