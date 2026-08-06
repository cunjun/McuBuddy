from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_docs import validate_repository


UPSTREAM_URL = "https://github.com/SolarWang233/mcudbg"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_repo(tmp_path: Path) -> Path:
    _write(
        tmp_path / "src" / "McuBuddy" / "tool_profiles.py",
        "CORE_TOOL_NAMES = frozenset({'doctor', 'probe_connect'})\n",
    )
    _write(
        tmp_path / "src" / "McuBuddy" / "tool_safety.py",
        "DEFAULT_TOOL_NAMES = frozenset({'doctor', 'probe_connect'})\n"
        "TOOL_POLICIES = {'doctor': {}, 'probe_connect': {}, 'diagnose': {}}\n"
        "CONCURRENT_TOOLS = frozenset({'list_supported_targets'})\n",
    )
    _write(
        tmp_path / "README.md",
        "default core\nMCUBUDDY_TOOLSETS\n[Project Guide](PROJECT_GUIDE.md)\n"
        "[Tool Reference](docs/tool-reference.md)\nexecution-changing\n"
        f"Upstream: {UPSTREAM_URL}\n",
    )
    _write(
        tmp_path / "README_zh.md",
        "默认 core\nMCUBUDDY_TOOLSETS\n[项目指南](PROJECT_GUIDE_zh.md)\n"
        "[工具参考](docs/tool-reference.md)\n执行状态变化\n"
        f"上游：{UPSTREAM_URL}\n",
    )
    sections = (
        "<!-- guide-section:positioning -->\n"
        "<!-- guide-section:maintenance -->\n"
        "src/McuBuddy/mcp_execution.py\n"
        "src/McuBuddy/tool_safety.py\n"
        "src/McuBuddy/tool_profiles.py\n"
        "SessionToolRegistrar\nProbeBackend\ncore\nMCUBUDDY_TOOLSETS\n"
    )
    _write(tmp_path / "PROJECT_GUIDE.md", "# Guide\n\n> Project version: 0.5.2\n" + sections)
    _write(
        tmp_path / "PROJECT_GUIDE_zh.md",
        "# 指南\n\n> 项目版本：0.5.2\n" + sections,
    )
    _write(tmp_path / "docs" / "tool-reference.md", "# Tools\n")
    _write(
        tmp_path / "LICENSE",
        "MIT License\n\nCopyright (c) 2026 SolarWang233\n",
    )
    _write(tmp_path / "NOTICE", f"Upstream: {UPSTREAM_URL}\n")
    _write(
        tmp_path / "pyproject.toml",
        f'[project]\nversion = "0.5.2"\n[project.urls]\nUpstream = "{UPSTREAM_URL}"\n',
    )
    return tmp_path


def test_valid_repository_contract_passes(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    _write(
        repo / "docs" / "example.md",
        "<!-- mcubuddy-profile: core -->\n"
        "1. `doctor()`\n2. `probe_connect()`\n"
        "<!-- /mcubuddy-profile -->\n",
    )
    assert validate_repository(repo) == []


def test_core_region_rejects_toolset_required_tool(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    _write(
        repo / "docs" / "example.md",
        "<!-- mcubuddy-profile: core -->\n`diagnose()`\n<!-- /mcubuddy-profile -->\n",
    )
    assert any(
        "toolset-required tool 'diagnose'" in error for error in validate_repository(repo)
    )


def test_profile_region_requires_closing_marker(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    _write(repo / "docs" / "example.md", "<!-- mcubuddy-profile: core -->\n`doctor()`\n")
    assert any(
        "missing <!-- /mcubuddy-profile -->" in error
        for error in validate_repository(repo)
    )


def test_profile_region_rejects_unmatched_closing_marker(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    _write(repo / "docs" / "example.md", "<!-- /mcubuddy-profile -->\n")
    assert any(
        "unmatched <!-- /mcubuddy-profile -->" in error
        for error in validate_repository(repo)
    )


def test_current_docs_reject_stale_refs_but_history_preserves_them(
    tmp_path: Path,
) -> None:
    repo = _minimal_repo(tmp_path)
    _write(repo / "docs" / "guide.md", "Update `PROGRESS.md`.\n")
    _write(repo / "docs" / "plans" / "old.md", "Update `PROGRESS.md`.\n")
    _write(repo / "docs" / "archive" / "old.md", "Update `README_CN.md`.\n")
    errors = validate_repository(repo)
    assert sum("PROGRESS.md" in error for error in errors) == 1
    assert not any("docs/archive/old.md" in error for error in errors)


def test_broken_relative_markdown_link_is_reported(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    _write(repo / "docs" / "guide.md", "[Missing](missing.md)\n")
    assert any("broken link 'missing.md'" in error for error in validate_repository(repo))


def test_readmes_must_share_critical_contract_tokens(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / "README_zh.md").write_text("[项目指南](PROJECT_GUIDE_zh.md)\n", encoding="utf-8")
    assert any(
        "README_zh.md: missing critical token" in error
        for error in validate_repository(repo)
    )


def test_current_docs_define_local_stdio_installation_contract() -> None:
    root = Path(__file__).parents[2]
    english = (root / "README.md").read_text(encoding="utf-8")
    chinese = (root / "README_zh.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "architecture.md").read_text(encoding="utf-8")

    for text in (english, chinese):
        assert "stdio" in text
        assert "https://github.com/cunjun/McuBuddy" in text
        assert "HTTP" in text and "WebSocket" in text
    assert "automatic" in english.lower()
    assert "自动" in chinese
    assert "separate process" in architecture


def test_project_guides_must_have_matching_section_ids(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    path = repo / "PROJECT_GUIDE_zh.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "<!-- guide-section:maintenance -->",
            "<!-- guide-section:different -->",
        ),
        encoding="utf-8",
    )

    assert "project guides: section IDs are not synchronized" in validate_repository(repo)


def test_project_guides_must_match_package_version(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    path = repo / "PROJECT_GUIDE.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Project version: 0.5.2", "Project version: 0.5.1"),
        encoding="utf-8",
    )

    assert "PROJECT_GUIDE.md: project version must be 0.5.2" in validate_repository(repo)


def test_project_guides_must_cover_architecture_contract(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    path = repo / "PROJECT_GUIDE.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("SessionToolRegistrar", ""),
        encoding="utf-8",
    )

    assert (
        "PROJECT_GUIDE.md: missing project-guide contract token 'SessionToolRegistrar'"
        in validate_repository(repo)
    )


def test_missing_tool_contract_fails_closed(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / "src" / "McuBuddy" / "tool_safety.py").write_text(
        "TOOL_POLICIES = {'doctor': {}}\n",
        encoding="utf-8",
    )
    assert any(
        "unable to load DEFAULT_TOOL_NAMES" in error for error in validate_repository(repo)
    )


def test_upstream_attribution_is_required(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    assert any(
        "LICENSE: missing upstream copyright" in error
        for error in validate_repository(repo)
    )


@pytest.mark.parametrize(
    ("relative_path", "expected_error"),
    (
        ("NOTICE", "NOTICE: missing upstream URL"),
        ("README.md", "README.md: missing upstream URL"),
        ("README_zh.md", "README_zh.md: missing upstream URL"),
        ("pyproject.toml", "pyproject.toml: missing upstream URL"),
    ),
)
def test_upstream_url_is_required_in_project_metadata(
    tmp_path: Path,
    relative_path: str,
    expected_error: str,
) -> None:
    repo = _minimal_repo(tmp_path)
    path = repo / relative_path
    path.write_text(path.read_text(encoding="utf-8").replace(UPSTREAM_URL, ""), encoding="utf-8")
    assert expected_error in validate_repository(repo)
