from __future__ import annotations

from pathlib import Path
import re

from McuBuddy.tool_profiles import CORE_TOOL_NAMES
from McuBuddy.tool_catalog_docs import render_tool_catalog_markdown


ROOT = Path(__file__).parents[2]
SKILL_PATH = ROOT / "skills" / "mcubuddy" / "SKILL.md"
TOOL_CALL_RE = re.compile(r"`([a-z][a-z0-9_]*)\([^`]*\)`")
GENERATED_CATALOG_PATH = ROOT / "docs" / "tool-catalog.generated.md"


def test_generated_tool_catalog_is_current() -> None:
    assert GENERATED_CATALOG_PATH.read_text(encoding="utf-8") == render_tool_catalog_markdown()


def test_generated_tool_catalog_groups_every_public_tool() -> None:
    catalog = render_tool_catalog_markdown()

    assert "# Generated MCP Tool Catalog" in catalog
    assert "## default" in catalog
    assert "## diagnose" in catalog
    assert "## experimental" in catalog
    assert "`diagnose`" in catalog
    assert sum(line.startswith("| `") for line in catalog.splitlines()) == 118


def test_evaluation_scenarios_are_parseable_and_complete() -> None:
    text = (ROOT / "tests" / "evaluation" / "gpt5p6_scenarios.yaml").read_text(encoding="utf-8")

    for scenario_id in [
        "board-bring-up",
        "hardfault-evidence",
        "uart-no-output",
        "freertos-stall",
        "keil-build-flash-verify",
        "new-user-project-memory",
    ]:
        assert f"id: {scenario_id}" in text
    assert text.count("baseline:") == 6
    assert "executed: false" in text


def test_project_guides_document_core_and_full_profiles() -> None:
    for relative_path in ["PROJECT_GUIDE.md", "PROJECT_GUIDE_zh.md"]:
        guide = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "MCUBUDDY_TOOL_PROFILE" in guide
        assert "core" in guide
        assert "full" in guide


def test_documented_core_tools_match_code_allowlist() -> None:
    reference = (ROOT / "docs" / "tool-reference.md").read_text(encoding="utf-8")

    missing = {name for name in CORE_TOOL_NAMES if name not in reference}

    assert missing == set()


def test_skill_resumes_known_projects_before_first_contact() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert "Target Project Memory" in skill
    assert "`inspect_project_memory(...)`" in skill
    assert "never write another firmware project's memory into the McuBuddy repository" in skill
    assert "Known Project Resume" in skill
    assert "`get_runtime_config()`" in skill
    assert "Do not run `first_contact()`" in skill
    assert "`doctor()`" in skill
    assert "`first_contact()`" in skill
    assert skill.index("`inspect_project_memory(...)`") < skill.index("`get_runtime_config()`")
    assert skill.index("`get_runtime_config()`") < skill.index("`first_contact()`")
    assert skill.index("Known Project Resume") < skill.index("Default Flow")


def test_skill_marks_every_hidden_tool_call_with_a_startup_boundary() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    unmarked: list[str] = []

    for line_number, line in enumerate(skill.splitlines(), start=1):
        for tool_name in TOOL_CALL_RE.findall(line):
            if (
                tool_name not in CORE_TOOL_NAMES
                and "toolset" not in line.lower()
                and "full-only" not in line.lower()
            ):
                unmarked.append(f"{line_number}:{tool_name}")

    assert unmarked == []


def test_skill_body_stays_concise() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert len(skill.split()) <= 600


def test_project_guides_document_management_and_rtt_safety_preflight() -> None:
    for relative_path in ["PROJECT_GUIDE.md", "PROJECT_GUIDE_zh.md"]:
        guide = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "McuBuddy.exe doctor --json" in guide
        assert "McuBuddy.exe config show --json" in guide
        assert "MCUBUDDY_MAX_RTT_SCAN_SIZE" in guide


def test_session_workflows_resume_config_before_first_contact() -> None:
    for relative_path in ["PROJECT_GUIDE.md", "PROJECT_GUIDE_zh.md"]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "get_runtime_config()" in text, relative_path
        assert "doctor()" in text, relative_path
        assert "first_contact()" in text, relative_path
        assert text.index("get_runtime_config()") < text.index("first_contact()")


def test_new_board_workflow_keeps_full_preflight() -> None:
    for relative_path in ["PROJECT_GUIDE.md", "PROJECT_GUIDE_zh.md"]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "doctor()" in text
        assert "first_contact()" in text
        assert text.index("doctor()") < text.index("configure_probe(")
        assert text.index("first_contact()") < text.index("configure_probe(")
