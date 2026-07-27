from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[2]
VALIDATOR_PATH = ROOT / "skills" / "mcubuddy" / "scripts" / "validate_skill.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mcubuddy_skill_validator", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frontmatter_validation_rejects_non_trigger_description() -> None:
    validator = _load_validator()
    text = "---\nname: mcubuddy\ndescription: Debug MCU boards\n---\n\n# mcubuddy\n"

    errors = validator.validate_frontmatter(text, expected_name="mcubuddy")

    assert "description must start with 'Use when '" in errors


def test_frontmatter_validation_accepts_current_skill() -> None:
    validator = _load_validator()
    text = (ROOT / "skills" / "mcubuddy" / "SKILL.md").read_text(encoding="utf-8")

    assert validator.validate_frontmatter(text, expected_name="mcubuddy") == []


def test_skill_body_validation_enforces_concise_main_file() -> None:
    validator = _load_validator()
    text = "---\nname: mcubuddy\ndescription: Use when debugging boards\n---\n\n" + (
        "word " * 601
    )

    assert validator.validate_body(text) == ["SKILL.md exceeds 600 words"]


def test_skill_uses_user_registry_without_mutating_itself() -> None:
    text = (ROOT / "skills" / "mcubuddy" / "SKILL.md").read_text(encoding="utf-8")

    assert "McuBuddy home show --json" in text
    assert "McuBuddy home set" in text
    assert "Never write a local checkout path into `SKILL.md`" in text


def test_skill_is_self_contained_without_copied_markdown_references() -> None:
    validator = _load_validator()

    assert validator.validate_links(ROOT / "skills" / "mcubuddy") == []
    references = ROOT / "skills" / "mcubuddy" / "references"
    assert not references.exists() or not list(references.glob("*.md"))
