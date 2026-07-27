---
name: mcubug
description: Use when debugging MCU firmware or boards with McuBuddy, including probe connection, boot or HardFault crashes, silent peripherals, register/memory/ELF/SVD inspection, RTOS or RTT/UART evidence, Keil build/flash, GDB, and board bring-up through pyOCD, J-Link, ST-Link, or CMSIS-DAP.
---

# mcubug

## Core Principle

Collect reproducible hardware evidence. Prefer reads, separate facts from hypotheses, and repeat
checks after changes. Start in `core`; use `full` only when evidence requires it.

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

If tools are unavailable, state that integration is missing and give the required setup or sequence.

## Known Project Resume

Start with `get_runtime_config()`. Reuse configured target, backend, probe, ELF, build, and logs.
Do not run `first_contact()` when configuration supplies what the task needs.

Use `doctor()` and `first_contact()` only for first setup, changed hardware, missing configuration,
connection recovery, or an explicit preflight. A new Codex task alone is not first contact.

## Default Flow

For a board problem without requested commands:

1. Read configuration; choose resume or first contact.
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
- Classify calls as read-only, execution-changing, state-changing, or persistent. Confirm target,
  scope, firmware, intent, and recovery before writes or flash operations.
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
