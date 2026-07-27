---
name: mcubuddy
description: Use when debugging MCU firmware or boards with McuBuddy, including probe, boot, HardFault, peripheral, register, memory, ELF/SVD, RTOS, RTT/UART, Keil, GDB, pyOCD, J-Link, ST-Link, or CMSIS-DAP work.
---

# mcubuddy

## Core Principle

Collect reproducible evidence. Prefer reads, separate facts from hypotheses, and verify changes.
Start in `core`; use `full` only when required.

## Reference Selection

Load only the reference needed for the current task:

| Situation | Read |
| --- | --- |
| First setup | `references/quickstart.md` |
| Windows MCP config | `references/windows-mcp-config-example.md` |
| Unknown target or board | `references/generic-board-workflow.md` |
| Tool names | `references/tool-reference.md` |
| Capabilities and limits | `references/support-matrix.md` |
| AI debug session | `references/ai-playbook.md` |
| Symptom examples | `references/ai-examples.md` |
| ACK without actuator output | `references/peripheral-actuator-debug-playbook.md` |
| Board validation | `references/board-validation-guide.md` |

## Target Project Memory

Use the user's firmware root or one unambiguous Keil project. Never use the Skill location as the
target, and never write another firmware project's memory into the McuBuddy repository.

Call `inspect_project_memory(...)` before `get_runtime_config()`. Reuse confirmed facts and verify
last-known hardware. If missing, explain the proposal; call `write_project_memory(...)` only after
the user confirms root and content. Ambiguity means no write.

## Known Project Resume

Reuse project memory and runtime configuration. Do not run `first_contact()` when they supply what
the task needs. Use `doctor()` and `first_contact()` only for first setup, changed hardware, missing
configuration, connection recovery, or an explicit preflight. A new Codex task alone is not first
contact.

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

- Keep the default path inside `core`.
- A full-only call requires `MCUBUDDY_TOOL_PROFILE=full` before startup and a restart; a running
  core session cannot expose it.
- Use `list_tool_safety(include_hidden=true)` to inspect hidden metadata without changing profiles.

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
| Actuator command ACKed but no motion/output | Use the actuator playbook evidence ladder |

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
