import pytest
from src.knowledge.loader import KnowledgeBase
from src.storage.database import EventStore
from src.pipeline.orchestrator import PipelineOrchestrator
from src.models import InboundMessage
from src.config import KNOWLEDGE_DIR

@pytest.fixture
def test_kb():
    return KnowledgeBase(KNOWLEDGE_DIR)

@pytest.fixture
def test_store(tmp_path):
    db_file = tmp_path / "test_case_loi_events.db"
    return EventStore(str(db_file))

@pytest.fixture
def orchestrator(test_kb, test_store):
    return PipelineOrchestrator(kb=test_kb, store=test_store)

# 1. Khách hỏi loại bạc, bạc thật: AI nạp policies/warranty.md với cam kết S925, không báo thiếu thông tin
def test_silver_quality_facts_retrieval(orchestrator):
    inbound = InboundMessage(
        id="case_loi_1",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Viễn Chí Bảo dùng loại bạc gì, có phải bạc thật không?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert "policies/warranty.md" in result.knowledge_files
    facts_str = str(result.knowledge_facts)
    assert "S925" in facts_str
    assert "purity" in facts_str.lower() or "authentic" in facts_str.lower()

# 2. Mẹo phân biệt bạc thật tại nhà (DIY tests & nam châm): Khớp edge case
def test_diy_silver_authenticity_testing_edge_case(orchestrator):
    inbound = InboundMessage(
        id="case_loi_2",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Làm sao phân biệt bạc thật của Viễn Chí Bảo với bạc pha hay xi mạ? Có hút nam châm không?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_diy_silver_testing"
    assert "meta/edge_cases.md" in result.knowledge_files

# 3. Xử lý khi phát hiện bạc giả / không chuẩn: Cam kết đền bù 10 lần (không nhầm lẫn thu đổi thông thường)
def test_fake_silver_10x_compensation_edge_case(orchestrator):
    inbound = InboundMessage(
        id="case_loi_3",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Nếu nhận hàng và thấy bạc không đúng chuẩn, nếu là bạc giả thì Viễn Chí Bảo xử lý thế nào?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_substandard_silver_claim"
    assert "meta/edge_cases.md" in result.knowledge_files

# 4. Phương thức thanh toán khác ngoài PayPal -> Handover cho người theo policy mới
def test_unsupported_payment_methods_handover(orchestrator):
    inbound = InboundMessage(
        id="case_loi_4",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Shop có cho thanh toán khi nhận hàng ship COD không hay phải quẹt thẻ?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_unsupported_payment_handover"
    assert result.decision == "escalate"
    assert result.flag == "handover"
    assert result.needs_human is True
    assert "PayPal" in result.draft_reply

# 4b. Khách hỏi thanh toán PayPal: Tự động trả lời qua policies/payment.md
def test_paypal_payment_inquiry_auto_reply(orchestrator):
    inbound = InboundMessage(
        id="case_paypal_payment",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Shop có nhận thanh toán qua PayPal không ạ?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert "policies/payment.md" in result.knowledge_files
    payment_fact = result.knowledge_facts.get("policies.payment", "")
    assert "PayPal" in payment_fact
    assert "PayPal Buyer Protection" in payment_fact

# 5. Khách hỏi ưu đãi khi mua nhiều món: Kích hoạt Edge Case chuyển giao VIP Concierge
def test_bulk_purchase_volume_discount_escalation(orchestrator):
    inbound = InboundMessage(
        id="case_loi_5",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Mình định mua 3 chiếc nhẫn cùng lúc, mua nhiều có được giảm giá hay bớt không?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_bulk_volume_discount"
    assert result.needs_human is True
    assert result.flag == "handover"
    assert result.decision == "escalate"

# 6. Kiện hàng bị kẹt, tracking không cập nhật: Kích hoạt Handover đội Logistics
def test_stuck_shipment_delay_escalation(orchestrator):
    inbound = InboundMessage(
        id="case_loi_6",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Shipment is stuck, tracking not updating for 5 days!",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_stuck_shipment_delay"
    assert result.needs_human is True
    assert result.flag == "handover"

# 7. Khách lo lắng website lừa đảo: Cung cấp bằng chứng uy tín (10 năm, S925, 10x refund, PayPal buyer protection)
def test_anti_scam_legitimacy_inquiry(orchestrator):
    inbound = InboundMessage(
        id="case_loi_7",
        platform="ig",
        channel="meta",
        surface="comment",
        text="Is this legit or are you a scam website? Where are you located?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_scam_legitimacy_inquiry"

# 8. TikTok: Tố cáo lừa đảo, đạo nhái -> Handover ngay lập tức
def test_tiktok_scam_allegation_handover(orchestrator):
    inbound = InboundMessage(
        id="case_loi_8",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="This is stolen design, fake products, such a total scam!",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "tiktok_edge_scam_allegation"
    assert result.needs_human is True
    assert result.flag == "handover"

# 9. TikTok: Hỏi thử bạc tại nhà trên TikTok comment -> Nhanh, gọn, chuẩn
def test_tiktok_diy_silver_test(orchestrator):
    inbound = InboundMessage(
        id="case_loi_9",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="Mẫu này bạc thật không có hút nam châm không bạn?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "tiktok_edge_diy_silver_test"
    assert result.decision == "auto_reply"

# 10. Official Cancellation, Return & Refund Policy (HuyK Jewelry Docs)
def test_official_return_cancellation_policy(orchestrator):
    inbound = InboundMessage(
        id="case_loi_10",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Chính sách hủy đơn và đổi trả hàng của shop như thế nào ạ? Bị lỗi ban đầu thì liên hệ trong mấy ngày?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert "policies/returns.md" in result.knowledge_files
    returns_fact = result.knowledge_facts.get("policies.returns", "")
    assert "7 days" in returns_fact
    assert "Cancellation Before Shipment" in returns_fact
    assert "order@huykjeweler.com" in returns_fact
    assert "100%" in returns_fact

# 11. Customer wants to buy product ("how can I buy it"): Matches order rule, auto_reply, not fallback
def test_customer_want_to_buy_product(orchestrator):
    inbound = InboundMessage(
        id="case_loi_11",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        text="Hey, I want to buy your invisible ring? how can I buy it",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.flag == "auto_reply"
    assert result.status_badge == "handled"
    assert result.needs_human is False
    assert result.matched_product is not None
    assert result.matched_product.id == "N0006-07-S-WH"
    assert result.matched_rule == "tiktok_ask_order_dm"
    assert "356" in result.draft_reply or "$" in result.draft_reply

# 12. Official Shipping Policy (VIENCHIBAO – HuyK Jewelry Docs)
def test_official_shipping_policy(orchestrator):
    inbound = InboundMessage(
        id="case_loi_12",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Thời gian giao hàng và phí vận chuyển của shop như thế nào ạ?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert "policies/shipping.md" in result.knowledge_files
    ship_fact = result.knowledge_facts.get("policies.shipping", "")
    assert "2–5 business days" in ship_fact or "2-5 business days" in ship_fact or "2–5" in ship_fact
    assert "order@huykjeweler.com" in ship_fact
    assert "Free Domestic Shipping" in ship_fact or "free" in ship_fact.lower()

# 13. Official Warranty & Exchange Policy (VIENCHIBAO – HuyK Jewelry Docs)
def test_official_warranty_exchange_policy(orchestrator):
    inbound = InboundMessage(
        id="case_loi_13",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Chính sách bảo hành và đổi hàng của shop quy định trong mấy ngày?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert "policies/warranty.md" in result.knowledge_files
    warranty_fact = result.knowledge_facts.get("policies.warranty", "")
    assert "8 days" in warranty_fact
    assert "order@huykjeweler.com" in warranty_fact
    assert "Free 1-to-1 Replacement" in warranty_fact or "replacement" in warranty_fact.lower()

# 14. Fake product allegation on public comment -> Handover & Under 15 words clean reply
def test_fake_product_allegation_comment(orchestrator):
    inbound = InboundMessage(
        id="case_loi_14",
        platform="ig",
        channel="meta",
        surface="comment",
        text="Hey, your product is fake!",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_angry_complaint"
    assert result.flag == "handover"
    assert result.decision == "escalate"
    assert result.needs_human is True
    # Ensure no internal reasoning leaked
    assert "we need answer" not in result.draft_reply.lower()
    assert "need parse" not in result.draft_reply.lower()
    assert "<think>" not in result.draft_reply
    # Ensure under 15 words limit for public comment
    words = result.draft_reply.split()
    assert len(words) <= 15
    assert not result.draft_reply.endswith("/")

# 15. Refund & fake allegation on DM -> Handover & Complete studio escalation response
def test_fake_product_refund_dm(orchestrator):
    inbound = InboundMessage(
        id="case_loi_15",
        platform="ig",
        channel="meta",
        surface="dm",
        text="hey i want to be refunded, your product is fake?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_angry_complaint"
    assert result.flag == "handover"
    assert result.decision == "escalate"
    assert result.needs_human is True
    assert "we need answer" not in result.draft_reply.lower()
    assert not result.draft_reply.endswith("and I’m")
    assert not result.draft_reply.endswith("and I'm")
    if result.draft_reply != "chưa gắn API model":
        assert len(result.draft_reply) > 20

# 16. Unit test for sanitize_model_output logic
def test_sanitize_scratchpad_and_cutoffs():
    from src.adapters.model import sanitize_model_output
    # Deliberation scratchpad
    leak = 'We need answer. Need parse. Customer says "Hey, your product is fake!" Public comment. Need reply one single line under'
    assert sanitize_model_output(leak) == ""
    # Incomplete sentence cut-off
    cutoff = 'I hear you, and I’m'
    assert sanitize_model_output(cutoff) == ""
    # Think tag block
    cot = '<think>Deliberating answer...</think>We hear you and apologize!'
    assert sanitize_model_output(cot) == "We hear you and apologize!"

# 17. Sales Test Case: Khách hỏi nhẫn làm bằng vàng -> Khớp meta_ask_gold_material_any, không đẩy sang xưởng
def test_case_loi_ask_gold_material(orchestrator):
    inbound = InboundMessage(
        id="case_gold_1",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="Do you have this ring in gold?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "tiktok_ask_gold_material_any"
    assert "workshop" not in result.draft_reply.lower()
    assert "Master Jeweler" not in result.draft_reply

# 18. Sales Test Case: Khách hỏi loại đá / có làm bằng kim cương không -> Khớp meta_ask_stones_any
def test_case_loi_ask_stones_diamond(orchestrator):
    inbound = InboundMessage(
        id="case_stones_1",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="What kind of stones do you use? do you made with diamonds?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "tiktok_ask_stones_any"
    assert "specialist" not in result.draft_reply.lower()

# 19. Sales Test Case: Khách hỏi bạc có đen không -> Khớp meta_ask_tarnish_care_any
def test_case_loi_ask_tarnish_care(orchestrator):
    inbound = InboundMessage(
        id="case_tarnish_1",
        platform="ig",
        channel="meta",
        surface="comment",
        text="Will the ring tarnish or turn black over time?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "meta_ask_tarnish_care_any"

# 20. Sales Test Case: Khách hỏi size khi chưa có sản phẩm -> Trả lời size 4-12 trực tiếp, không check xưởng
def test_case_loi_ask_size_general(orchestrator):
    inbound = InboundMessage(
        id="case_size_general_1",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Can I order this ring in my size?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "meta_ask_size_general_any"
    assert "workshop" not in result.draft_reply.lower()

# 21. Sales Test Case: Khách hỏi nhận chế tác mẫu riêng -> Khớp tiktok_ask_custom_design_any
def test_case_loi_ask_custom_design(orchestrator):
    inbound = InboundMessage(
        id="case_custom_1",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="Do you offer custom ring designs?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "tiktok_ask_custom_design_any"

# 22. Sales Test Case: Khách hỏi ship sang Trung Quốc / quốc tế -> Khớp meta_ask_shipping_international_any
def test_case_loi_ask_china_shipping(orchestrator):
    inbound = InboundMessage(
        id="case_shipping_china_1",
        platform="ig",
        channel="meta",
        surface="dm",
        text="你好，在中国能买吗",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "meta_ask_shipping_international_any"

# 23. Sales Test Case: Khách hỏi địa chỉ xưởng / sản xuất ở đâu -> Khớp tiktok_ask_store_location_any
def test_case_loi_ask_store_location(orchestrator):
    inbound = InboundMessage(
        id="case_location_1",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        text="Please give me your store address. Where is your jewelry made?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "auto_reply"
    assert result.matched_rule == "tiktok_ask_store_location_any"

# 24. Sanitization test: Không lọt token [HANDOVER: missing_info] hoặc dấu ngoặc ]
def test_sanitize_handover_tokens_and_brackets():
    from src.adapters.model import sanitize_model_output
    raw = "That's our eternity band pick! [HANDOVER: missing_info]"
    cleaned = sanitize_model_output(raw)
    assert "[HANDOVER" not in cleaned
    assert "missing_info" not in cleaned

    stray_bracket = "Free US shipping included 🤍\n\n]"
    cleaned_bracket = sanitize_model_output(stray_bracket)
    assert "]" not in cleaned_bracket

# 25. Ops Feedback: Khách góp ý phát âm tiếng Anh -> Khớp pronunciation_feedback edge case
def test_pronunciation_feedback_edge_case(orchestrator):
    inbound = InboundMessage(
        id="case_ops_pronunciation",
        platform="ig",
        channel="meta",
        surface="comment",
        text="You’re mispronouncing the words, so I can’t understand what you’re saying.",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_pronunciation_feedback"
    assert result.decision == "auto_reply"
    # Public comment under 15 words
    words = result.draft_reply.split()
    assert len(words) <= 15

# 26. Ops Feedback: Khách tố cáo AI junk / bot -> Khớp ai_bot_question edge case
def test_ai_generated_junk_edge_case(orchestrator):
    inbound = InboundMessage(
        id="case_ops_ai_junk",
        platform="ig",
        channel="meta",
        surface="comment",
        text="AI-generated junk.",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_ai_bot_question"
    assert result.decision == "auto_reply"
    words = result.draft_reply.split()
    assert len(words) <= 15

# 27. Ops Feedback: Khách tố cáo lừa đảo (scammer) -> Phủ định lừa đảo & cảnh báo web giả mạo
def test_tiktok_scammer_denial_and_warning(orchestrator):
    inbound = InboundMessage(
        id="case_ops_scammer",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        text="You're scammer",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "tiktok_edge_scam_allegation"
    assert result.decision == "escalate"

# 28. Ops Feedback: Khách hỏi cửa hàng vật lý tại Mỹ vs VN -> Khớp ask_store_location, không nhầm sang scam
def test_physical_store_inquiry_not_scam(orchestrator):
    inbound = InboundMessage(
        id="case_ops_store_loc",
        platform="ig",
        channel="meta",
        surface="comment",
        text="Do you have a physical store?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_rule == "meta_ask_store_location_any"
    assert result.decision == "auto_reply"
    words = result.draft_reply.split()
    assert len(words) <= 15

# 29. Ops Feedback: Khách hỏi quà tặng kèm -> Khớp ask_gift_promotions rule
def test_free_gifts_promotion_inquiry(orchestrator):
    inbound = InboundMessage(
        id="case_ops_gift",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        text="Are there any free gifts included with the purchase?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_rule == "tiktok_ask_gift_promotions_any"
    assert result.decision == "auto_reply"

# 30. Ops Feedback: Khách so sánh giá với nơi khác rẻ hơn nửa -> Khớp ask_price_comparison rule
def test_price_comparison_inquiry(orchestrator):
    inbound = InboundMessage(
        id="case_ops_price_comp",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        text="Your ring looks almost identical to one I found online for half the price. Why should I buy yours?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_rule == "tiktok_ask_price_comparison_any"
    assert result.decision == "auto_reply"

# 31. Ops Feedback: Khách phàn nàn chưa được trả lời tin nhắn -> Khớp unanswered_dm_complaint
def test_unanswered_dm_complaint(orchestrator):
    inbound = InboundMessage(
        id="case_ops_unanswered_dm",
        platform="ig",
        channel="meta",
        surface="comment",
        text="Why aren’t you replying to my messages? Are you still selling this product or not?",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "meta_edge_unanswered_dm_complaint"
    assert result.decision == "auto_reply"
    words = result.draft_reply.split()
    assert len(words) <= 15

# 32. Ops Feedback: Khách khiếu nại bạc bị đen sau 1 tuần -> Khớp silver_tarnish_complaint
def test_silver_tarnish_complaint_edge_case(orchestrator):
    inbound = InboundMessage(
        id="case_ops_tarnish_complaint",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        text="I’ve only been wearing it for a week, and the silver has already turned black. You sold me a fake product!",
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.matched_edge_case == "tiktok_edge_silver_tarnish_complaint"
    assert result.decision == "auto_reply"

# 33. Multi-turn DM context continuity (Turn 1 -> Turn 2 -> Turn 3)
def test_multi_turn_dm_context_continuity(orchestrator, test_store):
    thread_id = "test_thread_continuity_01"

    # Turn 1: Customer asks about a ring
    inbound_t1 = InboundMessage(
        id="turn_1_msg",
        platform="ig",
        channel="meta",
        surface="dm",
        thread_id=thread_id,
        user_id="user_meta_01",
        text="Cho mình hỏi chiếc nhẫn mắt thần horus bên bạn giá bao nhiêu?",
        source="dry_run"
    )
    res_1 = orchestrator.process(inbound_t1)
    assert res_1.matched_product is not None
    assert "Horus" in res_1.matched_product.name
    assert res_1.decision == "auto_reply"

    # Save turn 1 into store session
    test_store.save_session_turn(
        session_id=thread_id,
        channel="meta",
        platform="ig",
        surface="dm",
        user_message=inbound_t1.text,
        reply=res_1.draft_reply,
        turn_data={
            "turn_index": 1,
            "customer_message": inbound_t1.text,
            "bot_reply": res_1.draft_reply,
            "matched_product": res_1.matched_product.name,
            "product_id": res_1.matched_product.id
        },
        thread_id=thread_id,
        user_id="user_meta_01"
    )

    # Turn 2: Customer asks follow-up size question WITHOUT repeating the product name
    inbound_t2 = InboundMessage(
        id="turn_2_msg",
        platform="ig",
        channel="meta",
        surface="dm",
        thread_id=thread_id,
        user_id="user_meta_01",
        text="Mẫu này có những size nào vậy shop?",
        source="dry_run"
    )
    res_2 = orchestrator.process(inbound_t2)
    # Context continuity: Must remember product from turn 1!
    assert res_2.matched_product is not None
    assert res_2.matched_product.id == res_1.matched_product.id
    assert "Horus" in res_2.matched_product.name
    # Must answer size inquiry without restarting or re-greeting
    assert "size" in res_2.draft_reply.lower() or "ni" in res_2.draft_reply.lower()
    # Must NOT repeat formal or first-turn greeting
    assert not res_2.draft_reply.startswith("Hi love!")
    assert not res_2.draft_reply.startswith("Chào bạn!")
    assert not res_2.draft_reply.startswith("Dạ chào")

    # Save turn 2 into store session
    test_store.save_session_turn(
        session_id=thread_id,
        channel="meta",
        platform="ig",
        surface="dm",
        user_message=inbound_t2.text,
        reply=res_2.draft_reply,
        turn_data={
            "turn_index": 2,
            "customer_message": inbound_t2.text,
            "bot_reply": res_2.draft_reply,
            "matched_product": res_2.matched_product.name,
            "product_id": res_2.matched_product.id
        },
        thread_id=thread_id,
        user_id="user_meta_01"
    )

    # Turn 3: Customer asks shipping without repeating product name
    inbound_t3 = InboundMessage(
        id="turn_3_msg",
        platform="tiktok",
        channel="tiktok",
        surface="dm",
        thread_id=thread_id,
        user_id="user_meta_01",
        text="Ship về Hà Nội mất mấy ngày vậy bạn?",
        source="dry_run"
    )
    res_3 = orchestrator.process(inbound_t3)
    assert res_3.matched_product is not None
    assert res_3.matched_product.id == res_1.matched_product.id
    assert not res_3.draft_reply.startswith("Hi love!")
    assert not res_3.draft_reply.startswith("Chào bạn!")

# 34. Image scanning - Non-jewelry image sent: Politely inform customer, NO hallucination
def test_image_scan_non_jewelry_detection(orchestrator):
    from src.models import MediaFrame
    inbound = InboundMessage(
        id="case_non_jewelry_meme",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Quét ảnh meme này xem giá bao nhiêu?",
        frames=[MediaFrame(data_url="data:image/jpeg;base64,...", label="funny_meme_cat.jpg")],
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "fallback"
    # Must inform customer it is not a jewelry product
    assert "không phải là hình ảnh sản phẩm trang sức" in result.draft_reply or "trang sức" in result.draft_reply
    # Must NOT hallucinate product specs or catalogue match
    assert result.matched_product is None

# 35. Image scanning - Non-jewelry image in comment (< 15 words)
def test_image_scan_non_jewelry_comment(orchestrator):
    from src.models import MediaFrame
    inbound = InboundMessage(
        id="case_non_jewelry_comment",
        platform="tiktok",
        channel="tiktok",
        surface="comment",
        text="Xem giúp mình hóa đơn này với",
        frames=[MediaFrame(data_url="data:image/jpeg;base64,...", label="receipt_bill.jpg")],
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "fallback"
    assert result.matched_product is None
    words = result.draft_reply.split()
    assert len(words) <= 15
    assert "\n" not in result.draft_reply

# 36. Image scanning - Unidentifiable jewelry image: Fallback and Handover, NO guessing
def test_image_scan_unidentified_jewelry_fallback_handover(orchestrator):
    from src.models import MediaFrame
    inbound = InboundMessage(
        id="case_unidentified_jewelry",
        platform="ig",
        channel="meta",
        surface="dm",
        text="Nhận dạng ảnh mẫu trang sức này giúp mình với shop ơi",
        frames=[MediaFrame(data_url="data:image/jpeg;base64,...", label="unknown_custom_piece.jpg")],
        source="dry_run"
    )
    result = orchestrator.process(inbound)
    assert result.decision == "fallback"
    assert result.flag == "handover"
    assert result.needs_human is True
    assert result.status_badge == "handover"
    # Never guess product or price
    assert result.matched_product is None
    # Inform customer politely and handover
    assert "chưa nhận diện được" in result.draft_reply or "chưa có trong danh mục" in result.draft_reply
    assert "Huy K" in result.draft_reply or "craft team" in result.draft_reply





