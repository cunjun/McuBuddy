from __future__ import annotations

import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .tool_safety import DEFAULT_TOOL_NAMES, TOOL_POLICIES, TOOLSET_MEMBERS


PROFILE_ENV_VAR = "MCUBUDDY_TOOL_PROFILE"
TOOL_PROFILE_CORE = "core"
TOOL_PROFILE_FULL = "full"
VALID_TOOL_PROFILES = frozenset({TOOL_PROFILE_CORE, TOOL_PROFILE_FULL})
ToolProfileName = Literal["core", "full"]
ToolStability = Literal["stable", "preview", "experimental"]
CORE_TOOL_NAMES = DEFAULT_TOOL_NAMES
VALID_TOOLSETS = frozenset(TOOLSET_MEMBERS)


@dataclass(frozen=True)
class ToolSpec:
    """Governance metadata for one explicitly exposed MCP tool."""

    name: str
    safety_level: str
    toolsets: frozenset[str]
    stability: ToolStability
    owner: str
    schema_version: int
    deprecated: bool
    default_enabled: bool = False


TOOL_CATALOG = MappingProxyType(
    {
        name: ToolSpec(
            name=name,
            safety_level=policy["level"],
            toolsets=policy["toolsets"],
            stability=policy["stability"],
            owner=policy["owner"],
            schema_version=policy["schema_version"],
            deprecated=policy["deprecated"],
            default_enabled=policy["default_enabled"],
        )
        for name, policy in TOOL_POLICIES.items()
    }
)

# Both profiles are explicit allowlists. A newly decorated MCP callback remains hidden
# until it is deliberately added to the governed tool catalog above.
FULL_TOOL_NAMES = frozenset(TOOL_CATALOG)


@dataclass(frozen=True)
class ToolProfile:
    name: ToolProfileName
    enabled_tool_names: frozenset[str]
    selected_toolsets: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.enabled_tool_names is None:
            raise ValueError("Tool profiles require an explicit tool allowlist.")

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.enabled_tool_names


class ToolProfileError(ValueError):
    """Raised when a startup tool profile value is invalid."""


def _normalize_profile(value: str) -> ToolProfileName:
    normalized = value.strip().lower()
    if normalized in VALID_TOOL_PROFILES:
        return normalized  # type: ignore[return-value]
    options = ", ".join(sorted(VALID_TOOL_PROFILES))
    raise ToolProfileError(f"Unknown McuBuddy tool profile {value!r}. Valid values are: {options}.")


def resolve_tool_profile(
    explicit: str | None = None,
    *,
    environ: dict[str, str] | None = None,
    toolsets: list[str] | tuple[str, ...] | frozenset[str] | None = None,
) -> ToolProfile:
    value = explicit
    if value is None:
        env = os.environ if environ is None else environ
        value = env.get(PROFILE_ENV_VAR, TOOL_PROFILE_CORE)
    name = _normalize_profile(value)
    selected = frozenset(item.strip().lower() for item in toolsets or () if item.strip())
    unknown = selected - VALID_TOOLSETS
    if unknown:
        options = ", ".join(sorted(VALID_TOOLSETS))
        raise ToolProfileError(
            f"Unknown McuBuddy toolset(s): {', '.join(sorted(unknown))}. "
            f"Valid values are: {options}."
        )
    if name == TOOL_PROFILE_FULL and selected:
        raise ToolProfileError("The full profile already includes every toolset.")
    enabled = FULL_TOOL_NAMES if name == TOOL_PROFILE_FULL else CORE_TOOL_NAMES
    if selected:
        enabled |= frozenset(
            tool_name for tool_name, spec in TOOL_CATALOG.items() if spec.toolsets & selected
        )
    return ToolProfile(
        name=name,
        enabled_tool_names=enabled,
        selected_toolsets=selected,
    )
