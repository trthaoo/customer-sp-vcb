import re
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from src.models import Product, Rule, EdgeCase
from src.config import KNOWLEDGE_DIR

EXAMPLE_PATTERNS = [
    re.compile(r'<!--\s*EXAMPLE_DELETE_ME\s*-->.*?<!--\s*/EXAMPLE_DELETE_ME\s*-->', re.DOTALL | re.IGNORECASE),
    re.compile(r'\[EXAMPLE_DELETE_ME\].*?\[/EXAMPLE_DELETE_ME\]', re.DOTALL | re.IGNORECASE),
    re.compile(r'BEGIN_EXAMPLE_DELETE_ME.*?END_EXAMPLE_DELETE_ME', re.DOTALL | re.IGNORECASE),
]

def strip_example_blocks(content: str) -> str:
    """Strips all EXAMPLE_DELETE_ME blocks from the input string."""
    cleaned = content
    for pattern in EXAMPLE_PATTERNS:
        cleaned = pattern.sub('', cleaned)
    return cleaned

def is_meaningful_content(text: str) -> bool:
    """
    Checks if a markdown document has actual policy/business facts,
    ignoring headings, TODO comments, and blank lines.
    """
    cleaned = strip_example_blocks(text)
    # Remove html comments <!-- ... -->
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    # Remove markdown headers and whitespace
    meaningful_lines = []
    for line in cleaned.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith('#') or trimmed.startswith('##') or trimmed.startswith('###'):
            continue
        if trimmed.lower().startswith('purpose:') or trimmed.lower().startswith('purpose'):
            continue
        meaningful_lines.append(trimmed)
    return len(meaningful_lines) > 0

class KnowledgeBase:
    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        self.brand_voice: str = ""
        self.brand_overview: str = ""
        self.escalation_guide: str = ""
        self.fallbacks: Dict[str, str] = {}
        self.default_fallback: str = "Let me double-check this exact piece with our studio workshop and get right back to you! ✨"
        self.intents: List[str] = []
        self.meta_rules: List[Rule] = []
        self.meta_edge_cases: List[EdgeCase] = []
        self.tiktok_rules: List[Rule] = []
        self.tiktok_edge_cases: List[EdgeCase] = []
        self.policies: Dict[str, str] = {}
        self.products: List[Product] = []
        # Parse problems the app skips at runtime; tests/test_knowledge_valid.py fails on any.
        self.errors: List[str] = []
        self.load_all()

    def _read_file(self, rel_path: str) -> str:
        file_path = self.knowledge_dir / rel_path
        if not file_path.exists():
            return ""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        return strip_example_blocks(raw)

    def load_all(self):
        # 1. Load Shared
        self.brand_voice = self._read_file("shared/brand_voice.md")
        self.brand_overview = self._read_file("shared/brand_overview.md")
        self.escalation_guide = self._read_file("shared/escalation.md")
        
        fallbacks_content = self._read_file("shared/fallbacks.md")
        self._parse_fallbacks(fallbacks_content)
        
        intents_content = self._read_file("shared/intents.md")
        self._parse_intents(intents_content)

        # 2. Load Meta
        meta_rules_content = self._read_file("meta/rules.md")
        self.meta_rules = self._parse_rules(meta_rules_content, default_channel="meta")

        meta_edge_cases_content = self._read_file("meta/edge_cases.md")
        self.meta_edge_cases = self._parse_edge_cases(meta_edge_cases_content, default_channel="meta")

        # 3. Load TikTok
        tiktok_rules_content = self._read_file("tiktok/rules.md")
        self.tiktok_rules = self._parse_rules(tiktok_rules_content, default_channel="tiktok")

        tiktok_edge_cases_content = self._read_file("tiktok/edge_cases.md")
        self.tiktok_edge_cases = self._parse_edge_cases(tiktok_edge_cases_content, default_channel="tiktok")

        # 4. Load Policies
        policy_files = ["shipping", "returns", "warranty", "payment", "promotions"]
        for p in policy_files:
            content = self._read_file(f"policies/{p}.md")
            self.policies[p] = content if is_meaningful_content(content) else ""

        # 5. Load Catalogue
        self._load_catalogue()

    def _parse_fallbacks(self, content: str):
        self.fallbacks = {}
        # Find default fallback under ## Default Fallback
        match = re.search(r'##\s*Default Fallback\s*\n+([^\n#]+)', content, re.IGNORECASE)
        if match:
            self.default_fallback = match.group(1).strip()
            self.fallbacks["default"] = self.default_fallback
        else:
            self.fallbacks["default"] = self.default_fallback

        match_ambig = re.search(r'##\s*Ambiguous Product Fallback\s*\n+([^\n#]+)', content, re.IGNORECASE)
        if match_ambig:
            self.fallbacks["ambiguous_product"] = match_ambig.group(1).strip()
        else:
            self.fallbacks["ambiguous_product"] = "We have a few similar artisan designs in our studio! Could you share a quick photo or the exact name of the piece you have your eye on so I can assist you accurately? 🤍"

        match_scope = re.search(r'##\s*Out Of Scope Fallback\s*\n+([^\n#]+)', content, re.IGNORECASE)
        if match_scope:
            self.fallbacks["out_of_scope"] = match_scope.group(1).strip()
        else:
            self.fallbacks["out_of_scope"] = self.default_fallback

    def _parse_intents(self, content: str):
        self.intents = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                intent_part = line[1:].strip().split(":")[0].strip()
                if intent_part:
                    self.intents.append(intent_part)

    def _extract_yaml_blocks(self, content: str, source: str = "") -> List[Any]:
        # Extract ```yaml ... ``` blocks
        results = []
        blocks = re.findall(r'```(?:yaml|yml)?\s*\n(.*?)\n```', content, re.DOTALL)
        for block in blocks:
            try:
                data = yaml.safe_load(block)
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
            except Exception as e:
                self.errors.append(f"{source}: invalid YAML block: {e}")
        return results

    def _parse_rules(self, content: str, default_channel: str) -> List[Rule]:
        data = self._extract_yaml_blocks(content, f"{default_channel}/rules.md")
        rules = []
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            item.setdefault("channel", default_channel)
            try:
                rule = Rule(**item)
                rules.append(rule)
            except Exception as e:
                self.errors.append(f"{default_channel}/rules.md: rule {item.get('id')}: {e}")
                print(f"Warning: Failed to parse rule {item.get('id')}: {e}")
        return rules

    def _parse_edge_cases(self, content: str, default_channel: str) -> List[EdgeCase]:
        data = self._extract_yaml_blocks(content, f"{default_channel}/edge_cases.md")
        edge_cases = []
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            item.setdefault("channel", default_channel)
            try:
                ec = EdgeCase(**item)
                edge_cases.append(ec)
            except Exception as e:
                self.errors.append(f"{default_channel}/edge_cases.md: edge case {item.get('id')}: {e}")
                print(f"Warning: Failed to parse edge case {item.get('id')}: {e}")
        return edge_cases

    def _load_catalogue(self):
        self.products = []
        live_file = self.knowledge_dir / "catalogue" / "products.json"
        template_file = self.knowledge_dir / "catalogue" / "products.template.json"
        
        target = live_file if live_file.exists() else template_file
        if not target.exists():
            return
        
        try:
            with open(target, "r", encoding="utf-8") as f:
                raw = f.read()
            cleaned = strip_example_blocks(raw)
            data = json.loads(cleaned)
            prods = data.get("products", [])
            for p in prods:
                if isinstance(p, dict):
                    self.products.append(Product(**p))
        except Exception as e:
            self.errors.append(f"catalogue/{target.name}: {e}")
            print(f"Warning: Could not load products from {target}: {e}")

_kb_instance: Optional[KnowledgeBase] = None

def get_knowledge_base() -> KnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance

def reload_knowledge_base() -> KnowledgeBase:
    global _kb_instance
    _kb_instance = KnowledgeBase()
    return _kb_instance
