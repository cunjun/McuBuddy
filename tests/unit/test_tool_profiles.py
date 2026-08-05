from __future__ import annotations

import pytest

from McuBuddy.tool_profiles import (
    CORE_TOOL_NAMES,
    PROFILE_ENV_VAR,
    TOOL_CATALOG,
    VALID_TOOLSETS,
    ToolProfile,
    ToolProfileError,
    resolve_tool_profile,
)
from McuBuddy.tool_safety import TOOL_POLICIES


def test_default_profile_is_core() -> None:
    profile = resolve_tool_profile(environ={})

    assert profile.name == "core"
    assert profile.enabled_tool_names == CORE_TOOL_NAMES
    assert len(CORE_TOOL_NAMES) == 19
    assert profile.allows("doctor") is True
    assert profile.allows("diagnose") is False
    assert profile.allows("probe_write_memory") is False
    assert profile.allows("build_project") is False
    assert profile.allows("collect_crash_evidence") is False


def test_removed_full_profile_is_rejected() -> None:
    with pytest.raises(ToolProfileError, match="Valid values are: core"):
        resolve_tool_profile(environ={PROFILE_ENV_VAR: "full"})


def test_tool_catalog_carries_governance_metadata() -> None:
    assert VALID_TOOLSETS == frozenset(
        {"default", "probe", "diagnose", "build_flash", "rtos", "logs", "experimental"}
    )
    assert CORE_TOOL_NAMES == frozenset(
        name for name, spec in TOOL_CATALOG.items() if spec.default_enabled
    )
    assert all(spec.name == name for name, spec in TOOL_CATALOG.items())
    assert all(
        spec.safety_level == TOOL_POLICIES[name]["level"] for name, spec in TOOL_CATALOG.items()
    )
    assert all(spec.toolsets for spec in TOOL_CATALOG.values())
    assert all(spec.toolsets <= VALID_TOOLSETS for spec in TOOL_CATALOG.values())
    assert all(len(spec.toolsets) == 1 for spec in TOOL_CATALOG.values())
    assert all(spec.owner for spec in TOOL_CATALOG.values())
    assert all(spec.schema_version == 1 for spec in TOOL_CATALOG.values())
    assert all(spec.deprecated is False for spec in TOOL_CATALOG.values())
    assert all(
        spec.stability in {"stable", "preview", "experimental"} for spec in TOOL_CATALOG.values()
    )


def test_tool_catalog_is_immutable_after_startup() -> None:
    with pytest.raises(TypeError):
        TOOL_CATALOG["runtime_added_tool"] = TOOL_CATALOG["doctor"]  # type: ignore[index]


def test_tool_profile_rejects_an_unbounded_allowlist() -> None:
    with pytest.raises(ValueError, match="explicit tool allowlist"):
        ToolProfile(name="core", enabled_tool_names=None)  # type: ignore[arg-type]


def test_tool_policies_hold_explicit_governance_metadata() -> None:
    required = {
        "level",
        "execution",
        "toolsets",
        "owner",
        "stability",
        "schema_version",
        "deprecated",
        "default_enabled",
    }

    assert all(required <= policy.keys() for policy in TOOL_POLICIES.values())


def test_core_profile_can_add_explicit_domain_toolsets() -> None:
    profile = resolve_tool_profile("core", toolsets=["diagnose"])

    expected = CORE_TOOL_NAMES | frozenset(
        name for name, spec in TOOL_CATALOG.items() if "diagnose" in spec.toolsets
    )
    assert profile.enabled_tool_names == expected
    assert profile.selected_toolsets == frozenset({"diagnose"})
    assert profile.allows("diagnose") is True


def test_unknown_toolset_selection_is_rejected() -> None:
    with pytest.raises(ToolProfileError, match="Unknown McuBuddy toolset"):
        resolve_tool_profile("core", toolsets=["mystery"])


def test_explicit_profile_overrides_environment() -> None:
    profile = resolve_tool_profile("core", environ={PROFILE_ENV_VAR: "invalid"})

    assert profile.name == "core"


def test_profile_values_are_case_and_whitespace_tolerant() -> None:
    assert resolve_tool_profile(" CORE ").name == "core"


def test_unknown_profile_lists_valid_values() -> None:
    with pytest.raises(ToolProfileError, match="Valid values are: core"):
        resolve_tool_profile("expert", environ={})


def test_core_tool_names_are_unique_and_immutable() -> None:
    assert isinstance(CORE_TOOL_NAMES, frozenset)
    assert len(CORE_TOOL_NAMES) == len(set(CORE_TOOL_NAMES))


def test_core_profile_exposes_read_only_runtime_config_for_resume() -> None:
    assert "get_runtime_config" in CORE_TOOL_NAMES


def test_core_profile_exposes_target_project_memory_tools() -> None:
    assert "inspect_project_memory" in CORE_TOOL_NAMES
    assert "write_project_memory" in CORE_TOOL_NAMES
