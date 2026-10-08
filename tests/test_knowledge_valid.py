from src.knowledge.loader import KnowledgeBase
from src.config import KNOWLEDGE_DIR


def test_shipped_knowledge_parses_cleanly():
    # The app silently skips broken rules at runtime, so a typo in a rule file
    # would drop rules without any visible error. This test is the gate.
    assert KnowledgeBase(KNOWLEDGE_DIR).errors == []


def test_broken_rule_yaml_is_reported(tmp_path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "rules.md").write_text(
        "```yaml\n- id: r1\n  when: [unclosed\n```\n", encoding="utf-8"
    )
    errors = KnowledgeBase(tmp_path).errors
    assert len(errors) == 1 and errors[0].startswith("meta/rules.md: invalid YAML")
