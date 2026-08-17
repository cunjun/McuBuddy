from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .installation_registry import inspect_runtime_installation
from .skill_installer import install_skill

CommandResult = dict[str, Any]
CommandRunner = Callable[[list[str]], CommandResult]
DEFAULT_CODEX_TOOLSETS = ("probe", "diagnose")


def inspect_codex_integration(
    *,
    repo_root: str | Path | None = None,
    runner: CommandRunner | None = None,
    codex_command: str | None = None,
) -> dict[str, Any]:
    root = _resolve_repo_root(repo_root)
    executable = _resolve_mcubuddy_executable(root)
    skill_source, skill_source_kind = _resolve_skill_source(root)
    codex = codex_command or shutil.which("codex") or shutil.which("codex.cmd")
    if codex is None:
        return {
            "status": "warning",
            "summary": "Codex CLI was not found; McuBuddy MCP registration could not be checked.",
            "registered": False,
            "repo_root": str(root) if root is not None else None,
            "executable": str(executable) if executable is not None else None,
            "skill_source": str(skill_source) if skill_source is not None else None,
            "skill_source_kind": skill_source_kind,
        }

    result = (runner or _run_command)([codex, "mcp", "get", "mcubuddy"])
    registered = result["returncode"] == 0
    return {
        "status": "ok" if registered else "not_configured",
        "summary": (
            "McuBuddy MCP is registered with Codex."
            if registered
            else "McuBuddy MCP is not registered with Codex."
        ),
        "registered": registered,
        "repo_root": str(root) if root is not None else None,
        "executable": str(executable) if executable is not None else None,
        "skill_source": str(skill_source) if skill_source is not None else None,
        "skill_source_kind": skill_source_kind,
        "codex_command": codex,
        "details": result["stdout"] or result["stderr"],
    }


def setup_codex(
    *,
    repo_root: str | Path | None = None,
    home: str | Path | None = None,
    toolsets: Sequence[str] = DEFAULT_CODEX_TOOLSETS,
    confirm: bool = False,
    repair: bool = False,
    runner: CommandRunner | None = None,
    codex_command: str | None = None,
) -> dict[str, Any]:
    command_runner = runner or _run_command
    current = inspect_codex_integration(
        repo_root=repo_root,
        runner=command_runner,
        codex_command=codex_command,
    )
    if current["status"] == "warning":
        return current
    if not confirm:
        return {
            **current,
            "status": "needs_confirmation",
            "summary": "Confirm installing the McuBuddy Codex skill and persistent MCP registration.",
        }

    root = Path(current["repo_root"]) if current.get("repo_root") else None
    executable = Path(current["executable"]) if current.get("executable") else None
    skill_source = Path(current["skill_source"]) if current.get("skill_source") else None
    if executable is None or not executable.is_file() or skill_source is None:
        return {
            "status": "error",
            "summary": "A usable McuBuddy executable and bundled Skill are required for Codex setup.",
            "integration": current,
        }

    normalized_toolsets = _normalize_toolsets(toolsets)
    codex = current["codex_command"]
    actions: list[dict[str, Any]] = []
    if current["registered"] and repair:
        removal = command_runner([codex, "mcp", "remove", "mcubuddy"])
        actions.append({"action": "remove-mcp", **removal})
        if removal["returncode"] != 0:
            return _setup_error("Could not remove the existing McuBuddy MCP registration.", actions)

    if not current["registered"] or repair:
        addition = command_runner(
            [
                codex,
                "mcp",
                "add",
                "mcubuddy",
                "--env",
                f"MCUBUDDY_TOOLSETS={','.join(normalized_toolsets)}",
                "--",
                str(executable),
                "serve",
            ]
        )
        actions.append({"action": "add-mcp", **addition})
        if addition["returncode"] != 0:
            return _setup_error("Could not register the McuBuddy MCP server.", actions)

    skill = install_skill(
        target="codex",
        home=home,
        source=skill_source,
        force=True,
    )
    skill_action = {key: value for key, value in skill.items() if key != "next_steps"}
    actions.append({"action": "install-skill", **skill_action})
    if skill["status"] != "ok":
        return _setup_error("MCP registration succeeded, but Skill installation failed.", actions)

    verified = inspect_codex_integration(
        repo_root=root,
        runner=command_runner,
        codex_command=codex,
    )
    if not verified["registered"]:
        return _setup_error("Codex did not report the McuBuddy MCP registration after setup.", actions)
    return {
        "status": "ok",
        "summary": "Configured persistent McuBuddy integration for Codex.",
        "registered": True,
        "repo_root": str(root) if root is not None else None,
        "executable": str(executable),
        "skill_source": str(skill_source),
        "skill_source_kind": current["skill_source_kind"],
        "toolsets": normalized_toolsets,
        "actions": actions,
        "restart_required": True,
        "next_steps": [
            "Restart Codex so new tasks load the McuBuddy MCP tool surface.",
            "After restart, requests that name McuBuddy should use its MCP tools directly.",
        ],
    }


def remove_codex(
    *,
    confirm: bool = False,
    runner: CommandRunner | None = None,
    codex_command: str | None = None,
) -> dict[str, Any]:
    command_runner = runner or _run_command
    current = inspect_codex_integration(runner=command_runner, codex_command=codex_command)
    if not current.get("registered"):
        return {**current, "status": "ok", "summary": "McuBuddy MCP was not registered."}
    if not confirm:
        return {
            **current,
            "status": "needs_confirmation",
            "summary": "Confirm removing the persistent McuBuddy MCP registration from Codex.",
        }
    result = command_runner([current["codex_command"], "mcp", "remove", "mcubuddy"])
    return {
        "status": "ok" if result["returncode"] == 0 else "error",
        "summary": (
            "Removed the McuBuddy MCP registration from Codex."
            if result["returncode"] == 0
            else "Could not remove the McuBuddy MCP registration from Codex."
        ),
        "result": result,
        "restart_required": result["returncode"] == 0,
    }


def inspect_claude_integration(
    *,
    repo_root: str | Path | None = None,
    runner: CommandRunner | None = None,
    claude_command: str | None = None,
) -> dict[str, Any]:
    root = _resolve_repo_root(repo_root)
    executable = _resolve_mcubuddy_executable(root)
    skill_source, skill_source_kind = _resolve_skill_source(root)
    claude = claude_command or shutil.which("claude") or shutil.which("claude.cmd")
    if claude is None:
        return {
            "status": "warning",
            "summary": "Claude Code CLI was not found; McuBuddy MCP registration could not be checked.",
            "registered": False,
            "repo_root": str(root) if root is not None else None,
            "executable": str(executable) if executable is not None else None,
            "skill_source": str(skill_source) if skill_source is not None else None,
            "skill_source_kind": skill_source_kind,
        }

    result = (runner or _run_command)([claude, "mcp", "get", "mcubuddy"])
    registered = result["returncode"] == 0
    return {
        "status": "ok" if registered else "not_configured",
        "summary": (
            "McuBuddy MCP is registered with Claude Code."
            if registered
            else "McuBuddy MCP is not registered with Claude Code."
        ),
        "registered": registered,
        "repo_root": str(root) if root is not None else None,
        "executable": str(executable) if executable is not None else None,
        "skill_source": str(skill_source) if skill_source is not None else None,
        "skill_source_kind": skill_source_kind,
        "claude_command": claude,
        "details": result["stdout"] or result["stderr"],
    }


def setup_claude(
    *,
    repo_root: str | Path | None = None,
    home: str | Path | None = None,
    toolsets: Sequence[str] = DEFAULT_CODEX_TOOLSETS,
    confirm: bool = False,
    repair: bool = False,
    runner: CommandRunner | None = None,
    claude_command: str | None = None,
) -> dict[str, Any]:
    command_runner = runner or _run_command
    current = inspect_claude_integration(
        repo_root=repo_root,
        runner=command_runner,
        claude_command=claude_command,
    )
    if current["status"] == "warning":
        return current
    if not confirm:
        return {
            **current,
            "status": "needs_confirmation",
            "summary": "Confirm installing the McuBuddy Claude Code skill and user MCP registration.",
        }

    root = Path(current["repo_root"]) if current.get("repo_root") else None
    executable = Path(current["executable"]) if current.get("executable") else None
    skill_source = Path(current["skill_source"]) if current.get("skill_source") else None
    if executable is None or not executable.is_file() or skill_source is None:
        return {
            "status": "error",
            "summary": "A usable McuBuddy executable and bundled Skill are required for Claude Code setup.",
            "integration": current,
        }

    normalized_toolsets = _normalize_toolsets(toolsets)
    claude = current["claude_command"]
    actions: list[dict[str, Any]] = []
    if current["registered"] and repair:
        removal = command_runner(
            [claude, "mcp", "remove", "--scope", "user", "mcubuddy"]
        )
        actions.append({"action": "remove-mcp", **removal})
        if removal["returncode"] != 0:
            return _setup_error("Could not remove the existing McuBuddy MCP registration.", actions)

    if not current["registered"] or repair:
        addition = command_runner(
            [
                claude,
                "mcp",
                "add",
                "--scope",
                "user",
                "--env",
                f"MCUBUDDY_TOOLSETS={','.join(normalized_toolsets)}",
                "mcubuddy",
                "--",
                str(executable),
                "serve",
            ]
        )
        actions.append({"action": "add-mcp", **addition})
        if addition["returncode"] != 0:
            return _setup_error("Could not register the McuBuddy MCP server.", actions)

    skill = install_skill(
        target="claude",
        home=home,
        source=skill_source,
        force=True,
    )
    skill_action = {key: value for key, value in skill.items() if key != "next_steps"}
    actions.append({"action": "install-skill", **skill_action})
    if skill["status"] != "ok":
        return _setup_error("MCP registration succeeded, but Skill installation failed.", actions)

    verified = inspect_claude_integration(
        repo_root=root,
        runner=command_runner,
        claude_command=claude,
    )
    if not verified["registered"]:
        return _setup_error(
            "Claude Code did not report the McuBuddy MCP registration after setup.", actions
        )
    return {
        "status": "ok",
        "summary": "Configured persistent McuBuddy integration for Claude Code.",
        "registered": True,
        "repo_root": str(root) if root is not None else None,
        "executable": str(executable),
        "skill_source": str(skill_source),
        "skill_source_kind": current["skill_source_kind"],
        "toolsets": normalized_toolsets,
        "actions": actions,
        "restart_required": True,
        "next_steps": [
            "Restart Claude Code so new sessions load the McuBuddy MCP tool surface.",
            "After restart, requests that name McuBuddy should use its MCP tools directly.",
        ],
    }


def remove_claude(
    *,
    confirm: bool = False,
    runner: CommandRunner | None = None,
    claude_command: str | None = None,
) -> dict[str, Any]:
    command_runner = runner or _run_command
    current = inspect_claude_integration(
        runner=command_runner,
        claude_command=claude_command,
    )
    if not current.get("registered"):
        return {**current, "status": "ok", "summary": "McuBuddy MCP was not registered."}
    if not confirm:
        return {
            **current,
            "status": "needs_confirmation",
            "summary": "Confirm removing the user McuBuddy MCP registration from Claude Code.",
        }
    result = command_runner(
        [current["claude_command"], "mcp", "remove", "--scope", "user", "mcubuddy"]
    )
    return {
        "status": "ok" if result["returncode"] == 0 else "error",
        "summary": (
            "Removed the McuBuddy MCP registration from Claude Code."
            if result["returncode"] == 0
            else "Could not remove the McuBuddy MCP registration from Claude Code."
        ),
        "result": result,
        "restart_required": result["returncode"] == 0,
    }


def _resolve_repo_root(repo_root: str | Path | None) -> Path | None:
    if repo_root is not None:
        return Path(repo_root).expanduser().resolve()
    runtime = inspect_runtime_installation()
    checkout = runtime.get("source_checkout")
    return Path(checkout).resolve() if checkout else None


def _resolve_mcubuddy_executable(repo_root: Path | None) -> Path | None:
    if repo_root is not None:
        candidates = [
            repo_root / ".venv" / "Scripts" / "McuBuddy.exe",
            repo_root / ".venv" / "Scripts" / "McuBuddy",
            repo_root / ".venv" / "bin" / "McuBuddy",
        ]
        found = next((path.resolve() for path in candidates if path.is_file()), None)
        if found is not None:
            return found
    executable = shutil.which("McuBuddy")
    return Path(executable).resolve() if executable else None


def _resolve_skill_source(repo_root: Path | None) -> tuple[Path | None, str | None]:
    bundled = _resolve_bundled_skill()
    if bundled is not None:
        return bundled, "package"
    if repo_root is not None:
        checkout_skill = (repo_root / "skills" / "mcubuddy").resolve()
        if (checkout_skill / "SKILL.md").is_file():
            return checkout_skill, "checkout"
    return None, None


def _resolve_bundled_skill() -> Path | None:
    skill = Path(__file__).resolve().parent / "resources" / "mcubuddy_skill"
    return skill if (skill / "SKILL.md").is_file() else None


def _normalize_toolsets(toolsets: Sequence[str]) -> list[str]:
    normalized = list(dict.fromkeys(item.strip().lower() for item in toolsets if item.strip()))
    return normalized or list(DEFAULT_CODEX_TOOLSETS)


def _run_command(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _setup_error(summary: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status": "error", "summary": summary, "actions": actions, "restart_required": False}
