# Session Architecture Hard-Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `SessionState` service locator with explicit service, artifact, and lifecycle groups while making debug-session cleanup safe, retryable, and impossible to bypass through raw MCP registration.

**Architecture:** `SessionState` retains only configuration, grouped state, and the execution lock. All callers move in one change to `services`, `artifacts`, and `lifecycle`; cleanup records successful stages rather than caching a failed whole-session result; MCP registration groups require a nominal `SessionToolRegistrar` instance.

**Tech Stack:** Python 3.11+, dataclasses, asyncio, FastMCP, pytest, ruff, CodeGraph.

---

### Task 1: Define the hard-cut session contract

**Files:**
- Modify: `src/McuBuddy/session.py`
- Test: `tests/unit/test_session.py`

- [ ] Write tests constructing `SessionServices`, `DebugArtifacts`, `SessionLifecycle`, and `SessionState` through the new nested API; assert the removed flat fields raise `AttributeError`.
- [ ] Run `pytest tests/unit/test_session.py -q` and confirm the new imports or fields fail before production changes.
- [ ] Add the three focused dataclasses and update `create_default_session()` to replace `session.services.probe`.
- [ ] Run the focused test and confirm it passes.

### Task 2: Make lifecycle cleanup dependency-aware and retryable

**Files:**
- Modify: `src/McuBuddy/tools/lifecycle.py`
- Test: `tests/unit/test_lifecycle_tools.py`

- [ ] Add failing tests proving failed UART payloads remain queued, reset failure prevents resume, successful steps are not repeated, and failed steps retry on the next call.
- [ ] Run the focused lifecycle tests and confirm each new assertion fails for the old behavior.
- [ ] Implement ordered cleanup stages backed by `session.lifecycle.completed_cleanup_steps`; retain failed payloads and cache only the latest report, not a terminal partial result.
- [ ] Run the focused lifecycle tests and confirm they pass.

### Task 3: Enforce the MCP registration boundary

**Files:**
- Modify: `src/McuBuddy/mcp_execution.py`
- Modify: `src/McuBuddy/mcp_tools/**/*.py`
- Test: `tests/unit/test_mcp_execution.py`
- Test: `tests/integration/test_tool_profiles.py`

- [ ] Add failing tests that raw FastMCP-like registrars are rejected and that registered callbacks still enforce confirmation and serialization.
- [ ] Run the focused tests and confirm rejection/contract assertions fail before implementation.
- [ ] Add `require_session_tool_registrar()`, type all registration functions as `SessionToolRegistrar`, rename their parameter to `registrar`, and validate every public registration-group entry.
- [ ] Run the focused tests and confirm they pass.

### Task 4: Migrate every session-field caller in one pass

**Files:**
- Modify: `src/McuBuddy/**/*.py`
- Modify: `tests/**/*.py`

- [ ] Replace service accesses with `session.services.*`, artifact accesses with `session.artifacts.*`, and lifecycle accesses with `session.lifecycle.*` in production and test doubles.
- [ ] Use CodeGraph to confirm no old `SessionState` field access remains.
- [ ] Run the complete test suite and repair only migration regressions.

### Task 5: Verify architecture and quality

**Files:**
- Modify only files required by verification failures attributable to this change.

- [ ] Run `pytest -q` and require zero failures.
- [ ] Run `ruff check .` and require zero errors.
- [ ] Run `git diff --check` and require zero whitespace errors.
- [ ] Re-query CodeGraph for `SessionState`, `SessionToolRegistrar`, and `finish_debug_session`; confirm the intended dependency boundaries and review the final diff.

No commit is created by this plan.
