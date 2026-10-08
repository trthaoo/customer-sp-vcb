import re
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.knowledge.rag_store import KnowledgeChunk
from src.knowledge.loader import strip_example_blocks, is_meaningful_content
from src.config import KNOWLEDGE_DIR

class KnowledgeChunker:
    """
    Splits all knowledge documents and product catalogue across the project
    into high-quality, semantically coherent chunks for RAG embedding.
    """
    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR

    def chunk_all(self) -> List[KnowledgeChunk]:
        chunks: List[KnowledgeChunk] = []
        chunks.extend(self.chunk_catalogue())
        chunks.extend(self.chunk_policies())
        chunks.extend(self.chunk_shared())
        chunks.extend(self.chunk_funnels())
        return chunks

    def chunk_catalogue(self) -> List[KnowledgeChunk]:
        chunks: List[KnowledgeChunk] = []
        live_file = self.knowledge_dir / "catalogue" / "products.json"
        template_file = self.knowledge_dir / "catalogue" / "products.template.json"
        target = live_file if live_file.exists() else template_file

        if not target.exists():
            return chunks

        try:
            with open(target, "r", encoding="utf-8") as f:
                raw = f.read()
            cleaned = strip_example_blocks(raw)
            data = json.loads(cleaned)
            prods = data.get("products", [])

            for p in prods:
                if not isinstance(p, dict):
                    continue
                pid = p.get("id", "")
                name = p.get("name", "")
                aliases = p.get("aliases", [])
                price = p.get("price")
                price_usd = p.get("price_usd")
                materials = p.get("materials", "")
                craftsmanship = p.get("craftsmanship", "")
                desc = p.get("description", "")
                care = p.get("care_notes", "")
                sizing = p.get("sizing", "")
                variants = p.get("variants", [])

                # Format USD price
                price_usd_str = f"${price_usd:.2f}" if price_usd is not None else "Price available upon request"
                price_vnd_str = f"{int(price):,}đ" if price is not None else ""

                variant_summary = ""
                if variants:
                    v_texts = [f"{v.get('name', '')} ({v.get('sku', '')})" for v in variants if isinstance(v, dict)]
                    variant_summary = ", ".join(v_texts[:6])

                content_lines = [
                    f"Product Name: {name}",
                    f"Product ID / SKU: {pid}",
                    f"Search Aliases: {', '.join(aliases)}",
                    f"USD Price: {price_usd_str}",
                ]
                if price_vnd_str:
                    content_lines.append(f"VND Price: {price_vnd_str}")
                if materials:
                    content_lines.append(f"Material: {materials}")
                if craftsmanship:
                    content_lines.append(f"Craftsmanship: {craftsmanship}")
                if sizing:
                    content_lines.append(f"Sizing & Fit: {sizing}")
                if care:
                    content_lines.append(f"Care Instructions: {care}")
                if variant_summary:
                    content_lines.append(f"Available Variants: {variant_summary}")
                if desc:
                    content_lines.append(f"Description: {desc}")

                chunk_content = "\n".join(content_lines)

                chunks.append(KnowledgeChunk(
                    id=f"catalogue::{pid}",
                    category="catalogue",
                    source_file=f"catalogue/{target.name}",
                    title=f"Jewelry Piece: {name}",
                    content=chunk_content,
                    metadata={
                        "product_id": pid,
                        "product_name": name,
                        "aliases": aliases,
                        "price_usd": price_usd,
                        "price": price,
                        "materials": materials
                    }
                ))
        except Exception as e:
            print(f"Warning: Error chunking catalogue: {e}")

        return chunks

    def chunk_policies(self) -> List[KnowledgeChunk]:
        chunks: List[KnowledgeChunk] = []
        policy_files = ["shipping", "warranty", "returns", "payment", "promotions"]

        for pf in policy_files:
            file_path = self.knowledge_dir / "policies" / f"{pf}.md"
            if not file_path.exists():
                continue

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()

            cleaned = strip_example_blocks(raw)
            if not is_meaningful_content(cleaned):
                continue

            # Split by markdown headers ## or ###
            sections = re.split(r'\n(?=##\s+)', cleaned)
            for idx, sec in enumerate(sections):
                sec_trimmed = sec.strip()
                if not sec_trimmed:
                    continue

                lines = sec_trimmed.splitlines()
                title_line = lines[0].replace("#", "").strip() if lines else f"{pf.capitalize()} Policy Part {idx+1}"

                # Ensure section has meaningful body
                body_lines = lines[1:] if len(lines) > 1 else lines
                body_text = "\n".join(body_lines).strip()
                if not body_text:
                    continue

                chunk_id = f"policy::{pf}::{idx+1}"
                chunks.append(KnowledgeChunk(
                    id=chunk_id,
                    category="policy",
                    source_file=f"policies/{pf}.md",
                    title=f"Policy ({pf.capitalize()}): {title_line}",
                    content=sec_trimmed,
                    metadata={
                        "policy_type": pf,
                        "section_title": title_line
                    }
                ))

        return chunks

    def chunk_shared(self) -> List[KnowledgeChunk]:
        chunks: List[KnowledgeChunk] = []
        shared_dir = self.knowledge_dir / "shared"
        if not shared_dir.exists():
            return chunks

        # 1. Brand voice - split by Rules (### Rule ...)
        brand_voice_path = shared_dir / "brand_voice.md"
        if brand_voice_path.exists():
            with open(brand_voice_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_bv = f.read()
            cleaned_bv = strip_example_blocks(raw_bv)

            rule_sections = re.split(r'\n(?=###\s+Rule\s+)', cleaned_bv)
            for idx, sec in enumerate(rule_sections):
                sec_trimmed = sec.strip()
                if not sec_trimmed:
                    continue
                first_line = sec_trimmed.splitlines()[0].replace("#", "").strip()
                chunks.append(KnowledgeChunk(
                    id=f"shared::brand_voice::part_{idx+1}",
                    category="shared",
                    source_file="shared/brand_voice.md",
                    title=f"Brand Voice: {first_line}",
                    content=sec_trimmed,
                    metadata={"topic": "brand_voice", "rule": first_line}
                ))

        # 2. Other shared files (brand_overview, escalation, fallbacks, intents)
        for sf in ["brand_overview.md", "escalation.md", "fallbacks.md", "intents.md"]:
            fp = shared_dir / sf
            if not fp.exists():
                continue
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            cleaned = strip_example_blocks(raw)
            if not is_meaningful_content(cleaned):
                continue

            sections = re.split(r'\n(?=##\s+)', cleaned)
            for idx, sec in enumerate(sections):
                sec_trimmed = sec.strip()
                if not sec_trimmed:
                    continue
                first_line = sec_trimmed.splitlines()[0].replace("#", "").strip()
                base_name = sf.replace(".md", "")
                chunks.append(KnowledgeChunk(
                    id=f"shared::{base_name}::{idx+1}",
                    category="shared",
                    source_file=f"shared/{sf}",
                    title=f"Shared Knowledge ({base_name}): {first_line}",
                    content=sec_trimmed,
                    metadata={"topic": base_name, "section": first_line}
                ))

        return chunks

    def chunk_funnels(self) -> List[KnowledgeChunk]:
        chunks: List[KnowledgeChunk] = []

        # Meta & TikTok rules / edge cases
        for channel in ["meta", "tiktok"]:
            # Rules
            rf = self.knowledge_dir / channel / "rules.md"
            if rf.exists():
                with open(rf, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read()
                cleaned = strip_example_blocks(raw)
                blocks = re.findall(r'```(?:yaml|yml)?\s*\n(.*?)\n```', cleaned, re.DOTALL)
                for block in blocks:
                    try:
                        data = yaml.safe_load(block)
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if not isinstance(item, dict) or "id" not in item:
                                continue
                            rid = item["id"]
                            surface = item.get("surface", "any")
                            when = item.get("when", {})
                            intent = when.get("intent", "") if isinstance(when, dict) else ""
                            guide = item.get("reply_guide", "")
                            example = item.get("example_good_reply", "")

                            content = (
                                f"Channel: {channel.upper()}\n"
                                f"Rule ID: {rid}\n"
                                f"Surface: {surface}\n"
                                f"Intent: {intent}\n"
                                f"Reply Guidance:\n{guide}\n"
                            )
                            if example:
                                content += f"\nHuman Response Example:\n{example}"

                            chunks.append(KnowledgeChunk(
                                id=f"{channel}::rule::{rid}",
                                category=f"{channel}_rule",
                                source_file=f"{channel}/rules.md",
                                title=f"{channel.capitalize()} Rule: {rid} ({intent or surface})",
                                content=content,
                                metadata={
                                    "channel": channel,
                                    "surface": surface,
                                    "intent": intent,
                                    "rule_id": rid
                                }
                            ))
                    except Exception as e:
                        print(f"Warning: Error parsing {channel} rule block: {e}")

            # Edge Cases
            ef = self.knowledge_dir / channel / "edge_cases.md"
            if ef.exists():
                with open(ef, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read()
                cleaned = strip_example_blocks(raw)
                blocks = re.findall(r'```(?:yaml|yml)?\s*\n(.*?)\n```', cleaned, re.DOTALL)
                for block in blocks:
                    try:
                        data = yaml.safe_load(block)
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if not isinstance(item, dict) or "id" not in item:
                                continue
                            ec_id = item["id"]
                            handover = item.get("handover", False)
                            guide = item.get("reply_guide", "")
                            example = item.get("example_good_reply", "")

                            content = (
                                f"Channel: {channel.upper()}\n"
                                f"Edge Case ID: {ec_id}\n"
                                f"Requires Handover: {handover}\n"
                                f"Reply Guidance:\n{guide}\n"
                            )
                            if example:
                                content += f"\nHuman Response Example:\n{example}"

                            chunks.append(KnowledgeChunk(
                                id=f"{channel}::edge_case::{ec_id}",
                                category=f"{channel}_edge_case",
                                source_file=f"{channel}/edge_cases.md",
                                title=f"{channel.capitalize()} Edge Case: {ec_id}",
                                content=content,
                                metadata={
                                    "channel": channel,
                                    "edge_case_id": ec_id,
                                    "handover": handover
                                }
                            ))
                    except Exception as e:
                        print(f"Warning: Error parsing {channel} edge case block: {e}")

        return chunks
