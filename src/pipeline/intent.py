import re
from typing import List, Dict, Any, Optional
from src.adapters.model import ModelAdapter

# Taxonomy of Customer Intents with Descriptions and Illustrative Examples.
# NOTE: Examples are purely illustrative guides for AI semantic reasoning, NOT rigid keyword filters.
INTENT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "complaint_angry": {
        "description": "Customer expresses anger, dissatisfaction, alleges scam or stolen design, reports damaged goods, or demands an urgent refund.",
        "examples": [
            "scam", "broken", "refund", "fake", "terrible", "damaged", "poor quality", "stolen design", "rip off",
            "lừa đảo", "hỏng", "rởm", "tẩy chay", "hoàn tiền", "trả hàng gấp", 
            "chất lượng kém", "tệ hại", "đạo nhái", "ăn cắp mẫu", "treo đầu dê"
        ]
    },
    "demand_human": {
        "description": "Customer asks if speaking with a robot/AI, or explicitly asks to speak with a real human agent.",
        "examples": [
            "are you a bot", "is this ai", "are you real", "talk to human", "real person", "human agent",
            "gặp người thật", "gặp nhân viên", "bot à", "robot à", "ai à", 
            "người thật hay ai", "auto rep à", "phải bot không"
        ]
    },
    "ask_order": {
        "description": "Customer expresses desire to buy, asks how to purchase, how to place an order, or requests checkout link / order steps.",
        "examples": [
            "how to buy", "how can i buy", "how do i buy", "want to buy", "wanna buy", "buy this", "buy it",
            "how to order", "how can i order", "how do i order", "want to order", "order this", "place an order", "can i order",
            "where to buy", "where can i buy", "how to purchase", "how can i get", "where to order", "link to buy", "order link", "checkout link",
            "how to get this", "how can i get this", "buy", "order", "purchase",
            "mua", "mua thế nào", "cách mua", "mua ở đâu", "làm sao để mua", "tôi muốn mua", "muốn mua",
            "đặt hàng", "đặt mua", "chốt đơn", "lên đơn", "mua hàng", "hướng dẫn mua"
        ]
    },
    "ask_photo": {
        "description": "Customer asks to see photos, pictures, close-up details, or visual images of a product.",
        "examples": [
            "send me the picture", "picture", "photo", "pic", "pics", "send pics", "send photo", "can i see it", "show me a photo",
            "see the photo", "show picture", "visuals", "look like", "ảnh", "hình", "cho xem ảnh", "gửi ảnh", "xem hình", "ảnh thật"
        ]
    },
    "ask_price": {
        "description": "Customer asks about the price, cost, or pricing of a product (including idioms like 'what\\'s the damage', 'how much for this').",
        "examples": [
            "price", "how much", "cost", "how much is", "what's the damage",
            "giá", "nhiêu", "bao nhiêu", "tiền", "ib giá", "xin giá", "inbox giá"
        ]
    },
    "ask_material": {
        "description": "Customer asks about the materials, metals, silver purity, stones, tarnish resistance, or whether it causes skin discoloration (turn skin green).",
        "examples": [
            "material", "sterling silver", "s925", "gold", "silver", "what is this made of", "tarnish", "pure silver", "turn skin green",
            "chất liệu", "bằng gì", "bạc", "vàng", "titan", "thật không", "bạc thật", "bị đen", "gỉ"
        ]
    },
    "ask_size": {
        "description": "Customer asks about sizes, US ring sizes, dimensions, finger measurements, or how to choose the right fit.",
        "examples": [
            "size", "sizing", "measurement", "dimensions", "fit", "diameter", "size 7", "size 8", "size 9", "size guide",
            "kích thước", "đo size", "vừa không", "tay nhỏ", "chiều dài", "đường kính", "bảng size"
        ]
    },
    "ask_stock": {
        "description": "Customer asks if an item is currently available, in stock, or sold out.",
        "examples": [
            "in stock", "available", "sold out", "ready to ship", "backorder",
            "còn hàng", "sẵn không", "hết hàng", "còn k", "sẵn ko", "còn mẫu", "có sẵn"
        ]
    },
    "ask_shipping": {
        "description": "Customer asks about shipping fees, delivery speed, transit time, shipping to a specific state or address, or carrier.",
        "examples": [
            "shipping", "delivery", "shipping fee", "how long to ship", "ship to", "deliver to", "fast shipping", "freeship",
            "ship", "vận chuyển", "giao hàng", "mấy ngày nhận", "phí ship", "bao lâu nhận"
        ]
    },
    "ask_payment": {
        "description": "Customer asks about payment methods, credit/debit cards, PayPal, Klarna/BNPL, taxes, or COD availability.",
        "examples": [
            "payment", "pay", "paypal", "credit card", "apple pay", "google pay", "klarna", "afterpay", "installment", "cod", "cash on delivery",
            "thanh toán", "thẻ", "quẹt thẻ", "trả sau", "trả góp", "ship cod"
        ]
    },
    "ask_silver_quality": {
        "description": "Customer asks about S925 hallmarks, testing authenticity at home (magnets, ice), or authenticity guarantees (10x refund).",
        "examples": [
            "real silver", "pure silver", "fake silver", "how to test", "magnet", "s925 stamp", "hallmark", "ice test", "10x", "guarantee",
            "bạc thật không", "phân biệt bạc", "bạc giả", "hút nam châm", "thử bạc", "đền 10 lần", "bạc xi", "bạc pha"
        ]
    },
    "ask_bulk_discount": {
        "description": "Customer asks about volume discounts, buying multiple pieces or combo sets.",
        "examples": [
            "bulk", "buy multiple", "buy 2", "buy 3", "discount", "combo", "wholesale", "offer",
            "mua nhiều", "mua 2", "mua 3", "giảm giá", "bớt không", "ưu đãi", "chiết khấu", "mua sỉ"
        ]
    },
    "ask_legitimacy": {
        "description": "Customer asks if the brand/store is legitimate, where the business is located, or asks for reassurance against online scams.",
        "examples": [
            "legit", "is this legit", "scam store", "where are you located", "business location", "trustpilot", "buyer protection",
            "uy tín không", "có lừa đảo không", "shop ở đâu", "cửa hàng ở đâu"
        ]
    },
    "ask_return_warranty": {
        "description": "Customer asks about return policy, 7-day initial defect return, exchange window, warranty, or polishing care.",
        "examples": [
            "warranty", "return", "exchange", "refund policy", "repair", "care", "polishing", "rma",
            "bảo hành", "đổi trả", "đổi size", "sửa", "làm sáng", "đánh bóng", "bảo quản"
        ]
    },
    "ask_store_location": {
        "description": "Customer asks for physical workshop address, showroom, or visiting the atelier in person.",
        "examples": [
            "address", "store location", "where is the studio", "showroom", "visit in person",
            "địa chỉ", "cửa hàng ở đâu", "qua xem trực tiếp", "shop ở đâu"
        ]
    },
    "request_custom": {
        "description": "Customer asks for bespoke jewelry, custom engraving, personalized sizing, or custom stone setting.",
        "examples": [
            "custom", "bespoke", "engrave", "engraving", "personalized", "custom size",
            "đặt làm", "theo yêu cầu", "khắc tên", "thiết kế riêng"
        ]
    },
    "general_compliment": {
        "description": "Customer shares a friendly compliment, expresses love for the piece, or warm greeting without asking a specific question.",
        "examples": [
            "beautiful", "gorgeous", "so pretty", "stunning", "love this", "obsessed", "amazing", "thank you", "thanks",
            "đẹp quá", "xinh xỉu", "mê quá", "cuốn ghê", "nhìn sang ghê", "tuyệt vời", "thả tim", "cảm ơn"
        ]
    }
}

# Backward compatibility alias
INTENT_KEYWORDS = {k: v["examples"] for k, v in INTENT_TAXONOMY.items()}

class IntentClassifier:
    def __init__(
        self,
        allowed_intents: Optional[List[str]] = None,
        model_adapter: Optional[ModelAdapter] = None
    ):
        self.allowed_intents = allowed_intents or list(INTENT_TAXONOMY.keys())
        self.model_adapter = model_adapter or ModelAdapter()
        self._cache: Dict[str, str] = {}

    def classify(self, text: str, context: Optional[str] = None) -> str:
        text = (text or "").strip()
        if not text:
            return "other"

        cache_key = f"{text.lower()}||{context or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. AI-Driven Semantic Reasoning via Model Adapter
        if self.model_adapter and self.model_adapter.is_available():
            inferred_intent = self._classify_with_llm(text, context)
            if inferred_intent and inferred_intent in self.allowed_intents:
                self._cache[cache_key] = inferred_intent
                return inferred_intent

        # 2. Semantic Heuristic Fallback (e.g. for offline testing or API downtime)
        fallback_intent = self._classify_semantic_fallback(text)
        self._cache[cache_key] = fallback_intent
        return fallback_intent

    def _classify_with_llm(self, text: str, context: Optional[str] = None) -> Optional[str]:
        """
        Uses LLM reasoning to infer customer intent semantically from meaning and goal,
        using example lists purely as illustrative guides.
        """
        taxonomy_lines = []
        for name in self.allowed_intents:
            meta = INTENT_TAXONOMY.get(name)
            if meta:
                ex_sample = ", ".join(meta["examples"][:6])
                taxonomy_lines.append(f"- {name}: {meta['description']} (Examples for reference: {ex_sample})")
        taxonomy_text = "\n".join(taxonomy_lines)

        system_prompt = (
            "You are an expert AI customer intent classifier for a fine jewelry studio (US market).\n"
            "Analyze the customer message, understand their semantic goal, and infer the most appropriate intent.\n"
            "IMPORTANT: Do NOT perform rigid keyword matching. Reason over the underlying meaning, idioms, slang, and context.\n"
            "The examples provided are only illustrations to guide your semantic reasoning.\n\n"
            "ALLOWED INTENTS & SEMANTIC DEFINITIONS:\n"
            f"{taxonomy_text}\n\n"
            "DECISION GUIDELINES:\n"
            "1. If customer asks how to buy, order, where to purchase, or how to get a piece, output: ask_order.\n"
            "2. If customer asks about cost, price, or pricing idioms (e.g. 'what's the damage', 'how much for this'), output: ask_price.\n"
            "3. If customer asks about metal, stone, tarnish, pure silver, or skin reaction (e.g. 'will this turn my skin green'), output: ask_material.\n"
            "4. If customer expresses anger, defects, or scam allegations, output: complaint_angry.\n"
            "5. If customer asks if you are an AI/bot or demands a real human, output: demand_human.\n"
            "6. If none of the specific intents clearly apply, output: other.\n\n"
            "RESPONSE FORMAT:\n"
            "Output ONLY the intent identifier (e.g. ask_order) with NO markdown, NO punctuation, and NO explanation."
        )

        user_content = text
        if context:
            user_content = f"Context: {context}\nCustomer: {text}"

        try:
            raw = self.model_adapter.generate_reply(
                system_prompt,
                [{"role": "user", "content": user_content}]
            )
            raw = (raw or "").strip().lower()
            cleaned = re.sub(r'[^a-z_]', '', raw)
            if cleaned in self.allowed_intents:
                return cleaned
            if cleaned == "other":
                return "other"
            for intent in self.allowed_intents:
                if intent == cleaned or intent in raw:
                    return intent
        except Exception as e:
            # Fall back to heuristic classification
            pass
        return None

    def _classify_semantic_fallback(self, text: str) -> str:
        """
        Fast semantic heuristic fallback when LLM is unavailable or in offline test environments.
        """
        text_lower = text.lower()

        # Priority 1: Complaints & bot demand
        for intent in ["complaint_angry", "demand_human"]:
            if intent in self.allowed_intents:
                examples = INTENT_TAXONOMY.get(intent, {}).get("examples", [])
                if any(kw in text_lower for kw in examples):
                    return intent

        # Priority 2: Product & service inquiries
        priority_order = [
            "ask_silver_quality", "ask_bulk_discount", "ask_legitimacy",
            "ask_order", "ask_payment", "ask_price", "ask_material", "ask_size", "ask_stock", 
            "ask_shipping", "ask_return_warranty", "ask_store_location", 
            "request_custom", "general_compliment"
        ]

        for intent in priority_order:
            if intent in self.allowed_intents:
                examples = INTENT_TAXONOMY.get(intent, {}).get("examples", [])
                if any(kw in text_lower for kw in examples):
                    return intent

        return "other"
