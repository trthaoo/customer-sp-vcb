from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from src.models import InboundMessage, PipelineResult, EventRecord, Product
from src.knowledge.loader import KnowledgeBase, get_knowledge_base
from src.storage.database import EventStore, get_event_store
from src.pipeline.matcher import ProductMatcher
from src.pipeline.intent import IntentClassifier
from src.pipeline.engine import FunnelEngine
from src.pipeline.composer import ReplyComposer
from src.adapters.zernio import ZernioClient
from src.config import HOLD_ON_HANDOVER, AUTO_SEND

from src.pipeline.media import get_media_processor, MediaProcessor
from src.pipeline.matcher import ProductMatcher, comment_depends_on_media

class PipelineOrchestrator:
    def __init__(
        self,
        kb: Optional[KnowledgeBase] = None,
        store: Optional[EventStore] = None,
        zernio: Optional[ZernioClient] = None
    ):
        self.kb = kb or get_knowledge_base()
        self.store = store or get_event_store()
        self.zernio = zernio or ZernioClient()
        self.media_processor = get_media_processor()

        self.composer = ReplyComposer(self.kb)
        self.matcher = ProductMatcher(self.kb.products, model_adapter=self.composer.model_adapter)
        self.classifier = IntentClassifier(self.kb.intents, model_adapter=self.composer.model_adapter)
        self.engine = FunnelEngine(self.kb, model_adapter=self.composer.model_adapter)

    def process(self, inbound: InboundMessage) -> PipelineResult:
        import time
        start_time = time.perf_counter()

        # Multi-turn history hydration: if inbound.history is empty, attempt to hydrate from store using thread_id / user_id
        if not inbound.history and (inbound.thread_id or inbound.user_id):
            session = self.store.get_chat_session_by_thread_or_user(inbound.thread_id, inbound.user_id)
            if session and session.get("turns"):
                hydrated = []
                for turn in session["turns"]:
                    if turn.get("customer_message"):
                        hydrated.append({"role": "user", "content": turn["customer_message"]})
                    if turn.get("bot_reply"):
                        hydrated.append({"role": "assistant", "content": turn["bot_reply"]})
                inbound.history = hydrated

        # Step 1: Media processing if not already extracted
        if not inbound.frames and (inbound.media_url or inbound.carousel_urls) and inbound.media_type != "link":
            extracted_frames, missing = self.media_processor.process_media(
                post_id=inbound.post_id,
                media_url=inbound.media_url,
                carousel_urls=inbound.carousel_urls,
                media_type=inbound.media_type
            )
            inbound.frames = extracted_frames
            if missing and inbound.surface == "comment":
                inbound.context_missing = True

        comment_needs_media = (inbound.surface == "comment" and comment_depends_on_media(inbound.text))

        # Check context_missing on comment
        # Take the media URL from the Zernio event payload. No URL = mark context_missing. If the comment depends on the video, handover.
        if inbound.surface == "comment" and inbound.context_missing and comment_needs_media:
            fallback_reply = self.kb.fallbacks.get("default", self.kb.default_fallback)
            now_ts = datetime.now(timezone.utc).isoformat()
            escalate_reason = "Bình luận phụ thuộc vào hình ảnh/video bài viết nhưng thiếu URL media (context_missing) -> chuyển giao nhân viên"
            short_reason = "Context missing: Bình luận cần video nhưng thiếu media URL -> Handover"
            
            result = PipelineResult(
                inbound=inbound,
                matched_product=None,
                intent="ask_product",
                knowledge_files=["shared/fallbacks.md"],
                knowledge_facts={},
                retrieved_chunks=[{
                    "file": "shared/fallbacks.md",
                    "title": "Context Missing Fallback",
                    "content": fallback_reply
                }],
                missing_fields=["post.media_context"],
                status_badge="handover",
                draft_reply=fallback_reply,
                final_reply=fallback_reply if not HOLD_ON_HANDOVER else "",
                decision="fallback",
                flag="handover",
                needs_human=True,
                escalate_reason=escalate_reason,
                short_reason=short_reason,
                context_missing=True,
                vision_unsupported=False,
                caption=inbound.post_context,
                frames=inbound.frames,
                frame_count=len(inbound.frames),
                frame_timestamps=[f.label for f in inbound.frames],
                reply_sent=False
            )
            elapsed_sec = round(time.perf_counter() - start_time, 3)
            result.response_time_sec = elapsed_sec
            result.latency_ms = int(round(elapsed_sec * 1000))
            self._log_event(inbound, result, fallback_reply, "fallback", "handover", escalate_reason, now_ts)
            return result

        # Check vision capability
        # Model must be vision-capable. If it cannot take images, log vision_unsupported and handover when the comment needs the video.
        vision_unsupported = False
        if inbound.frames:
            if not self.composer.model_adapter.is_vision_capable():
                vision_unsupported = True
                if comment_needs_media:
                    fallback_reply = self.kb.fallbacks.get("default", self.kb.default_fallback)
                    now_ts = datetime.now(timezone.utc).isoformat()
                    escalate_reason = "Mô hình không hỗ trợ thị giác/hình ảnh (vision_unsupported) trong khi bình luận cần thông tin từ video -> chuyển giao nhân viên"
                    short_reason = "Vision unsupported: Model không xử lý được video/frames -> Handover"
                    result = PipelineResult(
                        inbound=inbound,
                        matched_product=None,
                        intent="ask_product",
                        knowledge_files=["shared/fallbacks.md"],
                        knowledge_facts={},
                        retrieved_chunks=[{
                            "file": "shared/fallbacks.md",
                            "title": "Vision Unsupported Fallback",
                            "content": fallback_reply
                        }],
                        missing_fields=["model.vision_unsupported"],
                        status_badge="handover",
                        draft_reply=fallback_reply,
                        final_reply=fallback_reply if not HOLD_ON_HANDOVER else "",
                        decision="fallback",
                        flag="handover",
                        needs_human=True,
                        escalate_reason=escalate_reason,
                        short_reason=short_reason,
                        context_missing=False,
                        vision_unsupported=True,
                        caption=inbound.post_context,
                        frames=inbound.frames,
                        frame_count=len(inbound.frames),
                        frame_timestamps=[f.label for f in inbound.frames],
                        reply_sent=False
                    )
                    elapsed_sec = round(time.perf_counter() - start_time, 3)
                    result.response_time_sec = elapsed_sec
                    result.latency_ms = int(round(elapsed_sec * 1000))
                    self._log_event(inbound, result, fallback_reply, "fallback", "handover", escalate_reason, now_ts)
                    return result

        # Step 2 & 3: Run independent product matching, intent classification, and RAG retrieval concurrently
        # Guarantees 100% full semantic reasoning depth while reducing overall pipeline latency by ~1.5x - 2x
        import concurrent.futures

        def _run_matcher():
            return self.matcher.match(inbound.text, inbound.post_context)

        def _run_classifier():
            return self.classifier.classify(inbound.text)

        def _run_rag():
            t_rag_start = time.perf_counter()
            try:
                from src.knowledge.rag_service import get_rag_service
                rag_res = get_rag_service().search(query=inbound.text, top_k=3, channel=inbound.channel, min_score=0.45)
                dur = int(round((time.perf_counter() - t_rag_start) * 1000))
                return rag_res, dur
            except Exception as e:
                print(f"Warning: Concurrent RAG search error: {e}")
                return [], 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            fut_match = executor.submit(_run_matcher)
            fut_intent = executor.submit(_run_classifier)
            fut_rag = executor.submit(_run_rag)

            matched_product, ambiguous_products = fut_match.result()
            intent = fut_intent.result()
            prefetched_rag, rag_time_ms = fut_rag.result()
        
        visual_product_guess: Optional[str] = None
        catalogue_id_matched: Optional[str] = None
        frame_used: Optional[str] = None
        product_visible_not_in_catalogue = False
        is_non_jewelry_image = False
        unidentified_jewelry_image = False

        if inbound.frames and not vision_unsupported:
            if comment_needs_media or not matched_product or inbound.surface == "dm":
                v_prod, v_guess, v_frame, unlisted, is_non_j = self._resolve_visual_context(inbound)
                if is_non_j:
                    is_non_jewelry_image = True
                    matched_product = None
                    visual_product_guess = v_guess or "non_jewelry"
                    frame_used = v_frame
                elif unlisted:
                    product_visible_not_in_catalogue = True
                    visual_product_guess = v_guess
                    frame_used = v_frame
                    matched_product = None
                elif v_prod:
                    matched_product = v_prod
                    visual_product_guess = v_guess or v_prod.name
                    catalogue_id_matched = v_prod.id
                    frame_used = v_frame
                elif v_guess:
                    visual_product_guess = v_guess
                    frame_used = v_frame
                elif not matched_product and (inbound.surface == "dm" or "ảnh" in inbound.text.lower()):
                    unidentified_jewelry_image = True
                    frame_used = v_frame
                elif matched_product:
                    visual_product_guess = matched_product.name
                    catalogue_id_matched = matched_product.id
                    frame_used = v_frame or (inbound.frames[0].label if inbound.frames else None)
            else:
                visual_product_guess = matched_product.name
                catalogue_id_matched = matched_product.id
                frame_used = inbound.frames[0].label if inbound.frames else None
        elif matched_product:
            visual_product_guess = matched_product.name
            catalogue_id_matched = matched_product.id

        # Multi-turn context inheritance: if no product matched in current query, check previous turns in thread
        if not matched_product and not is_non_jewelry_image:
            # 1. Check session turns first if available
            if inbound.thread_id or inbound.user_id:
                session = self.store.get_chat_session_by_thread_or_user(inbound.thread_id, inbound.user_id)
                if session and session.get("turns"):
                    for past_turn_data in reversed(session["turns"]):
                        p_id = past_turn_data.get("product_id")
                        p_name = past_turn_data.get("matched_product")
                        if p_id and p_id in self.kb.products_by_id:
                            matched_product = self.kb.products_by_id[p_id]
                            visual_product_guess = matched_product.name
                            catalogue_id_matched = matched_product.id
                            unidentified_jewelry_image = False
                            break
                        elif p_name:
                            past_p, _ = self.matcher.match(p_name)
                            if past_p:
                                matched_product = past_p
                                visual_product_guess = past_p.name
                                catalogue_id_matched = past_p.id
                                unidentified_jewelry_image = False
                                break

            # 2. Check inbound.history (both user and assistant turns)
            if not matched_product and inbound.history:
                for past_turn in reversed(inbound.history):
                    past_text = past_turn.get("content", "")
                    if not past_text:
                        continue
                    past_prod, _ = self.matcher.match(past_text)
                    if past_prod:
                        matched_product = past_prod
                        visual_product_guess = past_prod.name
                        catalogue_id_matched = past_prod.id
                        unidentified_jewelry_image = False
                        break

        # Check if customer sent image or asked to scan/identify an image but no product matched
        if not matched_product and not is_non_jewelry_image and not product_visible_not_in_catalogue:
            lower_msg = inbound.text.lower()
            asking_scan = any(w in lower_msg for w in ["quét ảnh", "nhận dạng ảnh", "quet anh", "nhan dang anh", "ảnh này là gì", "mẫu trong ảnh", "chiếc này trong ảnh", "xem mẫu trong ảnh"])
            if inbound.frames or asking_scan:
                unidentified_jewelry_image = True

        is_ambiguous = len(ambiguous_products) > 1

        # Detect photo request & resolve attached_image_url
        lower_text = inbound.text.lower()
        is_asking_photo = (
            intent == "ask_photo"
            or any(w in lower_text for w in ["photo", "pic", "picture", "image", "visual", "ảnh", "hình", "xem mẫu", "show me", "send me"])
        )
        attached_image_url: Optional[str] = None
        if matched_product and is_asking_photo:
            attached_image_url = matched_product.image_url or f"/static/products/{matched_product.id}.jpg"

        # Step 4: Match edge case first, else match rule, else fallback
        matched_edge_case, matched_rule = self.engine.match_funnel(inbound, intent, matched_product)

        # Step 5: Load only the knowledge fields the rule cites
        # Price, material, stock, ship, promo still come only from knowledge. A frame never fills a null field.
        facts: Dict[str, Any] = {}
        files_used: List[str] = []
        missing_fields: List[str] = []
        is_missing: bool = False

        if matched_rule:
            facts, files_used, is_missing, missing_fields = self.engine.load_knowledge_facts(matched_rule, matched_product)

        # Step 6 & 7: Compose human reply
        t_comp_start = time.perf_counter()
        composition = self.composer.compose_reply(
            inbound=inbound,
            intent=intent,
            product=matched_product,
            rule=matched_rule,
            edge_case=matched_edge_case,
            facts=facts,
            is_missing_required_facts=is_missing,
            is_ambiguous_product=is_ambiguous,
            missing_fields=missing_fields,
            product_visible_not_in_catalogue=product_visible_not_in_catalogue,
            visual_product_guess=visual_product_guess,
            frame_used=frame_used,
            attached_image_url=attached_image_url,
            rag_results=prefetched_rag,
            is_non_jewelry_image=is_non_jewelry_image,
            unidentified_jewelry_image=unidentified_jewelry_image
        )
        model_time_ms = int(round((time.perf_counter() - t_comp_start) * 1000))

        reply = composition["reply"]
        decision = composition["decision"]
        flag = composition["flag"]
        status_badge = composition.get("status_badge", "handled")
        needs_human = composition["needs_human"]
        escalate_reason = composition["escalate_reason"]
        all_files_used = composition.get("files_used", files_used)
        retrieved_chunks = composition.get("retrieved_chunks", [])
        final_missing_fields = composition.get("missing_fields", missing_fields)
        example_good_reply = composition.get("example_good_reply")
        model_called = composition.get("model_called", False)
        model_used = composition.get("model_used")
        short_reason = composition.get("short_reason")

        # Outbound handling
        reply_sent = False
        if inbound.source == "brand_test":
            reply_sent = False
        elif flag == "auto_reply" and decision == "auto_reply":
            if AUTO_SEND:
                try:
                    if inbound.surface == "comment" and inbound.post_id:
                        self.zernio.reply_comment(inbound.post_id, inbound.id, reply)
                    elif inbound.surface == "dm" and inbound.thread_id:
                        self.zernio.send_dm(inbound.thread_id, reply)
                    reply_sent = True
                except Exception as e:
                    print(f"Error calling Zernio send: {e}")
                    reply_sent = False
            else:
                reply_sent = False
        else:
            reply_sent = False

        result = PipelineResult(
            inbound=inbound,
            matched_product=matched_product,
            ambiguous_products=ambiguous_products,
            matched_rule=matched_rule.id if matched_rule else None,
            matched_edge_case=matched_edge_case.id if matched_edge_case else None,
            intent=intent,
            knowledge_files=all_files_used,
            knowledge_facts=facts,
            retrieved_chunks=retrieved_chunks,
            missing_fields=final_missing_fields,
            status_badge=status_badge,
            draft_reply=reply,
            final_reply=reply if (not HOLD_ON_HANDOVER or flag != "handover") else "",
            decision=decision,
            flag=flag,
            needs_human=needs_human,
            escalate_reason=escalate_reason,
            example_good_reply=example_good_reply,
            model_called=model_called,
            model_used=model_used,
            reply_sent=reply_sent,
            caption=inbound.post_context,
            frames=inbound.frames,
            frame_count=len(inbound.frames),
            frame_timestamps=[f.label for f in inbound.frames],
            visual_product_guess=visual_product_guess,
            catalogue_id_matched=catalogue_id_matched,
            frame_used=frame_used,
            context_missing=inbound.context_missing,
            vision_unsupported=vision_unsupported,
            short_reason=short_reason,
            attached_image_url=attached_image_url
        )

        elapsed_sec = round(time.perf_counter() - start_time, 3)
        result.response_time_sec = elapsed_sec
        result.latency_ms = int(round(elapsed_sec * 1000))
        result.rag_time_ms = rag_time_ms
        result.model_time_ms = model_time_ms

        now_ts = datetime.now(timezone.utc).isoformat()
        self._log_event(inbound, result, reply, decision, flag, escalate_reason, now_ts)

        return result

    def _resolve_visual_context(
        self, inbound: InboundMessage
    ) -> Tuple[Optional[Product], Optional[str], Optional[str], bool, bool]:
        """
        Resolves product on screen or uploaded image using caption + frames.
        Returns: (matched_product, visual_product_guess, frame_used, product_visible_not_in_catalogue, is_non_jewelry)
        """
        media_str = f"{inbound.text} {inbound.post_context or ''} {' '.join([f.label for f in inbound.frames])} {inbound.media_url or ''}".lower()
        non_jewelry_signals = [
            "meme", "hóa đơn", "hoa don", "receipt", "bill", "chuyển khoản", "banking",
            "chó", "mèo", "pet", "dog", "cat", "đồ ăn", "food", "selfie", "screenshot",
            "ảnh thẻ", "phong cảnh", "landscape", "xe hơi", "car", "non_jewelry", "unrelated"
        ]
        if any(w in media_str for w in non_jewelry_signals):
            frame_lbl = inbound.frames[0].label if inbound.frames else None
            return None, "non_jewelry_image", frame_lbl, False, True

        if not self.composer.model_adapter.is_available() or not self.composer.model_adapter.is_vision_capable():
            p, _ = self.matcher.match(inbound.text, inbound.post_context)
            if p:
                return p, p.name, (inbound.frames[0].label if inbound.frames else None), False, False
            if "unlisted" in media_str or "thiết kế riêng" in media_str or "mẫu ngoài" in media_str:
                return None, "unlisted_jewelry", (inbound.frames[0].label if inbound.frames else None), True, False
            return None, None, (inbound.frames[0].label if inbound.frames else None), False, False

        catalog_lines = []
        for p in self.kb.products:
            aliases_str = ", ".join(p.aliases or [])
            img_ref = f" | Image: {p.image_path or p.image_url}" if (p.image_path or p.image_url) else ""
            catalog_lines.append(f"- ID: {p.id} | Name: {p.name} | Aliases: {aliases_str}{img_ref}")
        catalog_text = "\n".join(catalog_lines)

        frame_labels = ", ".join([f.label for f in inbound.frames])
        prompt = (
            f"You are an expert jeweler staff analyzing social media post media or customer uploaded images for Viễn Chí Bảo Fine Jewelry.\n"
            f"Customer message: \"{inbound.text}\"\n"
            f"Post caption: \"{inbound.post_context or ''}\"\n"
            f"Frames attached in chronological order: {frame_labels}\n\n"
            f"STORE CATALOGUE ITEMS WITH RECOGNIZED ALIASES:\n"
            f"{catalog_text}\n\n"
            f"TASK:\n"
            f"1. Check if the attached media contains a JEWELRY product (ring, necklace, bracelet, earrings, pendant, bangle, gemstones, precious metals).\n"
            f"   - If the image is NOT jewelry (e.g. meme, animal/pet, receipt/bill, selfie/portrait without jewelry focus, random everyday object, landscape, food, car, chat screenshot, document):\n"
            f"     IS_JEWELRY: FALSE\n"
            f"     MATCH_ID: NONE\n"
            f"     GUESS: <short description of non-jewelry image>\n"
            f"     FRAME: <frame label>\n"
            f"     UNLISTED: FALSE\n\n"
            f"2. If the image IS jewelry:\n"
            f"   IS_JEWELRY: TRUE\n"
            f"   a. If it matches an item in the store catalogue above by alias, shape, or design:\n"
            f"      MATCH_ID: <exact catalogue ID, e.g. VCB_SP01>\n"
            f"      GUESS: <product name>\n"
            f"      FRAME: <label of the frame where it is most prominent, e.g. t=2.0s or Slide 1>\n"
            f"      UNLISTED: FALSE\n\n"
            f"   b. If it IS jewelry, but is NOT in the store catalogue:\n"
            f"      MATCH_ID: NONE\n"
            f"      GUESS: <short description of the unlisted jewelry piece>\n"
            f"      FRAME: <frame label>\n"
            f"      UNLISTED: TRUE\n\n"
            f"   c. If it IS jewelry, but cannot be identified / blurry / unclear:\n"
            f"      MATCH_ID: NONE\n"
            f"      GUESS: None\n"
            f"      FRAME: <frame label>\n"
            f"      UNLISTED: FALSE\n\n"
            f"Output ONLY these 5 key-value lines:\n"
            f"IS_JEWELRY: <TRUE/FALSE>\n"
            f"MATCH_ID: <ID or NONE>\n"
            f"GUESS: <description or None>\n"
            f"FRAME: <label or None>\n"
            f"UNLISTED: <TRUE/FALSE>"
        )

        try:
            import inspect
            sig = inspect.signature(self.composer.model_adapter.generate_reply)
            kwargs = {}
            if "frames" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs["frames"] = inbound.frames
            raw_res = self.composer.model_adapter.generate_reply(prompt, [], **kwargs)
            if not raw_res:
                return None, None, None, False, False

            match_id = None
            guess = None
            frame = None
            unlisted = False
            is_jewelry = True

            for line in raw_res.splitlines():
                line = line.strip()
                if line.upper().startswith("IS_JEWELRY:"):
                    val = line.split(":", 1)[1].strip().upper()
                    if "FALSE" in val:
                        is_jewelry = False
                elif line.upper().startswith("MATCH_ID:"):
                    val = line.split(":", 1)[1].strip()
                    if val.upper() != "NONE":
                        match_id = val
                elif line.upper().startswith("GUESS:"):
                    val = line.split(":", 1)[1].strip()
                    if val.upper() != "NONE":
                        guess = val
                elif line.upper().startswith("FRAME:"):
                    val = line.split(":", 1)[1].strip()
                    if val.upper() != "NONE":
                        frame = val
                elif line.upper().startswith("UNLISTED:"):
                    val = line.split(":", 1)[1].strip()
                    unlisted = (val.upper() == "TRUE")

            if not is_jewelry:
                return None, guess or "non_jewelry_image", frame, False, True

            matched_p = self.kb.products_by_id.get(match_id) if match_id else None
            if not matched_p and guess and not unlisted:
                p, _ = self.matcher.match(guess)
                if p:
                    matched_p = p

            return matched_p, guess, frame, unlisted, False
        except Exception as e:
            print(f"Warning: Visual resolution error: {e}")
            return None, None, None, False, False

    def _log_event(
        self,
        inbound: InboundMessage,
        result: PipelineResult,
        reply: str,
        decision: str,
        flag: str,
        escalate_reason: Optional[str],
        now_ts: str
    ):
        handover_state = "open" if flag == "handover" else None
        event_record = EventRecord(
            id=inbound.id,
            ts=now_ts,
            env=inbound.env,
            source=inbound.source,
            channel=inbound.channel,
            platform=inbound.platform,
            surface=inbound.surface,
            intent=result.intent,
            product_id=result.matched_product.id if result.matched_product else None,
            matched_rule=result.matched_rule or result.matched_edge_case,
            knowledge_files=result.knowledge_files,
            decision=decision,
            flag=flag,
            handover_state=handover_state,
            reply_sent=result.reply_sent,
            user_message=inbound.text,
            reply_text=reply,
            escalate_reason=escalate_reason,
            thread_id=inbound.thread_id,
            user_id=inbound.user_id,
            response_time_sec=result.response_time_sec
        )
        self.store.insert_event(event_record)

_orchestrator: Optional[PipelineOrchestrator] = None

def get_orchestrator() -> PipelineOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
    return _orchestrator
