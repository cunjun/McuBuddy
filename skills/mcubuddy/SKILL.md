---
name: mcubuddy
description: Use when an MCU task needs runtime evidence, including Keil online debugging, breakpoints, stepping, variables, probe, boot, HardFault, peripherals, ELF/SVD, RTOS, logs, GDB, pyOCD, J-Link, ST-Link, or CMSIS-DAP. Trigger proactively; the user need not name McuBuddy.
---

# mcubuddy

## Core Principle

Prefer reads, separate evidence from hypotheses, and verify changes. Start in `core`.

## Local McuBuddy Discovery

With MCP available, never ask for a checkout. Otherwise use `McuBuddy home show --json`; validate
before confirmed `McuBuddy home set` changes. Never embed local paths in Skill or repository docs.
Never write a local checkout path into `SKILL.md`.

## Codex MCP Recovery

If the task needs McuBuddy but its MCP tools are absent, do not stop. Run
`McuBuddy setup status --json`, then if needed
`McuBuddy setup codex --repair --confirm --json`. Explain that registration persists but Codex must
reload. After reload, use MCP directly unless startup fails.

## Proactive Runtime Debugging

Do not wait for the user to name McuBuddy. When source inspection cannot prove runtime behavior and
the AI needs Keil online debugging, a breakpoint, stepping, or variable values, select McuBuddy.
Use the matching Keil AXF/ELF and the probe toolset to:

- call `set_breakpoint(...)` with the probe toolset, resume, and verify the stop;
- call `read_symbol_value(...)` with the probe toolset for global and static variables;
- call `get_locals()` with the probe toolset for local variables and function parameters;
- single-step with the probe toolset and compare runtime values before and after.

Do not require access to Keil Watch windows. Keil may build the AXF, but it must release a probe
before McuBuddy connects to that same probe. Treat optimized-out or out-of-scope values as missing
DWARF/runtime evidence, not as absence of the debugging capability.

## Project Reference

Use `PROJECT_GUIDE.md` for architecture, `docs/tool-reference.md` for signatures, and
`docs/support-matrix.md` for verified support.

## Target Project Memory

Use firmware root; never write another firmware project's memory into the McuBuddy repository.
Call `inspect_project_memory(...)` before `get_runtime_config()`; search all descendant directories
for `.uvprojx` and `.uvproj`; select. Missing: call `write_project_memory(...)` to
`.mcubuddy/project-memory.md`;
reuse it on later debugging sessions.

## Known Project Resume

Reuse memory/config. Do not run `first_contact()` except for setup, hardware/config change, recovery,
or requested preflight; use `doctor()` there too.

## Default Flow

For a board problem without requested commands:

1. Read target-project memory, then runtime configuration.
2. Resolve only ambiguous targets with `match_chip_name(...)` or `get_target_info(...)`.
3. Configure only missing settings, then use `probe_connect(...)`.
4. With the probe toolset, establish a known state with `probe_halt()` or `probe_reset(halt=True)`.
5. Call `read_stopped_context()` and matching evidence collector.
6. Add ELF, SVD, logs, or RTOS context only when useful.
7. Test a hypothesis with the smallest safe check, then verify.
8. Call `finish_debug_session()` before concluding unless the user asks to preserve debug state.

## Profile Boundary

- Start with 19 defaults; enable only needed startup toolsets. Profiles cannot change live.
- Inspect hidden metadata with `list_tool_safety(include_hidden=true)`.

## Symptom Routing

- Boot/crash: diagnose and probe evidence, then stack and symbols.
- Silent peripheral: diagnose and probe SVD evidence.
- RTOS stall: RTOS task evidence; path proof: probe run-to or source stepping.
- No physical output: prove firmware, bus, peripheral, enable, then output.

## Ordering and Safety

- Await stateful calls; use separate sessions per board.
- Confirm target, scope, firmware, intent, and recovery before writes or flash.
- For flash: collect, build, flash, compare ELF/Flash, reset/halt, re-check.
- RTT memory scanning is bounded by `security.max_rtt_scan_size` or
  `MCUBUDDY_MAX_RTT_SCAN_SIZE`; do not bypass that guard.
- With logs, pair low-energy sends with cleanup. Report failed cleanup and `partial` finishes.

## Reporting Template

Report evidence, interpretation, missing evidence, then the next safe check and impact.
