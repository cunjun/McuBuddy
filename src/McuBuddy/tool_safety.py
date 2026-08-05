from __future__ import annotations

from typing import Any


DEFAULT_TOOL_NAMES = frozenset(
    {
        "doctor",
        "first_contact",
        "get_runtime_config",
        "inspect_project_memory",
        "write_project_memory",
        "list_tool_safety",
        "list_validation_records",
        "pack_diagnose",
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
        "read_stopped_context",
    }
)


TOOLSET_MEMBERS = {
    "build_flash": frozenset(
        {
            "build_project",
            "compare_elf_to_flash",
            "configure_build",
            "configure_keil_project",
            "discover_keil_projects",
            "erase_flash",
            "flash_firmware",
            "flash_image",
            "get_gdb_server_status",
            "get_jlink_gdb_server_status",
            "program_flash",
            "start_gdb_server",
            "start_jlink_gdb_server",
            "stop_gdb_server",
            "stop_jlink_gdb_server",
            "verify_flash",
        }
    ),
    "default": DEFAULT_TOOL_NAMES,
    "diagnose": frozenset(
        {
            "collect_crash_evidence",
            "collect_peripheral_evidence",
            "collect_startup_evidence",
            "diagnose",
            "diagnose_clock_issue",
            "diagnose_hardfault",
            "diagnose_interrupt_issue",
            "diagnose_memory_corruption",
            "diagnose_peripheral_stuck",
            "diagnose_stack_overflow",
            "diagnose_startup_failure",
        }
    ),
    "logs": frozenset(
        {
            "configure_log",
            "log_connect",
            "log_disconnect",
            "log_tail",
            "log_trace",
            "read_rtt_log",
            "read_swo_log",
            "uart_exchange",
            "uart_read_bytes",
            "uart_send",
            "uart_send_with_cleanup",
        }
    ),
    "probe": frozenset(
        {
            "backtrace",
            "clear_all_breakpoints",
            "clear_breakpoint",
            "connect_with_config",
            "continue_target",
            "disassemble",
            "dump_memory",
            "dwarf_backtrace",
            "elf_addr_to_source",
            "elf_list_functions",
            "elf_symbol_info",
            "get_locals",
            "list_conditional_breakpoints",
            "memory_diff",
            "memory_find",
            "memory_snapshot",
            "probe_clear_all_watchpoints",
            "probe_continue_until",
            "probe_disconnect",
            "probe_halt",
            "probe_read_fpu_registers",
            "probe_read_memory",
            "probe_read_mpu_regions",
            "probe_read_registers",
            "probe_remove_watchpoint",
            "probe_reset",
            "probe_resume",
            "probe_set_watchpoint",
            "probe_step",
            "probe_write_memory",
            "read_cycle_counter",
            "read_memory_map",
            "read_stack_usage",
            "read_symbol_value",
            "reset_and_trace",
            "run_to_function",
            "run_to_source",
            "set_breakpoint",
            "set_breakpoints_for_function_range",
            "set_local",
            "source_step",
            "step_n_instructions",
            "step_out",
            "step_over",
            "svd_get_registers",
            "svd_list_peripherals",
            "svd_read_peripheral",
            "svd_write_field",
            "svd_write_register",
            "watch_symbol",
            "write_symbol_value",
        }
    ),
    "rtos": frozenset(
        {"collect_rtos_evidence", "list_rtos_tasks", "rtos_switch_context", "rtos_task_context"}
    ),
    "experimental": frozenset(
        {
            "board_smoke_test",
            "list_demo_profiles",
            "list_supported_targets",
            "load_demo_profile",
            "pack_install",
            "run_debug_loop",
        }
    ),
}


CONCURRENT_TOOLS = frozenset(
    {
        "discover_keil_projects",
        "get_target_info",
        "inspect_project_memory",
        "list_demo_profiles",
        "list_supported_targets",
        "list_tool_safety",
        "list_validation_records",
        "match_chip_name",
        "pack_diagnose",
    }
)


SAFETY_LEVELS: dict[str, dict[str, Any]] = {
    "read-only": {
        "summary": "Reads configuration, debug state, symbols, logs, or metadata.",
        "requires_confirmation": False,
    },
    "execution-changing": {
        "summary": "Changes target execution state, such as halt, resume, reset, or continue.",
        "requires_confirmation": False,
    },
    "state-changing": {
        "summary": "Writes target runtime state, such as memory, registers, breakpoints, or watchpoints.",
        "requires_confirmation": True,
    },
    "persistent-destructive": {
        "summary": "Changes persistent target state, especially flash erase/program or firmware flashing.",
        "requires_confirmation": True,
    },
    "persistent": {
        "summary": "Creates or updates a persistent host-side project artifact.",
        "requires_confirmation": True,
    },
    "host-process": {
        "summary": "Starts, stops, or inspects host-side helper processes.",
        "requires_confirmation": False,
    },
    "session-changing": {
        "summary": "Changes McuBuddy session configuration or loaded debug metadata.",
        "requires_confirmation": False,
    },
    "connection-changing": {
        "summary": "Opens or closes probe, log, or other debug connections.",
        "requires_confirmation": False,
    },
}


TOOL_POLICIES: dict[str, dict[str, Any]] = {
    "doctor": {"level": "read-only"},
    "first_contact": {"level": "execution-changing"},
    "board_smoke_test": {"level": "execution-changing"},
    "get_runtime_config": {"level": "read-only"},
    "inspect_project_memory": {"level": "read-only"},
    "write_project_memory": {"level": "persistent"},
    "list_connected_probes": {"level": "read-only"},
    "list_supported_targets": {"level": "read-only"},
    "match_chip_name": {"level": "read-only"},
    "get_target_info": {"level": "read-only"},
    "list_conditional_breakpoints": {"level": "read-only"},
    "list_demo_profiles": {"level": "read-only"},
    "list_tool_safety": {"level": "read-only"},
    "list_validation_records": {"level": "read-only"},
    "pack_diagnose": {"level": "read-only"},
    "pack_install": {"level": "persistent-destructive"},
    "collect_crash_evidence": {"level": "execution-changing"},
    "collect_startup_evidence": {"level": "execution-changing"},
    "collect_peripheral_evidence": {"level": "read-only"},
    "collect_rtos_evidence": {"level": "read-only"},
    "discover_keil_projects": {"level": "read-only"},
    "elf_addr_to_source": {"level": "read-only"},
    "elf_list_functions": {"level": "read-only"},
    "elf_symbol_info": {"level": "read-only"},
    "read_symbol_value": {"level": "read-only"},
    "watch_symbol": {"level": "read-only"},
    "disassemble": {"level": "read-only"},
    "get_locals": {"level": "read-only"},
    "backtrace": {"level": "read-only"},
    "dwarf_backtrace": {"level": "read-only"},
    "read_memory_map": {"level": "read-only"},
    "compare_elf_to_flash": {"level": "read-only"},
    "verify_flash": {"level": "read-only"},
    "memory_find": {"level": "read-only"},
    "memory_snapshot": {"level": "read-only"},
    "memory_diff": {"level": "read-only"},
    "probe_read_fpu_registers": {"level": "read-only"},
    "read_stack_usage": {"level": "read-only"},
    "list_rtos_tasks": {"level": "read-only"},
    "rtos_task_context": {"level": "read-only"},
    "svd_list_peripherals": {"level": "read-only"},
    "svd_get_registers": {"level": "read-only"},
    "read_stopped_context": {"level": "read-only"},
    "probe_read_registers": {"level": "read-only"},
    "probe_read_memory": {"level": "read-only"},
    "dump_memory": {"level": "read-only"},
    "read_rtt_log": {"level": "read-only"},
    "log_tail": {"level": "read-only"},
    "uart_send": {"level": "state-changing"},
    "uart_send_with_cleanup": {"level": "state-changing"},
    "uart_read_bytes": {"level": "read-only"},
    "uart_exchange": {"level": "state-changing"},
    "svd_read_peripheral": {"level": "read-only"},
    "diagnose": {"level": "execution-changing"},
    "diagnose_hardfault": {"level": "execution-changing"},
    "diagnose_startup_failure": {"level": "execution-changing"},
    "diagnose_peripheral_stuck": {"level": "read-only"},
    "diagnose_memory_corruption": {"level": "read-only"},
    "diagnose_interrupt_issue": {"level": "read-only"},
    "diagnose_clock_issue": {"level": "read-only"},
    "diagnose_stack_overflow": {"level": "read-only"},
    "probe_halt": {"level": "execution-changing"},
    "probe_resume": {"level": "execution-changing"},
    "probe_reset": {"level": "execution-changing"},
    "continue_target": {"level": "execution-changing"},
    "probe_step": {"level": "execution-changing"},
    "source_step": {"level": "execution-changing"},
    "step_over": {"level": "execution-changing"},
    "step_out": {"level": "execution-changing"},
    "run_to_function": {"level": "execution-changing"},
    "run_to_source": {"level": "execution-changing"},
    "probe_continue_until": {"level": "execution-changing"},
    "step_n_instructions": {"level": "execution-changing"},
    "log_trace": {"level": "execution-changing"},
    "reset_and_trace": {"level": "execution-changing"},
    "run_debug_loop": {"level": "execution-changing"},
    "set_breakpoint": {"level": "state-changing"},
    "clear_breakpoint": {"level": "state-changing"},
    "clear_all_breakpoints": {"level": "state-changing"},
    "probe_set_watchpoint": {"level": "state-changing"},
    "probe_remove_watchpoint": {"level": "state-changing"},
    "probe_clear_all_watchpoints": {"level": "state-changing"},
    "probe_read_mpu_regions": {"level": "state-changing"},
    "probe_write_memory": {"level": "state-changing"},
    "write_symbol_value": {"level": "state-changing"},
    "set_local": {"level": "state-changing"},
    "svd_write_register": {"level": "state-changing"},
    "svd_write_field": {"level": "state-changing"},
    "set_breakpoints_for_function_range": {"level": "state-changing"},
    "rtos_switch_context": {"level": "state-changing"},
    "read_cycle_counter": {"level": "state-changing"},
    "read_swo_log": {"level": "state-changing"},
    "erase_flash": {"level": "persistent-destructive"},
    "program_flash": {"level": "persistent-destructive"},
    "flash_image": {"level": "persistent-destructive"},
    "flash_firmware": {"level": "persistent-destructive"},
    "build_project": {"level": "host-process"},
    "start_gdb_server": {"level": "host-process"},
    "stop_gdb_server": {"level": "host-process"},
    "get_gdb_server_status": {"level": "host-process"},
    "start_jlink_gdb_server": {"level": "host-process"},
    "stop_jlink_gdb_server": {"level": "host-process"},
    "get_jlink_gdb_server_status": {"level": "host-process"},
    "configure_build": {"level": "session-changing"},
    "configure_elf": {"level": "session-changing"},
    "configure_keil_project": {"level": "session-changing"},
    "configure_log": {"level": "session-changing"},
    "configure_probe": {"level": "session-changing"},
    "load_demo_profile": {"level": "session-changing"},
    "elf_load": {"level": "session-changing"},
    "svd_load": {"level": "session-changing"},
    "connect_with_config": {"level": "connection-changing"},
    "disconnect_all": {"level": "connection-changing"},
    "finish_debug_session": {"level": "execution-changing"},
    "log_connect": {"level": "connection-changing"},
    "log_disconnect": {"level": "connection-changing"},
    "probe_connect": {"level": "connection-changing"},
    "probe_disconnect": {"level": "connection-changing"},
}

for _tool_name, _policy in TOOL_POLICIES.items():
    _policy["execution"] = "concurrent" if _tool_name in CONCURRENT_TOOLS else "serialized"

_toolset_by_name = {
    tool_name: toolset
    for toolset, tool_names in TOOLSET_MEMBERS.items()
    for tool_name in tool_names
}
if set(_toolset_by_name) != set(TOOL_POLICIES):
    missing = sorted(set(TOOL_POLICIES) - set(_toolset_by_name))
    unknown = sorted(set(_toolset_by_name) - set(TOOL_POLICIES))
    raise RuntimeError(f"Invalid toolset declarations; missing={missing}, unknown={unknown}.")

for _tool_name, _policy in TOOL_POLICIES.items():
    _toolset = _toolset_by_name[_tool_name]
    _policy.update(
        {
            "toolsets": frozenset({_toolset}),
            "owner": f"mcubuddy.{_toolset}",
            "stability": "stable" if _tool_name in DEFAULT_TOOL_NAMES else "preview",
            "schema_version": 1,
            "deprecated": False,
            "default_enabled": _tool_name in DEFAULT_TOOL_NAMES,
        }
    )

# Backward-compatible name for callers that only consume safety metadata.
TOOL_SAFETY = TOOL_POLICIES


def get_tool_safety(tool_name: str) -> dict[str, Any]:
    entry = dict(TOOL_POLICIES.get(tool_name, {"level": "unknown", "execution": "serialized"}))
    level_info = SAFETY_LEVELS.get(
        entry["level"],
        {"summary": "No safety metadata is registered.", "requires_confirmation": True},
    )
    entry.update(level_info)
    # Import lazily because tool_profiles builds its catalog from TOOL_POLICIES.
    from .tool_profiles import TOOL_CATALOG

    if spec := TOOL_CATALOG.get(tool_name):
        entry.update(
            {
                "toolsets": sorted(spec.toolsets),
                "stability": spec.stability,
                "default_enabled": spec.default_enabled,
            }
        )
    return entry


def require_tool_confirmation(tool_name: str, confirmed: bool) -> dict[str, Any] | None:
    safety = get_tool_safety(tool_name)
    if confirmed or not safety["requires_confirmation"]:
        return None
    summary = f"{tool_name} is a {safety['level']} operation and requires explicit confirmation."
    return {
        "status": "error",
        "summary": summary,
        "safety": safety,
        "next_tools": ["list_tool_safety"],
    }


def list_tool_safety(
    *,
    active_profile: str = "core",
    selected_toolsets: frozenset[str] | set[str] | None = None,
    enabled_tool_names: frozenset[str] | set[str] | None = None,
    include_hidden: bool = False,
) -> dict[str, Any]:
    tool_names = (
        set(TOOL_POLICIES)
        if include_hidden or enabled_tool_names is None
        else set(enabled_tool_names)
    )
    return {
        "status": "ok",
        "summary": f"Listed safety metadata for {len(tool_names)} tool(s).",
        "active_profile": active_profile,
        "selected_toolsets": sorted(selected_toolsets or ()),
        "hidden_tools_included": include_hidden,
        "safety_levels": SAFETY_LEVELS,
        "tools": {name: get_tool_safety(name) for name in sorted(tool_names)},
    }
