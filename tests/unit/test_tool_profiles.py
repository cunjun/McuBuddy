from __future__ import annotations

import pytest

from McuBuddy.tool_profiles import (
    CORE_TOOL_NAMES,
    FULL_TOOL_NAMES,
    PROFILE_ENV_VAR,
    TOOL_CATALOG,
    ToolProfile,
    ToolProfileError,
    resolve_tool_profile,
)
from McuBuddy.tool_safety import TOOL_POLICIES


def test_default_profile_is_core() -> None:
    profile = resolve_tool_profile(environ={})

    assert profile.name == "core"
    assert profile.enabled_tool_names == CORE_TOOL_NAMES
    assert profile.allows("doctor") is True
    assert profile.allows("diagnose") is False
    assert profile.allows("probe_write_memory") is False


def test_environment_can_select_full_profile() -> None:
    profile = resolve_tool_profile(environ={PROFILE_ENV_VAR: "full"})

    assert profile.name == "full"
    assert profile.enabled_tool_names == FULL_TOOL_NAMES
    assert profile.allows("diagnose") is True


def test_full_profile_is_an_explicit_catalog_allowlist() -> None:
    assert isinstance(FULL_TOOL_NAMES, frozenset)
    assert FULL_TOOL_NAMES == frozenset(TOOL_CATALOG)
    assert FULL_TOOL_NAMES == frozenset(TOOL_POLICIES)
    assert resolve_tool_profile("full").allows("unregistered_future_tool") is False


def test_tool_catalog_carries_governance_metadata() -> None:
    assert CORE_TOOL_NAMES == frozenset(
        name for name, spec in TOOL_CATALOG.items() if spec.default_enabled
    )
    assert all(spec.name == name for name, spec in TOOL_CATALOG.items())
    assert all(
        spec.safety_level == TOOL_POLICIES[name]["level"] for name, spec in TOOL_CATALOG.items()
    )
    assert all(spec.toolsets for spec in TOOL_CATALOG.values())
    assert all(
        spec.stability in {"stable", "preview", "experimental"} for spec in TOOL_CATALOG.values()
    )


def test_tool_catalog_is_immutable_after_startup() -> None:
    with pytest.raises(TypeError):
        TOOL_CATALOG["runtime_added_tool"] = TOOL_CATALOG["doctor"]  # type: ignore[index]


def test_tool_profile_rejects_an_unbounded_allowlist() -> None:
    with pytest.raises(ValueError, match="explicit tool allowlist"):
        ToolProfile(name="full", enabled_tool_names=None)  # type: ignore[arg-type]


def test_explicit_profile_overrides_environment() -> None:
    profile = resolve_tool_profile("core", environ={PROFILE_ENV_VAR: "full"})

    assert profile.name == "core"


def test_profile_values_are_case_and_whitespace_tolerant() -> None:
    assert resolve_tool_profile(" FULL ").name == "full"


def test_unknown_profile_lists_valid_values() -> None:
    with pytest.raises(ToolProfileError, match="core, full"):
        resolve_tool_profile("expert", environ={})


def test_core_tool_names_are_unique_and_immutable() -> None:
    assert isinstance(CORE_TOOL_NAMES, frozenset)
    assert len(CORE_TOOL_NAMES) == len(set(CORE_TOOL_NAMES))


def test_core_profile_exposes_read_only_runtime_config_for_resume() -> None:
    assert "get_runtime_config" in CORE_TOOL_NAMES


def test_core_profile_exposes_target_project_memory_tools() -> None:
    assert "inspect_project_memory" in CORE_TOOL_NAMES
    assert "write_project_memory" in CORE_TOOL_NAMES
