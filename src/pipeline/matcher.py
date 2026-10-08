import re
import unicodedata
from typing import List, Tuple, Optional, Dict, Any
from src.models import Product
from src.adapters.model import ModelAdapter

def normalize_text(text: str) -> str:
    """Normalize text by lowering, stripping accents optionally or keeping unicode lower."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

DEICTIC_PATTERNS = [
    # Vietnamese deictic patterns
    r'cái này', r'mẫu này', r'chiếc này', r'vòng này', r'nhẫn này', r'mặt này',
    r'trong video', r'trong clip', r'trên video', r'trên clip', r'trên bài', r'trên post',
    r'cái bên trái', r'cái bên phải', r'ở giữa', r'mẫu bên trái', r'mẫu bên phải',
    r'màu này', r'màu đỏ', r'màu đen', r'màu trắng', r'màu vàng',
    r'thứ nhất', r'thứ hai', r'đầu tiên', r'giây thứ',
    # English deictic patterns
    r'this one', r'this piece', r'this ring', r'this pendant', r'this necklace', r'this bracelet',
    r'in the video', r'in the clip', r'on the video', r'on video', r'on screen', r'in the post',
    r'the one on the left', r'the one on the right', r'the one in the middle',
    r'first one', r'second one', r'third one', r'she is wearing', r'shown here', r'in this reel'
]

def comment_depends_on_media(text: str) -> bool:
    """Checks if a comment has deictic references referring to the post's video or image."""
    if not text:
        return False
    t = text.lower()
    for pattern in DEICTIC_PATTERNS:
        if re.search(r'(?:\b|\W|^)' + pattern + r'(?:\b|\W|$)', t, re.IGNORECASE):
            return True
    return False

class ProductMatcher:
    def __init__(self, products: List[Product], model_adapter: Optional[ModelAdapter] = None):
        self.products = products
        self.model_adapter = model_adapter or ModelAdapter()
        self._cache: Dict[str, Tuple[Optional[Product], List[Product]]] = {}

    def match(
        self,
        text: str,
        context: Optional[str] = None,
        visual_guess: Optional[str] = None
    ) -> Tuple[Optional[Product], List[Product]]:
        """
        Matches product against text, post caption context, and visual guess.
        Priority:
        1. Fast exact alias match in customer text alone
        2. Fast match in text + post context (caption)
        3. Match in visual guess
        4. AI Semantic Product Grounding (reasoning over product descriptions, stones, motifs)
        Returns:
            (matched_product, []) if exactly one product matched.
            (None, [prod1, prod2, ...]) if 2 or more products matched (Ambiguity!).
            (None, []) if no products matched.
        """
        cache_key = f"{text}||{context or ''}||{visual_guess or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Step 1: Check text alone via fast alias matching
        text_norm = normalize_text(text)
        matched_in_text = self._find_matches(text_norm)
        if len(matched_in_text) == 1:
            res = (matched_in_text[0], [])
            self._cache[cache_key] = res
            return res
        elif len(matched_in_text) > 1:
            res = (None, matched_in_text)
            self._cache[cache_key] = res
            return res

        # Step 2: Check text + context (post caption)
        if context:
            combined = f"{text_norm} {normalize_text(context)}"
            matched_combined = self._find_matches(combined)
            if len(matched_combined) == 1:
                res = (matched_combined[0], [])
                self._cache[cache_key] = res
                return res
            elif len(matched_combined) > 1:
                res = (None, matched_combined)
                self._cache[cache_key] = res
                return res

        # Step 3: Check visual guess
        if visual_guess:
            matched_visual = self._find_matches(normalize_text(visual_guess))
            if len(matched_visual) == 1:
                res = (matched_visual[0], [])
                self._cache[cache_key] = res
                return res
            elif len(matched_visual) > 1:
                res = (None, matched_visual)
                self._cache[cache_key] = res
                return res

        # Step 4: AI Semantic Product Grounding via Model Reasoning
        if self.model_adapter and self.model_adapter.is_available() and self.products and text_norm:
            semantic_res = self._match_semantic_ai(text, context)
            if semantic_res[0] is not None or len(semantic_res[1]) > 0:
                self._cache[cache_key] = semantic_res
                return semantic_res

        res = (None, [])
        self._cache[cache_key] = res
        return res

    def _match_semantic_ai(self, text: str, context: Optional[str] = None) -> Tuple[Optional[Product], List[Product]]:
        """
        Uses Gemini to reason over customer query and identify matching catalogue product(s) semantically.
        """
        # Build concise catalogue summary
        lines = []
        for p in self.products:
            aliases_str = ", ".join(p.aliases or [])
            desc_snippet = (p.description or "")[:120]
            lines.append(f"- ID: {p.id} | Name: {p.name} | Aliases: {aliases_str} | Material: {p.material or ''} | Features: {desc_snippet}")
        catalogue_text = "\n".join(lines)

        system_prompt = (
            "You are an expert fine jewelry product identifier for Vien Chi Bao.\n"
            "Your task is to determine which product from the catalogue below the customer is referring to.\n\n"
            f"CATALOGUE OF VERIFIED PRODUCTS:\n{catalogue_text}\n\n"
            "RULES:\n"
            "1. Read the customer query and infer which piece they are describing or asking about.\n"
            "2. If exactly one product matches, output ONLY its exact product ID (e.g. N0006-07-S-WH).\n"
            "3. If the query equally refers to 2 or more products (ambiguous), output their product IDs separated by commas (e.g. ID1,ID2).\n"
            "4. If the customer does NOT mention any specific jewelry design, or asks generally, output: NONE.\n"
            "5. Output NO other text, NO punctuation, and NO explanation."
        )

        user_content = text
        if context:
            user_content = f"Post Caption: {context}\nCustomer Query: {text}"

        try:
            raw = self.model_adapter.generate_reply(
                system_prompt,
                [{"role": "user", "content": user_content}]
            )
            raw = (raw or "").strip().upper()
            if not raw or "NONE" in raw:
                return None, []

            ids = [x.strip() for x in raw.split(",") if x.strip()]
            matched_prods = [p for p in self.products if p.id in ids]

            if len(matched_prods) == 1:
                return matched_prods[0], []
            elif len(matched_prods) > 1:
                return None, matched_prods
        except Exception:
            pass

        return None, []

    def _find_matches(self, search_text: str) -> List[Product]:
        if not search_text:
            return []
        matches: List[Product] = []
        for p in self.products:
            names_to_check = [p.name] + (p.aliases or [])
            is_matched = False
            for alias in names_to_check:
                alias_norm = normalize_text(alias)
                if not alias_norm:
                    continue
                pattern = r'(?:\b|\W|^)' + re.escape(alias_norm) + r'(?:\b|\W|$)'
                if re.search(pattern, search_text, re.IGNORECASE):
                    is_matched = True
                    break
            if is_matched:
                matches.append(p)
        return matches
