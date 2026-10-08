from typing import Optional, Tuple, Dict, Any, List
import re
from src.models import InboundMessage, Product, Rule, EdgeCase
from src.knowledge.loader import KnowledgeBase
from src.adapters.model import ModelAdapter

class FunnelEngine:
    def __init__(self, kb: KnowledgeBase, model_adapter: Optional[ModelAdapter] = None):
        self.kb = kb
        self.model_adapter = model_adapter or ModelAdapter()
        self._ec_cache: Dict[str, Optional[str]] = {}

    def match_funnel(
        self,
        inbound: InboundMessage,
        intent: str,
        product: Optional[Product]
    ) -> Tuple[Optional[EdgeCase], Optional[Rule]]:
        """
        Step 4: Semantic Funnel Routing
        Matches an edge case first via AI semantic reasoning and intent priorities.
        Else matches a channel-specific rule based on semantic intent and context.
        Else None.
        Enforces funnel separation:
        Meta funnel (ig, fb) only uses meta rules/edge_cases.
        TikTok funnel (tiktok) only uses tiktok rules/edge_cases.
        """
        text_lower = (inbound.text or "").lower()
        surface = inbound.surface
        channel = inbound.channel  # 'meta' or 'tiktok'

        # Select channel-specific edge cases and rules
        if channel == "meta":
            edge_cases = self.kb.meta_edge_cases
            rules = self.kb.meta_rules
        elif channel == "tiktok":
            edge_cases = self.kb.tiktok_edge_cases
            rules = self.kb.tiktok_rules
        else:
            edge_cases = []
            rules = []

        # ----------------------------------------------------------------------
        # 1. Edge case beats general rule (Semantic Priority & Reasoning)
        # ----------------------------------------------------------------------
        # Fast check for stuck shipment delay before generic angry complaint
        if any(kw in text_lower for kw in ["tracking not updating", "shipment is stuck", "tracking stuck", "kẹt hàng", "mã tracking không chạy"]):
            for ec in edge_cases:
                if "stuck_shipment" in ec.id:
                    return ec, None

        # Fast intent-based edge case mapping
        for ec in edge_cases:
            if ec.id in ("meta_edge_angry_complaint", "tiktok_edge_scam_allegation") and intent == "complaint_angry":
                return ec, None
            if ec.id == "meta_edge_ai_bot_question" and intent == "demand_human":
                return ec, None
            if "bulk" in ec.id and intent == "ask_bulk_discount":
                return ec, None
            if "scam_legitimacy" in ec.id and intent == "ask_legitimacy":
                return ec, None
            if "custom" in ec.id and intent == "request_custom":
                return ec, None

        # AI Semantic Edge Case Inference
        if self.model_adapter and self.model_adapter.is_available() and edge_cases and text_lower:
            ai_ec_id = self._infer_edge_case_semantic(inbound.text, edge_cases)
            # If normal silver quality consultation without scam accusation, let standard rule handle with warranty facts
            if intent in ("ask_silver_quality", "ask_material") and ai_ec_id and "scam" in ai_ec_id:
                if not any(k in text_lower for k in ["scam", "lừa đảo", "fake website", "is this legit", "where are you located", "shop ở đâu"]):
                    ai_ec_id = None
            if ai_ec_id:
                for ec in edge_cases:
                    if ec.id == ai_ec_id:
                        return ec, None

        # Fallback check on illustrative keyword examples
        for ec in edge_cases:
            if ec.contains_any:
                matched_kw = any(kw.lower() in text_lower for kw in ec.contains_any)
                if matched_kw:
                    return ec, None

        # ----------------------------------------------------------------------
        # 2. Match rule based on Semantic Intent, Surface & Product Context
        # ----------------------------------------------------------------------
        # Priority A: Check rules matching intent, surface, and product requirement
        for rule in rules:
            if rule.surface not in (surface, "any"):
                continue

            if rule.when.product_required and product is None:
                continue

            if rule.when.intent and rule.when.intent != intent:
                continue

            # Check contains_any only for rules without an explicit intent requirement
            if not rule.when.intent and rule.when.contains_any:
                matched_kw = any(kw.lower() in text_lower for kw in rule.when.contains_any)
                if not matched_kw:
                    continue

            return None, rule

        # Priority B: Check rules matching intent with surface="any" if surface-specific was not found
        for rule in rules:
            if rule.when.intent and rule.when.intent == intent:
                if rule.when.product_required and product is None:
                    continue
                return None, rule

        return None, None

    def _infer_edge_case_semantic(self, text: str, edge_cases: List[EdgeCase]) -> Optional[str]:
        """
        Uses Gemini to evaluate if the customer inquiry requires an operational Edge Case.
        """
        cache_key = f"ec::{text.lower().strip()}"
        if cache_key in self._ec_cache:
            return self._ec_cache[cache_key]

        lines = []
        for ec in edge_cases:
            lines.append(f"- ID: {ec.id} | Trigger: {ec.trigger}")
        ec_summary = "\n".join(lines)

        system_prompt = (
            "You are an operational edge case detector for a jewelry concierge support system.\n"
            "Review the customer message and determine if it matches any of the operational edge cases below.\n\n"
            f"OPERATIONAL EDGE CASES:\n{ec_summary}\n\n"
            "RULES:\n"
            "1. If the message clearly matches one of the edge case triggers, output ONLY its exact ID.\n"
            "2. If it is a normal product consultation (asking price, size, order, silver material purity/type, standard shipping policy), output: NONE.\n"
            "3. Inquiries asking about what kind of silver is used or if it is real silver ('dùng loại bạc gì', 'bạc thật không') are normal silver material consultations: output NONE.\n"
            "4. Inquiries reporting tracking number not updating or stuck shipment ('shipment is stuck', 'tracking not updating') match 'meta_edge_stuck_shipment_delay', NOT 'meta_edge_angry_complaint'.\n"
            "5. Output ONLY the ID or NONE with no explanation."
        )

        try:
            raw = self.model_adapter.generate_reply(
                system_prompt,
                [{"role": "user", "content": text}]
            )
            raw = (raw or "").strip()
            for ec in edge_cases:
                if ec.id in raw:
                    self._ec_cache[cache_key] = ec.id
                    return ec.id
        except Exception:
            pass

        self._ec_cache[cache_key] = None
        return None

    def load_knowledge_facts(
        self,
        rule: Optional[Rule],
        product: Optional[Product]
    ) -> Tuple[Dict[str, Any], List[str], bool, List[str]]:
        """
        Step 5: Load only the knowledge fields the rule cites.
        Returns:
            (facts_dict, knowledge_files_used, has_missing_required_facts, missing_fields)
        """
        facts: Dict[str, Any] = {}
        files_used: List[str] = []
        missing_fields: List[str] = []
        is_missing: bool = False

        if not rule:
            return facts, files_used, False, missing_fields

        if rule.when.product_required and product is None:
            is_missing = True
            missing_fields.append("catalogue.product_required")

        if not rule.use_knowledge:
            return facts, files_used, is_missing, missing_fields

        for field_path in rule.use_knowledge:
            parts = field_path.split(".", 1)
            prefix = parts[0]
            field_name = parts[1] if len(parts) > 1 else ""

            if prefix == "catalogue":
                files_used.append("catalogue/products.json")
                if product is None:
                    if rule.when.product_required:
                        is_missing = True
                        if field_path not in missing_fields:
                            missing_fields.append(field_path)
                    facts[field_path] = None
                else:
                    attr_name = "material" if field_name == "materials" else field_name
                    val = getattr(product, attr_name, None)
                    if val is None or val == "":
                        is_missing = True
                        if field_path not in missing_fields:
                            missing_fields.append(field_path)
                    facts[field_path] = val

            elif prefix == "policies":
                policy_file = f"policies/{field_name}.md"
                files_used.append(policy_file)
                policy_content = self.kb.policies.get(field_name, "")
                if not policy_content or not policy_content.strip():
                    is_missing = True
                    facts[field_path] = None
                    if field_path not in missing_fields:
                        missing_fields.append(field_path)
                else:
                    facts[field_path] = policy_content.strip()

        # Remove duplicate files
        files_used = list(dict.fromkeys(files_used))
        return facts, files_used, is_missing, missing_fields
