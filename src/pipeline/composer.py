import re
from typing import Optional, Dict, Any, List, Tuple
from src.models import InboundMessage, Product, Rule, EdgeCase, MediaFrame
from src.knowledge.loader import KnowledgeBase
from src.config import PLATFORM_LIMITS
from src.adapters.model import get_model_adapter

def format_currency(price: Optional[float], currency: Optional[str] = "VND") -> str:
    if price is None:
        return ""
    curr = (currency or "VND").upper()
    if curr in ("VND", "Đ", "VNĐ"):
        return f"{int(price):,}đ".replace(",", ".")
    return f"${price:.2f}" if curr == "USD" else f"{price} {curr}"

class ReplyComposer:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self._model_adapter = None

    @property
    def model_adapter(self):
        if self._model_adapter is not None:
            return self._model_adapter
        return get_model_adapter()

    @model_adapter.setter
    def model_adapter(self, adapter):
        self._model_adapter = adapter

    def compose_reply(
        self,
        inbound: InboundMessage,
        intent: str,
        product: Optional[Product],
        rule: Optional[Rule],
        edge_case: Optional[EdgeCase],
        facts: Dict[str, Any],
        is_missing_required_facts: bool,
        is_ambiguous_product: bool = False,
        missing_fields: Optional[List[str]] = None,
        product_visible_not_in_catalogue: bool = False,
        visual_product_guess: Optional[str] = None,
        frame_used: Optional[str] = None,
        attached_image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        RAG + Visual context every turn:
        - caption of that post or video
        - frames of the video, in time order
        - the image, or each carousel slide, if it is not a video

        Use caption + frames to resolve 'cái này', 'mẫu trong video', 'cái bên trái', color, and which product is on screen.
        Then match that read to catalogue aliases. Price, material, stock, ship, promo still come only from knowledge.
        A frame never fills a null field. Product visible but not in the catalogue = say so and handover.

        Do not reply from a fixed script.
        reply_guide and example_good_reply are constraints, not the sentence to send. No intent-to-canned-reply map.
        No '{price}' template as the customer reply.
        """
        missing_fields = list(missing_fields or [])
        files_used: List[str] = []
        retrieved_chunks: List[Dict[str, Any]] = []

        # 1. Product visible on screen but not in catalogue -> Say so politely and handover
        if product_visible_not_in_catalogue:
            files_used = ["shared/brand_voice.md"]
            is_vietnamese = bool(re.search(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', inbound.text.lower()))
            if is_vietnamese:
                reply_text = (
                    "Dạ mẫu trang sức trong video này bên em hiện chưa có trong danh mục niêm yết chính thức của xưởng ạ. "
                    "Em xin phép chuyển thông tin cho bạn chuyên viên kiểm tra kho chế tác và hỗ trợ anh/chị ngay nhé! ✨"
                )
            else:
                reply_text = (
                    "This handcrafted piece in the video is currently not listed in our official studio catalogue. "
                    "Let me connect you with our studio artisan to check workshop availability for you right away! ✨"
                )
            return {
                "reply": reply_text,
                "decision": "fallback",
                "flag": "handover",
                "status_badge": "handover",
                "needs_human": True,
                "escalate_reason": f"Sản phẩm hiển thị trong video ({visual_product_guess or 'mẫu trên màn hình'}) không có trong catalogue -> thông báo cho khách và chuyển giao nhân viên",
                "short_reason": f"Sản phẩm '{visual_product_guess or 'trên video'}' không có trong catalogue | Frame: {frame_used or 'N/A'}",
                "files_used": files_used,
                "retrieved_chunks": [{
                    "file": "catalogue/products.json",
                    "title": "Catalogue Check",
                    "content": f"Visual read: {visual_product_guess}. Không khớp mã sản phẩm nào trong catalogue."
                }],
                "missing_fields": ["catalogue.unlisted_product"],
                "example_good_reply": None,
                "model_called": False,
                "model_used": None
            }

        # 2. Ambiguous product match -> ask which one or handover
        if is_ambiguous_product:
            files_used = ["shared/fallbacks.md", "catalogue/products.json"]
            fallback_text = self.kb.fallbacks.get(
                "ambiguous_product",
                "Dạ hiện bên em có một vài mẫu tương tự, anh/chị cho em xin thêm tên hoặc hình ảnh mẫu mình đang quan tâm để em hỗ trợ chính xác nha!"
            )
            retrieved_chunks.append({
                "file": "shared/fallbacks.md",
                "title": "Ambiguous Product Fallback",
                "content": fallback_text
            })
            return {
                "reply": fallback_text,
                "decision": "fallback",
                "flag": "handover",
                "status_badge": "fallback",
                "needs_human": True,
                "escalate_reason": "Nhiều sản phẩm catalogue cùng khớp từ khóa (không tự ý đoán mẫu) -> kích hoạt fallback và chuyển giao nhân viên",
                "short_reason": "Trùng khớp nhiều sản phẩm trong catalogue -> Fallback fallbacks.md",
                "files_used": files_used,
                "retrieved_chunks": retrieved_chunks,
                "missing_fields": ["catalogue.product_disambiguation"],
                "example_good_reply": None,
                "model_called": False,
                "model_used": None
            }

        # 3. Edge case matched (Edge case matches before a general rule)
        if edge_case:
            files_used = ["shared/brand_voice.md", f"{inbound.channel}/edge_cases.md"]
            edge_chunk_content = f"Trigger: {edge_case.trigger}\nDO: {edge_case.do}\nDO NOT: {edge_case.do_not}"
            retrieved_chunks.append({
                "file": f"{inbound.channel}/edge_cases.md",
                "title": f"Edge Case: {edge_case.id}",
                "content": edge_chunk_content
            })
            retrieved_chunks.append({
                "file": "shared/brand_voice.md",
                "title": "Brand Voice & Persona (Huy K - Viễn Chí Bảo)",
                "content": self._get_brand_voice_summary()
            })

            # Semantic Knowledge Chunks from Google AI Studio Embeddings
            try:
                from src.knowledge.rag_service import get_rag_service
                rag = get_rag_service()
                rag_results = rag.search(query=inbound.text, top_k=2, channel=inbound.channel, min_score=0.45)
                for r in rag_results:
                    src_file = r.get("source_file", "")
                    if src_file:
                        files_used.append(src_file)
                    retrieved_chunks.append({
                        "file": src_file or "knowledge/rag",
                        "title": f"Google AI Studio RAG [{int(r['score']*100)}% Match]: {r['title']}",
                        "content": r["content"]
                    })
            except Exception as e:
                print(f"Warning: RAG retrieval error in edge case: {e}")

            # Decision and flag based on edge case
            if edge_case.escalate:
                decision = "escalate"
                flag = "handover"
                status_badge = "handover"
                needs_human = True
                escalate_reason = f"Khớp tình huống đặc biệt (Edge Case): {edge_case.id} ({edge_case.trigger})"
            else:
                decision = "auto_reply"
                flag = "auto_reply"
                status_badge = "handled"
                needs_human = False
                escalate_reason = f"Khớp tình huống đặc biệt (Edge Case): {edge_case.id}"

            short_reason = f"Edge case {edge_case.id} | DO: {edge_case.do[:40]}..."

            # Generate reply dynamically with model adhering to DO and DO NOT
            # example_good_reply is a side-by-side sample for the brand, not the answer and not a fact source.
            if not self.model_adapter.is_available():
                reply = "chưa gắn API model"
                model_called = False
                model_used = None
            else:
                reply, model_called, model_used, custom_reason = self._call_model_for_edge_case(
                    inbound, edge_case, retrieved_chunks, attached_image_url=attached_image_url
                )
                if custom_reason:
                    short_reason = custom_reason
                reply = self._enforce_limits(reply, inbound.platform, inbound.surface)

            return {
                "reply": reply,
                "decision": decision,
                "flag": flag,
                "status_badge": status_badge,
                "needs_human": needs_human,
                "escalate_reason": escalate_reason,
                "short_reason": short_reason,
                "files_used": files_used,
                "retrieved_chunks": retrieved_chunks,
                "missing_fields": [],
                "example_good_reply": edge_case.example_good_reply,
                "model_called": model_called,
                "model_used": model_used
            }

        # 4. Missing fact check
        # Missing fact = fallback from fallbacks.md + handover flag. Never fill price, material, stock, ship, or promo from the model.
        if is_missing_required_facts:
            files_used = ["shared/fallbacks.md"]
            if product:
                files_used.append("catalogue/products.json")

            fallback_text = self.kb.fallbacks.get("default", self.kb.default_fallback)
            escalate_reason = f"Thiếu thông tin bắt buộc trong kho tri thức: {', '.join(missing_fields)}"

            retrieved_chunks.append({
                "file": "shared/fallbacks.md",
                "title": "Fallback Response (fallbacks.md)",
                "content": fallback_text
            })

            short_reason = f"Missing fact ({', '.join(missing_fields)}) -> Fallback từ fallbacks.md | Chuyển giao"

            return {
                "reply": fallback_text,
                "decision": "fallback",
                "flag": "handover",
                "status_badge": "fallback",
                "needs_human": True,
                "escalate_reason": escalate_reason,
                "short_reason": short_reason,
                "files_used": files_used,
                "retrieved_chunks": retrieved_chunks,
                "missing_fields": missing_fields,
                "example_good_reply": None,
                "model_called": False,
                "model_used": None
            }

        # 4b. Dynamic semantic concierge rule if no specific static rule matched but verified facts are present
        if not rule:
            from src.models import Rule, RuleWhen
            guide = (
                "Respond warmly in Brand Voice as the mindful studio host from Master Jeweler Huy K's atelier. "
                "Use only confirmed knowledge and verified catalogue specs. Never invent unconfirmed discounts. "
                "Answer the customer naturally and ask at most ONE gentle clarifying question."
            )
            if product:
                guide = (
                    f"Confirm the piece is {product.name}. Share its authentic artisanal details and specifications "
                    "from verified catalogue facts without making up false specs. Offer ring sizing or styling guidance."
                )
            rule = Rule(
                id=f"{inbound.channel}_semantic_concierge",
                channel=inbound.channel,
                surface=inbound.surface,
                when=RuleWhen(intent=intent, product_required=False),
                use_knowledge=["catalogue.price", "catalogue.material", "policies.shipping", "policies.payment"],
                if_missing="escalate",
                reply_guide=guide
            )

        # 5. Valid rule with all allowed facts present -> RAG Chunks retrieved
        files_used.append("shared/brand_voice.md")
        files_used.append(f"{inbound.channel}/rules.md")

        # Chunk 1: Brand Voice
        retrieved_chunks.append({
            "file": "shared/brand_voice.md",
            "title": "Brand Voice & Persona (Huy K - Viễn Chí Bảo)",
            "content": self._get_brand_voice_summary()
        })

        # Chunk 2: Product Catalogue Facts (ONLY allowed product facts)
        if product:
            files_used.append("catalogue/products.json")
            cat_lines = [
                f"Sản phẩm: {product.name} (ID: {product.id})",
                f"Giá niêm yết: {format_currency(product.price, product.currency)}",
                f"Chất liệu: {product.material or 'N/A'}",
                f"Tình trạng tồn kho: {'Còn hàng' if product.in_stock else 'Tạm hết hàng'}",
                f"Biến thể / Size: {product.variants or 'N/A'}",
                f"Hướng dẫn size: {product.size_guide or 'N/A'}",
                f"Vận chuyển / Đóng gói: {product.ship_note or 'N/A'}"
            ]
            if product.description:
                cat_lines.append(f"Mô tả chi tiết / Description: {product.description}")
            if product.notes:
                cat_lines.append(f"Ý nghĩa & Ghi chú / Notes: {product.notes}")
            cat_content = "\n".join(cat_lines)
            retrieved_chunks.append({
                "file": "catalogue/products.json",
                "title": f"Catalogue: {product.name} (Chỉ sử dụng dữ liệu này)",
                "content": cat_content
            })

        # Chunk 3: Policies (if cited)
        for field in rule.use_knowledge:
            if field.startswith("policies."):
                pol_name = field.split(".", 1)[1]
                pol_content = self.kb.policies.get(pol_name, "")
                if pol_content:
                    files_used.append(f"policies/{pol_name}.md")
                    retrieved_chunks.append({
                        "file": f"policies/{pol_name}.md",
                        "title": f"Chính sách: {pol_name.capitalize()}",
                        "content": pol_content[:600]
                    })

        # Chunk 4: Rule Guidance
        retrieved_chunks.append({
            "file": f"{inbound.channel}/rules.md",
            "title": f"Quy tắc phản hồi: {rule.id}",
            "content": f"Kênh: {rule.channel} | Bề mặt: {rule.surface}\nHướng dẫn trả lời: {rule.reply_guide}"
        })

        # Chunk 5: Dynamic Semantic Knowledge from Google AI Studio Embeddings
        try:
            from src.knowledge.rag_service import get_rag_service
            rag = get_rag_service()
            rag_results = rag.search(query=inbound.text, top_k=3, channel=inbound.channel, min_score=0.45)
            for r in rag_results:
                src_file = r.get("source_file", "")
                if src_file:
                    files_used.append(src_file)
                retrieved_chunks.append({
                    "file": src_file or "knowledge/rag",
                    "title": f"Google AI Studio RAG [{int(r['score']*100)}% Match]: {r['title']}",
                    "content": r["content"]
                })
        except Exception as e:
            print(f"Warning: RAG retrieval error: {e}")

        # Deduplicate files used
        files_used = list(dict.fromkeys(files_used))

        p_name = product.name if product else "mẫu này"
        p_id = product.id if product else "None"
        short_reason = f"Product: {p_id} ({p_name}) | Rule: {rule.id} | Chunks: {', '.join(files_used)}"

        # Check Model Key
        # No model key = show "chưa gắn API model" and do not invent a reply.
        if not self.model_adapter.is_available():
            reply = "chưa gắn API model"
            model_called = False
            model_used = None
        else:
            reply, model_called, model_used, custom_reason = self._call_model_for_rule(
                inbound, product, rule, retrieved_chunks, frame_used=frame_used, attached_image_url=attached_image_url
            )
            if custom_reason:
                short_reason = custom_reason
            reply = self._enforce_limits(reply, inbound.platform, inbound.surface)

        return {
            "reply": reply,
            "decision": "auto_reply",
            "flag": "auto_reply",
            "status_badge": "handled",
            "needs_human": False,
            "escalate_reason": None,
            "short_reason": short_reason,
            "files_used": files_used,
            "retrieved_chunks": retrieved_chunks,
            "missing_fields": [],
            "example_good_reply": None,
            "model_called": model_called,
            "model_used": model_used
        }

    def _get_brand_voice_summary(self) -> str:
        return (
            "Brand: Vien Chi Bao Fine Jewelry & Artistry (US Market Concierge - HuyK Jewelry).\n"
            "Persona: The Mindful Studio Host, speaking with warmth and quiet pride from Master Jeweler Huy K's workshop.\n"
            "Target Audience: United States shoppers (roughly 18–34). Reply in 100% natural, human American texting style.\n"
            "HUMAN TEXTING CONVERSATIONAL ARCHITECTURE (9 NON-NEGOTIABLE RULES):\n"
            "1. DYNAMIC 1–3 BUBBLES RHYTHM: Send 1 to 3 short bubbles (separated by double newlines '\\n\\n'), NOT a giant block of text and NOT robotic 3 bubbles every single turn.\n"
            "   - Quick answers / photo shares / compliments: 1 or 2 short punchy bubbles.\n"
            "   - Consultations / sizing guidance / closing an order: 2 to 3 bubbles (Acknowledge -> Answer -> Hook).\n"
            "2. MATCH THEIR ENERGY: If excited ('omg so cute'), match excitement. If short/spec-oriented ('real gold or plated'), be direct and crisp. If formal, be warm and clean. NEVER open with 'hey bestie' for spec questions.\n"
            "3. SLANG SAFE VS SKIP: Safe: 'obsessed', 'so good on you', 'it's giving', 'love this for you'. Mirroring only if they use it first: 'girl', 'lowkey', 'ngl', 'fr'. BANNED: 'no cap', 'bussin', 'rizz', 'ate and left no crumbs', 'periodt', and no 'hey bestie' for refunds/shipping. Bridal / >$500 = zero slang.\n"
            "4. EMOJI: Max 1 emoji per bubble, usually at the end of the last bubble (✨ 🤍 💛 💍). No stacks (😍😍😍). No opening emoji. Zero to minimal on complaints/refunds.\n"
            "5. PUNCTUATION IS TONE & BANNED EM-DASH: No period on short casual lines = friendly. Period on short line = cold/annoyed. BANNED: NEVER use the em-dash '—'. It looks robotic, unnatural, and screams AI. Use commas, natural line breaks, or separate bubbles instead.\n"
            "6. COMMENTS VS DMS (QUY TẮC 1 - PUBLIC COMMENT REPLY): Comments MUST be under 15 words (< 15 words). BẢO MẬT GIÁ CẢ: Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền, không dùng ký hiệu '$'. Luôn điều hướng khách vào kiểm tra hộp thư riêng (DM/inbox) để xem báo giá và chi tiết độc quyền. DMs are 2-3 bubbles where orders close. Never pull off-platform to WhatsApp/email.\n"
            "7. JEWELRY SCRIPTS: Name the exact piece. Never say 'the item'. In compliments, never upsell.\n"
            "8. COMPLAINTS: Person first, not corporate policy. Never say 'as per our policy' or 'a lot of customers love this'. Direct empathy + quick resolution.\n"
            "9. ONE QUESTION ONLY: Ask at most ONE question per message. Never bombard with multiple questions. If they say 'I will think about it', one light bubble and silence."
        )

    def _call_model_for_edge_case(
        self,
        inbound: InboundMessage,
        edge_case: EdgeCase,
        chunks: List[Dict[str, Any]],
        attached_image_url: Optional[str] = None
    ) -> Tuple[str, bool, Optional[str], Optional[str]]:
        comment_instruction = ""
        if inbound.surface == "comment":
            comment_instruction = (
                "QUY TẮC 1: PHẢN HỒI BÌNH LUẬN CÔNG KHAI (PUBLIC COMMENT REPLY):\n"
                "- Bắt buộc dưới 15 từ (< 15 words).\n"
                "- BẢO MẬT GIÁ CẢ: Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền, không dùng ký hiệu '$'. Luôn điều hướng khách vào kiểm tra hộp thư riêng (DM/inbox) để xem báo giá và chi tiết độc quyền.\n"
            )

        system_prompt = (
            f"You are customer support staff replying to a customer for Vien Chi Bao jewelry on {inbound.platform} ({inbound.surface}).\n"
            f"Persona: The Mindful Studio Host, speaking with warmth and respect from Master Jeweler Huy K's workshop.\n"
            f"TARGET MARKET: United States (US). Reply in 100% natural, warm, human American texting style (unless customer writes in Vietnamese).\n"
            f"{comment_instruction}"
            f"Strict Edge Case instructions:\n"
            f"- DO: {edge_case.do}\n"
            f"- DO NOT: {edge_case.do_not}\n"
            f"CRITICAL BE HUMAN TEXTING RULES (DYNAMIC 1 TO 3 BUBBLES):\n"
            f"1. Format as 1 to 3 SHORT BUBBLES, separated by '\\n\\n'. ONE thought per bubble. Maximum 15 words per bubble.\n"
            f"   - Do NOT rigidly generate 3 bubbles if 1 or 2 bubbles are clearer and more natural.\n"
            f"   - Bubble 1: Acknowledge & direct empathy.\n"
            f"   - Bubble 2: Clear answer / resolution.\n"
            f"   - Bubble 3 (if needed): Next step or single clarifying question.\n"
            f"2. For complaints: Person first, NOT clauses. Never say 'as per policy' or 'a lot of customers love this'. Minimal or zero emojis.\n"
            f"3. Never admit being an AI or bot.\n"
            f"4. Keep comments 1–2 short lines. Keep DMs concise.\n"
            f"5. Vary wording naturally. Do not use canned scripts.\n"
            f"6. BANNED PUNCTUATION: Strictly NEVER use the em-dash '—'. Do not connect clauses with dashes. It looks robotic and screams AI. Use commas, periods, or short separate bubbles.\n"
            f"At the very end of your response, output on a new line: [REASON: EdgeCase {edge_case.id}]"
        )

        messages: List[Dict[str, str]] = []
        if inbound.history:
            messages.extend(inbound.history)
        messages.append({"role": "user", "content": inbound.text})

        import inspect
        sig = inspect.signature(self.model_adapter.generate_reply)
        kwargs = {}
        if "frames" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            kwargs["frames"] = inbound.frames

        raw_reply = self.model_adapter.generate_reply(system_prompt, messages, **kwargs)
        if not raw_reply:
            if not self.model_adapter.is_available():
                return "chưa gắn API model", False, None, None
            fallback_text = self.kb.fallbacks.get("default", self.kb.default_fallback)
            return fallback_text, False, self.model_adapter.model_name, f"Model {self.model_adapter.model_name} response empty -> Fallback"

        reply, reason = self._extract_diagnostic_reason(raw_reply)
        return reply, True, self.model_adapter.model_name, reason

    def _call_model_for_rule(
        self,
        inbound: InboundMessage,
        product: Optional[Product],
        rule: Rule,
        chunks: List[Dict[str, Any]],
        frame_used: Optional[str] = None,
        attached_image_url: Optional[str] = None
    ) -> Tuple[str, bool, Optional[str], Optional[str]]:
        chunks_text = "\n\n".join([f"[{c['title']}]\n{c['content']}" for c in chunks])
        media_info = ""
        if inbound.frames:
            media_info = f"\nATTACHED MEDIA: {len(inbound.frames)} frames from video/post in time order: " + ", ".join([f.label for f in inbound.frames])
        
        caption_info = f"\nPOST CAPTION: {inbound.post_context}" if inbound.post_context else ""

        photo_info = ""
        if attached_image_url and product:
            photo_info = (
                f"\nOFFICIAL PHOTO ATTACHMENT CAPABILITY:\n"
                f"The customer is asking to see the photo/picture of {product.name} (ID: {product.id}).\n"
                f"The chat system IS AUTOMATICALLY ATTACHING the official high-resolution studio photo ({attached_image_url}) directly to this message!\n"
                f"NEVER say 'I cannot send images', 'I am just a bot', or 'I don't have access to photos'.\n"
                f"Instead, warmly and casually present the photo in 1 or 2 short natural bubbles:\n"
                f"- Example: \"here's a close-up look at the {product.name} in studio lighting ✨\"\n"
                f"- Or: \"here she is! ✨\\n\\nlet me know if you want to see the clasp or chain detail 🤍\"\n"
            )

        comment_instruction = ""
        if inbound.surface == "comment":
            comment_instruction = (
                "CRITICAL QUY TẮC 1: PHẢN HỒI BÌNH LUẬN CÔNG KHAI (PUBLIC COMMENT REPLY):\n"
                "- Độ dài: Bắt buộc dưới 15 từ (< 15 words).\n"
                "- BẢO MẬT GIÁ CẢ: Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền, không dùng ký hiệu '$'. Luôn điều hướng khách vào kiểm tra hộp thư riêng (DM/inbox) để xem báo giá và chi tiết độc quyền.\n"
                "- PRICE CONFIDENTIALITY: Strictly NEVER reveal or quote any price in public comments, no dollar amounts, no '$' symbol. Always direct the user to check DM/inbox for pricing and exclusive details.\n\n"
            )

        system_prompt = (
            f"You are page staff replying to customers for Vien Chi Bao jewelry on {inbound.platform} ({inbound.surface}).\n"
            f"Persona: The Mindful Studio Host, speaking warmly from Master Jeweler Huy K's atelier.\n"
            f"TARGET MARKET: United States (US). Reply in 100% natural, warm, human American texting style (unless customer writes in Vietnamese).\n"
            f"{comment_instruction}"
            f"{caption_info}{media_info}{photo_info}\n\n"
            f"GROUNDING KNOWLEDGE CHUNKS (ONLY ALLOWED FACTS):\n"
            f"{chunks_text}\n\n"
            f"CRITICAL BE HUMAN TEXTING RULES (DYNAMIC 1 TO 3 SHORT BUBBLES):\n"
            f"1. DYNAMIC BUBBLE COUNT (1 TO 3 BUBBLES MAX), separated by double newlines '\\n\\n'. ONE thought per bubble:\n"
            f"   - DO NOT rigidly force 3 bubbles every time! Real people text naturally based on the question:\n"
            f"   - Quick facts, photo sharing, compliments, or single spec queries: send 1 or 2 short bubbles.\n"
            f"   - Detailed styling advice, ring sizing, or closing an order: send 2 or 3 bubbles (Acknowledge -> Answer -> Gentle Hook).\n"
            f"   - NEVER send a wall of text. Keep each bubble punchy (under 15 words).\n"
            f"   - Never add filler or repeat fake questions just to stretch out 3 bubbles.\n"
            f"2. NEVER start with formal greetings like 'Hello! It’s lovely to hear from you' or 'Thank you for reaching out'. Start directly like a real person texting.\n"
            f"3. Match customer energy. Name the exact piece. Never say 'the item'.\n"
            f"4. Slang safe vs skip: Safe: 'obsessed', 'love this for you', 'the cutest'. NEVER use 'no cap', 'bussin', 'rizz', 'periodt', and NEVER open with 'hey bestie' for specs.\n"
            f"5. Emoji: Max ONE emoji at the end of the last bubble (✨, 🤍, 💍). Never stack emojis.\n"
            f"6. Punctuation: Friendly natural casing. No cold period at the end of short lines. BANNED PUNCTUATION: Strictly NEVER use the em-dash '—'. It looks artificial and screams AI. Use commas, periods, or new bubbles instead.\n"
            f"7. Never say you are an AI, bot, or virtual assistant. Never invent unconfirmed discounts.\n"
            f"8. Comments: 1–2 short lines. DMs: 1–3 short bubbles.\n"
            f"At the very end of your response, output on a new line: [REASON: product={product.id if product else 'None'}, frame={frame_used or 'N/A'}, chunks=catalogue/{rule.id}]"
        )

        messages: List[Dict[str, str]] = []
        if inbound.history:
            messages.extend(inbound.history)
        messages.append({"role": "user", "content": inbound.text})

        import inspect
        sig = inspect.signature(self.model_adapter.generate_reply)
        kwargs = {}
        if "frames" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            kwargs["frames"] = inbound.frames

        raw_reply = self.model_adapter.generate_reply(system_prompt, messages, **kwargs)
        if not raw_reply:
            if not self.model_adapter.is_available():
                return "chưa gắn API model", False, None, None
            fallback_text = self.kb.fallbacks.get("default", self.kb.default_fallback)
            return fallback_text, False, self.model_adapter.model_name, f"Model {self.model_adapter.model_name} response empty -> Fallback"

        reply, reason = self._extract_diagnostic_reason(raw_reply)
        return reply, True, self.model_adapter.model_name, reason

    def _extract_diagnostic_reason(self, raw_reply: str) -> Tuple[str, Optional[str]]:
        """Extracts [REASON: ...] tag for playground panel and strips it from customer reply."""
        match = re.search(r'\[REASON:\s*(.*?)\]', raw_reply, re.DOTALL | re.IGNORECASE)
        reason = match.group(1).strip() if match else None
        cleaned_reply = re.sub(r'\[REASON:\s*.*?\]', '', raw_reply, flags=re.DOTALL | re.IGNORECASE).strip()
        return cleaned_reply, reason

    def _enforce_limits(self, text: str, platform: str, surface: str) -> str:
        if not text or text == "chưa gắn API model":
            return text
        if "—" in text:
            text = re.sub(r'\s*—\s*', ', ', text)
        limits = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS.get("ig", {}))
        if surface == "comment":
            max_chars = limits.get("comment_max_chars", 150)
            max_words = limits.get("comment_max_words", 25)
            words = text.split()
            if len(words) > max_words:
                text = " ".join(words[:max_words])
            if len(text) > max_chars:
                text = text[:max_chars].rsplit(" ", 1)[0]
        else:
            max_chars = limits.get("dm_max_chars", 600)
            if len(text) > max_chars:
                text = text[:max_chars].rsplit(" ", 1)[0]
        return text.strip()

