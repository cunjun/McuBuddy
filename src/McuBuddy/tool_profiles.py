from __future__ import annotations

import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .tool_safety import TOOL_POLICIES


PROFILE_ENV_VAR = "MCUBUDDY_TOOL_PROFILE"
TOOL_PROFILE_CORE = "core"
TOOL_PROFILE_FULL = "full"
VALID_TOOL_PROFILES = frozenset({TOOL_PROFILE_CORE, TOOL_PROFILE_FULL})
ToolProfileName = Literal["core", "full"]
ToolStability = Literal["stable", "preview", "experimental"]


CORE_TOOL_NAMES = frozenset(
    {
        "doctor",
        "first_contact",
        "get_runtime_config",
        "inspect_project_memory",
        "write_project_memory",
        "list_tool_safety",
        "list_validation_records",
        "pack_diagnose",
        "pack_install",
        "match_chip_name",
        "get_target_info",
        "list_connected_probes",
        "configure_probe",
        "configure_elf",
        "elf_load",
        "svd_load",
        "probe_connect",
        "disconnect_all",
        "finish_debug_session",
        "probe_halt",
        "probe_resume",
        "probe_reset",
        "read_stopped_context",
        "backtrace",
        "collect_crash_evidence",
        "collect_startup_evidence",
        "collect_peripheral_evidence",
        "collect_rtos_evidence",
        "svd_read_peripheral",
        "list_rtos_tasks",
        "rtos_task_context",
        "read_rtt_log",
        "configure_log",
        "log_connect",
        "uart_send",
        "uart_send_with_cleanup",
        "uart_read_bytes",
        "uart_exchange",
        "log_tail",
        "discover_keil_projects",
        "configure_keil_project",
        "build_project",
        "flash_firmware",
        "flash_image",
        "compare_elf_to_flash",
    }
)


def _toolsets_for(tool_name: str, *, default_enabled: bool) -> frozenset[str]:
    toolsets = {"core" if default_enabled else "expert"}
    if "rtos" in tool_name:
        toolsets.add("rtos")
    elif tool_name.startswith(("diagnose", "collect_")):
        toolsets.add("diagnostics")
    elif any(token in tool_name for token in ("build", "flash", "gdb", "keil")):
        toolsets.add("build_flash")
    elif any(token in tool_name for token in ("log", "uart", "rtt", "swo")):
        toolsets.add("logs")
    elif tool_name.startswith("svd_"):
        toolsets.add("peripherals")
    elif tool_name.startswith("probe_"):
        toolsets.add("probe")
    else:
        toolsets.add("runtime")
    return frozenset(toolsets)


@dataclass(frozen=True)
class ToolSpec:
    """Governance metadata for one explicitly exposed MCP tool."""

    name: str
    safety_level: str
    toolsets: frozenset[str]
    stability: ToolStability
    default_enabled: bool = False


TOOL_CATALOG = MappingProxyType(
    {
        name: ToolSpec(
            name=name,
            safety_level=policy["level"],
            toolsets=_toolsets_for(name, default_enabled=name in CORE_TOOL_NAMES),
            stability="stable" if name in CORE_TOOL_NAMES else "preview",
            default_enabled=name in CORE_TOOL_NAMES,
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
) -> ToolProfile:
    value = explicit
    if value is None:
        env = os.environ if environ is None else environ
        value = env.get(PROFILE_ENV_VAR, TOOL_PROFILE_CORE)
    name = _normalize_profile(value)
    enabled = FULL_TOOL_NAMES if name == TOOL_PROFILE_FULL else CORE_TOOL_NAMES
    return ToolProfile(name=name, enabled_tool_names=enabled)
