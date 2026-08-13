---
name: mcubuddy
description: Use when debugging MCU firmware or boards with McuBuddy, including probe, boot, HardFault, peripheral, register, memory, ELF/SVD, RTOS, RTT/UART, Keil, GDB, pyOCD, J-Link, ST-Link, or CMSIS-DAP work.
---

# mcubuddy

## Core Principle

Prefer reads, separate evidence from hypotheses, and verify changes. Start in `core`.

## Local McuBuddy Discovery

With MCP tools available, never ask for the checkout. Otherwise use `McuBuddy home show --json`;
validate a missing checkout, then after confirmation run
`McuBuddy home set <checkout> --confirm --json`. Never embed local paths in docs.
Never write a local checkout path into `SKILL.md` or repository documentation.

## Codex MCP Recovery

If the user names McuBuddy but its MCP tools are absent, do not stop. Run
`McuBuddy setup status --json`, then if needed
`McuBuddy setup codex --repair --confirm --json`. Explain that registration persists but Codex must
reload. After reload, use MCP directly unless startup fails.

## Project Reference

Use `PROJECT_GUIDE.md` for architecture, `docs/tool-reference.md` for signatures, and
`docs/support-matrix.md` for verified support.

## Target Project Memory

Use the confirmed firmware root, never the Skill location; never write another firmware project's memory into the McuBuddy repository. Call
`inspect_project_memory(...)` before `get_runtime_config()`. Verify remembered hardware; write only
after confirming root and content.

## Known Project Resume

Reuse memory and config. Do not run `first_contact()` except for setup, changed hardware, missing
config, recovery, or requested preflight; use `doctor()` there too.

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

- Start with 19 defaults. Enable needed `probe`, `diagnose`, `build_flash`, `rtos`, `logs`, or
  `experimental` toolsets before startup.
- No aggregate profile; enable only required startup toolsets.
- Inspect hidden metadata with `list_tool_safety(include_hidden=true)`; never change profiles live.

## Symptom Routing

| Symptom | Start With |
| --- | --- |
| Board will not boot | Diagnose toolset: `collect_startup_evidence(...)`, then crash evidence if fault state is present |
| HardFault or crash | Diagnose and probe toolsets: `collect_crash_evidence(...)`, then `backtrace()` |
| UART/SPI/I2C/GPIO silent | Diagnose and probe toolsets: `svd_load(...)`, `collect_peripheral_evidence(...)`, `svd_read_peripheral(...)` |
| Interrupt/memory/stack issue | Matching crash, peripheral, stack, symbol, or RTOS evidence |
| FreeRTOS stall | RTOS toolset: `collect_rtos_evidence(...)`, then task context when a task is named |
| Clock issue | RCC/clock SVD evidence |
| Need path proof | Probe toolset: use `run_to_function(...)` or `source_step()` |
| Actuator command ACKed but no motion/output | Prove firmware, bus, peripheral, enable/direction, then physical output |

## Ordering and Safety

- Await stateful calls; use separate sessions for independent boards. Cancellation may not stop
  an in-progress probe SDK call.
- Confirm target, scope, firmware, intent, and recovery before writes or flash.
- For flash: collect evidence, build, flash, compare ELF to flash, reset/halt, and re-check.
- RTT memory scanning is bounded by `security.max_rtt_scan_size` or
  `MCUBUDDY_MAX_RTT_SCAN_SIZE`; do not bypass that guard.
- With the logs toolset, use low-energy `uart_send_with_cleanup(...)` calls with paired stop commands.
- A `partial` finish is unconfirmed safety evidence; report each failed cleanup.

## Reporting Template

Report evidence, interpretation, missing evidence, then the next safe check and impact.
