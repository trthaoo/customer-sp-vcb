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



