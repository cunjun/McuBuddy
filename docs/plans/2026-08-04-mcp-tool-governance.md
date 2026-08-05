# MCP Tool Governance

## Decision

McuBuddy treats MCP tools as a versioned public contract, not as a mirror of every internal
capability. Internal domain behavior may continue to grow, while the MCP surface remains bounded,
explicit, and fail-closed.

The project uses one governed catalog to describe every exposed tool. Startup profiles are presets
derived from that catalog:

- `core` is the stable 19-tool default surface for orchestration and session setup.
- `full` is the explicit expert surface; it is not an automatic export of decorated callbacks.
- toolsets describe domain ownership and are selectable only at process startup.

## Invariants

1. A new `@mcp.tool()` callback is hidden until it has an explicit safety policy and catalog entry.
2. No profile may use an unbounded allowlist such as `enabled_tool_names=None`.
3. Catalog entries are immutable after startup.
4. Every public tool declares a safety level, stability, default visibility, and at least one
   toolset.
5. Read-only, execution-changing, state-changing, and persistent-destructive operations retain
   separate confirmation boundaries.
6. Internal helpers and backend-specific functions do not become public tools unless they represent
   a distinct user intent or safety boundary with a stable schema.

## Current Architecture

`src/McuBuddy/tool_safety.py` remains the explicit registration gate for tool policies.
`src/McuBuddy/tool_profiles.py` converts those policies into immutable `ToolSpec` entries and
derives the `core` and `full` allowlists. `SessionToolRegistrar` applies the selected allowlist
before FastMCP registers a callback.

Catalog metadata is returned by `list_tool_safety()` so clients and maintainers can inspect:

- safety level and confirmation requirement;
- serialized or concurrent execution mode;
- domain toolsets;
- `stable`, `preview`, or `experimental` stability;
- default visibility.

## Toolset Model

The catalog classifies tools into these official startup domains:

- `default`: 19 configuration, discovery, connection, and session lifecycle tools;
- `probe`: low-level target and probe operations;
- `diagnose`: diagnosis routers and structured evidence collection;
- `build_flash`: Keil, GDB server, build, Flash, and verification operations;
- `rtos`: RTOS inspection and context operations;
- `logs`: UART, RTT, SWO, and log lifecycle;
- `experimental`: preview workflows and compatibility operations.

`core` always contains `default` and may union explicit toolsets from `MCUBUDDY_TOOLSETS`. `full`
contains all governed tools for compatibility. Neither selection changes inside a live process.

## Delivery Phases

### Phase 1: fail-closed catalog — complete

- Introduce immutable `ToolSpec` and `TOOL_CATALOG`.
- Replace the unbounded `full` profile with an explicit allowlist.
- Reject manually constructed profiles without an allowlist.
- Expose governance metadata through `list_tool_safety()`.
- Add catalog, profile, and safety contract tests.

This phase deliberately preserves the current 45 `core` tools and 118 `full` tools.

### Phase 2: explicit domain ownership — complete

- Move toolset assignment from name-based classification to declarations beside each tool policy.
- Add catalog validation for owner, deprecation state, and schema version.
- Generate reference documentation from the catalog.
- Add startup selectors for supported toolset combinations without permitting live privilege
  escalation inside an existing MCP session.

Phase 2 reduces the default FastMCP schema from 45 to 19 tools while retaining all 118 governed
tools behind explicit domain selection or the `full` compatibility profile.

### Phase 3: bounded public surface

- Measure tool usage, model mis-selection, failed calls, and workflow length.
- Consolidate overlapping low-level tools only where user intent and safety boundaries remain clear.
- Keep compatibility aliases for renamed tools for at least one documented release cycle.
- Move rarely used or experimental operations out of the default surface.

### Phase 4: dynamic discovery evaluation

Evaluate dynamic toolset discovery only after clients used by McuBuddy reliably support tool-list
changes. Static startup selection remains the compatibility baseline.

## Promotion Checklist

A new public MCP tool must satisfy all of the following:

- represents an independently useful user intent;
- has a stable, typed input and output contract;
- cannot be expressed cleanly by an existing task or domain tool;
- has an explicit safety and confirmation policy;
- declares its toolset, stability, and default visibility;
- includes unit or integration coverage and reference documentation.

If any condition is missing, implement the capability in the domain layer and keep it internal.

## Verification

The Phase 1 and Phase 2 implementations are guarded by tests that verify:

- `core` and `full` resolve to explicit immutable sets;
- unknown future callbacks are denied by both profiles;
- every registered public tool has safety metadata;
- catalog and safety registries contain the same public tool names;
- `list_tool_safety()` reports governance metadata;
- FastMCP registers 19 tools for default `core` and 118 for `full`;
- every catalog entry belongs to exactly one of the seven official toolsets;
- generated reference documentation matches the runtime catalog.
