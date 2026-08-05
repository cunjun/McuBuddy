# McuBuddy v0.6.0

McuBuddy v0.6.0 strengthens the project as an evidence-first MCU debugging runtime. The release
narrows the default MCP surface, expands real-hardware backend coverage, and makes debugging
sessions safer to start, operate, and finish.

## Highlights

- Unified MCP tool registration around a generated catalog and explicit domain toolsets.
- Added project discovery and persistent project memory for repeat debugging sessions.
- Added probe-rs ESP32 Flash and RTT workflows alongside the existing pyOCD and J-Link backends.
- Added structured CLI, doctor, configuration, package-management, and evidence-collection flows.
- Improved session serialization and cleanup for probes, logs, GDB servers, and worker threads.
- Tightened capability reporting and diagnosis contracts so unsupported or incomplete hardware
  evidence is not presented as a successful result.
- Consolidated the English and Chinese documentation and the bundled Codex skill.

## Upgrade Notes

The default MCP surface is intentionally constrained. Enable only the additional domains needed
for a debugging workflow with `MCUBUDDY_TOOLSETS`. Existing installations should reinstall the
package and restart their MCP client after upgrading so the package metadata and tool catalog are
loaded from the same version.

## Validation

This release includes unit and integration coverage for tool registration, session lifecycle,
probe backends, Flash, RTT/UART logging, project memory, configuration, diagnostics, documentation,
and package metadata. Hardware capability claims remain scoped to the validation records and
support matrix shipped in the repository.
