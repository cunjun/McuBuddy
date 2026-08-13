# McuBuddy v0.6.1

McuBuddy v0.6.1 makes Codex integration persistent and self-repairing while tightening breakpoint
navigation semantics for real hardware debugging. Installed releases now carry the mcubuddy Skill,
so normal users can configure Codex without cloning the source repository.

## Highlights

- Added `McuBuddy setup codex/status/remove` for persistent Codex MCP registration, repair, and
  verification with `probe,diagnose` enabled by default.
- Bundled the mcubuddy Skill inside the wheel so `uv tool install McuBuddy` no longer requires a Git
  checkout for Codex setup.
- Made the Skill proactively repair missing MCP registration when the user explicitly requests
  McuBuddy.
- Fixed continue-after-breakpoint behavior by stepping over the active breakpoint while preserving
  its ownership and restoring it safely.
- Made run-to-function and run-to-source distinguish target hits, timeouts, errors, and unrelated
  stops instead of reporting every stop as success.
- Added tool-surface guidance to runtime and doctor reports.

## Upgrade Notes

Upgrade the installed package, run `McuBuddy setup codex --repair --confirm --json`, and restart
Codex so new tasks load the repaired MCP registration and bundled Skill.

## Validation

The complete unit and integration suite passes, the wheel contains the bundled Skill resources,
and documentation, Skill, Ruff, and repository-diff validation all pass. No additional real-board
validation is claimed for this release.
