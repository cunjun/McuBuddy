---
name: mcubuddy
description: Use when debugging MCU firmware or boards with McuBuddy, including probe, boot, HardFault, peripheral, register, memory, ELF/SVD, RTOS, RTT/UART, Keil, GDB, pyOCD, J-Link, ST-Link, or CMSIS-DAP work.
---

# mcubuddy

## Core Principle

Prefer reads, separate evidence from hypotheses, and verify changes. Start in `core`.

## Local McuBuddy Discovery

With MCP tools available, never ask for the checkout. Otherwise run `McuBuddy home show --json`.
If unavailable, ask once, validate `pyproject.toml` plus `src/McuBuddy`, and find `.venv`. After
confirmation run `McuBuddy home set <checkout> --confirm --json` with that executable. Store paths
only in user-level `.mcubuddy/installations.json`.
Never write a local checkout path into `SKILL.md` or repository documentation.

## Project Reference

This Skill is deliberately self-contained and does not duplicate the repository documentation.
When the source checkout is available, use its `PROJECT_GUIDE.md` for the project overview,
`docs/tool-reference.md` for exact signatures, and `docs/support-matrix.md` for verified support.

## Target Project Memory

Use the confirmed firmware root, never the Skill location;
never write another firmware project's memory into the McuBuddy repository.
Call `inspect_project_memory(...)` before `get_runtime_config()`. Verify remembered hardware.
Write only after confirming root and content.

## Known Project Resume

Reuse memory and config. Do not run `first_contact()` except for first setup, changed hardware,
missing config, recovery, or requested preflight; use `doctor()` there too. A new Codex task alone
is not first contact.

## Default Flow

For a board problem without requested commands:

1. Read target-project memory, then runtime configuration.
2. Resolve only ambiguous targets with `match_chip_name(...)` or `get_target_info(...)`.
3. Configure only missing settings, then use `probe_connect(...)`.
4. Establish a known state with `probe_halt()` or `probe_reset(halt=True)`.
5. Call `read_stopped_context()` and matching evidence collector.
6. Add ELF, SVD, logs, or RTOS context only when useful.
7. Test a hypothesis with the smallest safe check, then verify.

## Profile Boundary

- Stay in `core`. Full-only calls require `MCUBUDDY_TOOL_PROFILE=full` before startup and restart.
- Inspect hidden metadata with `list_tool_safety(include_hidden=true)`; never change profiles live.

## Symptom Routing

| Symptom | Start With |
| --- | --- |
| Board will not boot | `collect_startup_evidence(...)`, then crash evidence if fault state is present |
| HardFault or crash | `collect_crash_evidence(...)`, then `backtrace()` |
| UART/SPI/I2C/GPIO silent | `svd_load(...)`, `collect_peripheral_evidence(...)`, `svd_read_peripheral(...)` |
| Interrupt issue | Crash/peripheral evidence, NVIC state, handler symbols |
| Memory corruption | Crash evidence, repeatable snapshots, stack and symbol checks |
| Stack overflow | Crash/RTOS evidence and stack context |
| FreeRTOS stall | `collect_rtos_evidence(...)`, then task context when a task is named |
| Clock issue | RCC/clock SVD evidence |
| Need path proof | Full-only: restart in `full`, then use `run_to_function(...)` or `source_step()` |
| Actuator command ACKed but no motion/output | Prove firmware, bus, peripheral, enable/direction, then physical output |

## Ordering and Safety

- Await stateful calls; use separate sessions for independent boards. Cancellation may not stop
  an in-progress probe SDK call.
- Confirm target, scope, firmware, intent, and recovery before writes or flash.
- For flash: collect evidence, build, flash, compare ELF to flash, reset/halt, and re-check.
- RTT memory scanning is bounded by `security.max_rtt_scan_size` or
  `MCUBUDDY_MAX_RTT_SCAN_SIZE`; do not bypass that guard.
- For actuators, use short low-energy commands; prove firmware, bus, peripheral, and output.

## Reporting Template

Report results in this order:

```text
Evidence:
- ...

Interpretation:
- ...

Missing/uncertain evidence:
- ...

Next safe check and impact:
- ...
```
