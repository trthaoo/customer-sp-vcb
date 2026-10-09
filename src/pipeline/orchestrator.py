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
                    self._log_event(inbound, result, fallback_reply, "fallback", "handover", escalate_reason, now_ts)
                    return result

        # Step 2: Match product using catalogue aliases & visual grounding
        matched_product, ambiguous_products = self.matcher.match(inbound.text, inbound.post_context)
        
        visual_product_guess: Optional[str] = None
        catalogue_id_matched: Optional[str] = None
        frame_used: Optional[str] = None
        product_visible_not_in_catalogue = False

        if inbound.frames and not vision_unsupported:
            if comment_needs_media or not matched_product:
                v_prod, v_guess, v_frame, unlisted = self._resolve_visual_context(inbound)
                if unlisted:
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
            else:
                visual_product_guess = matched_product.name
                catalogue_id_matched = matched_product.id
                frame_used = inbound.frames[0].label if inbound.frames else None
        elif matched_product:
            visual_product_guess = matched_product.name
            catalogue_id_matched = matched_product.id

        # Multi-turn context inheritance: if no product matched in current query, check previous turns in thread
        if not matched_product and inbound.history:
            for past_turn in reversed(inbound.history):
                past_text = past_turn.get("content", "")
                if not past_text:
                    continue
                past_prod, past_ambi = self.matcher.match(past_text)
                if past_prod:
                    matched_product = past_prod
                    visual_product_guess = past_prod.name
                    catalogue_id_matched = past_prod.id
                    break

        is_ambiguous = len(ambiguous_products) > 1

        # Step 3: Classify intent
        intent = self.classifier.classify(inbound.text)

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
            attached_image_url=attached_image_url
        )

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

        now_ts = datetime.now(timezone.utc).isoformat()
        self._log_event(inbound, result, reply, decision, flag, escalate_reason, now_ts)

        return result

    def _resolve_visual_context(
        self, inbound: InboundMessage
    ) -> Tuple[Optional[Product], Optional[str], Optional[str], bool]:
        """
        Resolves product on screen using caption + frames.
        Returns: (matched_product, visual_product_guess, frame_used, product_visible_not_in_catalogue)
        """
        if not self.composer.model_adapter.is_available() or not self.composer.model_adapter.is_vision_capable():
            p, _ = self.matcher.match(inbound.text, inbound.post_context)
            return p, (p.name if p else None), (inbound.frames[0].label if inbound.frames else None), False

        catalog_lines = []
        for p in self.kb.products:
            aliases_str = ", ".join(p.aliases or [])
            img_ref = f" | Image: {p.image_path or p.image_url}" if (p.image_path or p.image_url) else ""
            catalog_lines.append(f"- ID: {p.id} | Name: {p.name} | Aliases: {aliases_str}{img_ref}")
        catalog_text = "\n".join(catalog_lines)

        frame_labels = ", ".join([f.label for f in inbound.frames])
        prompt = (
            f"You are an expert jeweler staff analyzing social media post media for Viễn Chí Bảo Fine Jewelry.\n"
            f"Customer comment: \"{inbound.text}\"\n"
            f"Post caption: \"{inbound.post_context or ''}\"\n"
            f"Frames attached in chronological order: {frame_labels}\n\n"
            f"STORE CATALOGUE ITEMS WITH RECOGNIZED ALIASES:\n"
            f"{catalog_text}\n\n"
            f"TASK:\n"
            f"1. Examine the attached frames in time order and the caption to identify which jewelry product is on screen or referred to by the customer (resolve 'cái này', 'mẫu trong video', 'cái bên trái', color, etc.).\n"
            f"2. If it matches an item in the store catalogue above by alias, shape, or design:\n"
            f"MATCH_ID: <exact catalogue ID, e.g. VCB_SP01>\n"
            f"GUESS: <product name>\n"
            f"FRAME: <label of the frame where it is most prominent, e.g. t=2.0s or Slide 1>\n"
            f"UNLISTED: FALSE\n\n"
            f"3. If a jewelry product IS clearly shown in the video/images, but it is NOT in the store catalogue:\n"
            f"MATCH_ID: NONE\n"
            f"GUESS: <short description of the unlisted jewelry piece>\n"
            f"FRAME: <frame label>\n"
            f"UNLISTED: TRUE\n\n"
            f"4. If no jewelry product is visible or cannot be determined:\n"
            f"MATCH_ID: NONE\n"
            f"GUESS: None\n"
            f"FRAME: None\n"
            f"UNLISTED: FALSE\n\n"
            f"Output ONLY these 4 key-value lines."
        )

        try:
            import inspect
            sig = inspect.signature(self.composer.model_adapter.generate_reply)
            kwargs = {}
            if "frames" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs["frames"] = inbound.frames
            raw_res = self.composer.model_adapter.generate_reply(prompt, [], **kwargs)
            if not raw_res:
                return None, None, None, False

            match_id = None
            guess = None
            frame = None
            unlisted = False

            for line in raw_res.splitlines():
                line = line.strip()
                if line.upper().startswith("MATCH_ID:"):
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

            matched_p = self.kb.products_by_id.get(match_id) if match_id else None
            if not matched_p and guess and not unlisted:
                p, _ = self.matcher.match(guess)
                if p:
                    matched_p = p

            return matched_p, guess, frame, unlisted
        except Exception as e:
            print(f"Warning: Visual resolution error: {e}")
            return None, None, None, False

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
            user_id=inbound.user_id
        )
        self.store.insert_event(event_record)

_orchestrator: Optional[PipelineOrchestrator] = None

def get_orchestrator() -> PipelineOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
    return _orchestrator
