from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

from ..config import RuntimeConfig
from ..security_guards import ensure_file_allowed
from .project import discover_keil_projects


_CANONICAL_RELATIVE_PATH = Path(".mcubuddy") / "project-memory.md"
_MEMORY_CANDIDATES = (
    _CANONICAL_RELATIVE_PATH,
    Path("PROJECT_MEMORY.md"),
    Path("MEMORY.md"),
)
_FACT_KEYS = {
    "mcu": "mcu",
    "keil project": "keil_project",
    "keil executable": "keil_executable",
    "target": "target",
    "flash method": "flash_method",
    "serial port": "serial_port",
    "baud rate": "baud_rate",
    "probe": "probe",
    "probe id": "probe_id",
}
_FACT_RE = re.compile(r"^-\s*([^:]+):\s*(.*?)\s*$")


def inspect_project_memory(
    target_root: str,
    *,
    current_root: str | None = None,
    max_depth: int = 6,
) -> dict:
    """Inspect target-project memory and Keil metadata without changing files."""
    resolved = _resolve_existing_directory(target_root)
    if isinstance(resolved, dict):
        return resolved
    root = resolved
    candidates = [
        path.resolve()
        for relative in _MEMORY_CANDIDATES
        if (path := root / relative).is_file()
    ]
    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "summary": "Multiple project memory files were found; select one explicitly.",
            "target_root": str(root),
            "memory": {"candidates": [str(path) for path in candidates]},
        }

    discovery = discover_keil_projects(str(root), max_depth=max_depth)
    projects = discovery.get("projects", []) if discovery.get("status") == "ok" else []
    proposed_path = root / _CANONICAL_RELATIVE_PATH
    base = {
        "target_root": str(root),
        "current_root": str(Path(current_root).resolve()) if current_root else None,
        "discovery": {"keil_projects": projects},
    }
    if candidates:
        memory_path = candidates[0]
        content = memory_path.read_text(encoding="utf-8", errors="replace")
        return {
            "status": "ok",
            "summary": "Loaded target-project memory.",
            **base,
            "memory": {"path": str(memory_path), "content": content},
            "facts": _parse_facts(content),
        }

    proposal = _render_proposal(root, projects)
    return {
        "status": "missing",
        "summary": "No target-project memory exists; review the read-only proposal before writing.",
        **base,
        "memory": {
            "proposed_path": str(proposed_path),
            "proposed_content": proposal,
        },
        "facts": _facts_from_projects(projects),
    }


def write_project_memory(
    target_root: str,
    content: str,
    *,
    config: RuntimeConfig,
    confirm: bool = False,
    update_existing: bool = False,
    allow_mcubuddy_target: bool = False,
) -> dict:
    """Write canonical target-project memory after explicit confirmation."""
    resolved = _resolve_existing_directory(target_root)
    if isinstance(resolved, dict):
        return resolved
    root = resolved
    destination = root / _CANONICAL_RELATIVE_PATH

    if _looks_like_mcubuddy_root(root) and not allow_mcubuddy_target:
        return {
            "status": "error",
            "summary": "Refusing to write project memory into the McuBuddy repository unless it is explicitly selected as the debug target.",
            "guard": "target_project_root",
            "target_root": str(root),
        }
    if not confirm:
        return {
            "status": "confirmation_required",
            "summary": "Review and confirm the target-project memory write.",
            "target_root": str(root),
            "path": str(destination),
            "content": content,
        }
    if blocked := ensure_file_allowed(config, destination):
        return blocked
    if destination.exists() and not update_existing:
        return {
            "status": "error",
            "summary": "Project memory already exists; pass update_existing=True to replace it.",
            "guard": "project_memory.update_existing",
            "path": str(destination),
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = destination.parent.resolve()
    if root != resolved_parent and root not in resolved_parent.parents:
        return {
            "status": "error",
            "summary": "Project memory destination escapes the confirmed target root.",
            "guard": "target_project_root",
            "target_root": str(root),
            "path": str(resolved_parent / destination.name),
        }

    handle, temp_name = tempfile.mkstemp(
        prefix=".project-memory-",
        suffix=".tmp",
        dir=resolved_parent,
        text=True,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        Path(temp_name).replace(destination)
    finally:
        Path(temp_name).unlink(missing_ok=True)

    return {
        "status": "ok",
        "summary": "Wrote target-project memory.",
        "target_root": str(root),
        "path": str(destination),
    }


def _resolve_existing_directory(path: str) -> Path | dict:
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
    except OSError as exc:
        return {
            "status": "error",
            "summary": f"Target project root could not be resolved: {exc}",
            "guard": "target_project_root",
        }
    if not resolved.is_dir():
        return {
            "status": "error",
            "summary": "Target project root is not a directory.",
            "guard": "target_project_root",
            "target_root": str(resolved),
        }
    return resolved


def _looks_like_mcubuddy_root(root: Path) -> bool:
    return (root / "skills" / "mcubug" / "SKILL.md").is_file() and (
        root / "src" / "McuBuddy"
    ).is_dir()


def _parse_facts(content: str) -> dict[str, dict[str, str]]:
    facts: dict[str, dict[str, str]] = {}
    state = "detected"
    for raw_line in content.splitlines():
        heading = raw_line.strip().lower()
        if heading.startswith("## confirmed") or heading.startswith("## 已确认"):
            state = "confirmed"
        elif heading.startswith("## last known") or heading.startswith("## 上次确认"):
            state = "last_known"
        elif heading.startswith("## detected") or heading.startswith("## 扫描发现"):
            state = "detected"
        match = _FACT_RE.match(raw_line.strip())
        if not match:
            continue
        key = _FACT_KEYS.get(match.group(1).strip().lower())
        value = match.group(2).strip()
        if key and value:
            facts[key] = {"value": value, "state": state}
    return facts


def _facts_from_projects(projects: list[dict]) -> dict[str, dict[str, str]]:
    if len(projects) != 1:
        return {}
    project = projects[0]
    facts = {
        "keil_project": {
            "value": project["project_path"],
            "state": "detected",
        }
    }
    devices = project.get("devices") or []
    if len(devices) == 1:
        facts["mcu"] = {"value": devices[0], "state": "detected"}
    targets = project.get("targets") or []
    if len(targets) == 1:
        facts["target"] = {"value": targets[0], "state": "detected"}
    return facts


def _render_proposal(root: Path, projects: list[dict]) -> str:
    facts = _facts_from_projects(projects)
    lines = [
        "# Project Debug Memory",
        "",
        "## Confirmed",
        "",
        f"- Firmware root: {root}",
        "",
        "## Detected - confirm before promoting",
        "",
    ]
    labels = {
        "mcu": "MCU",
        "keil_project": "Keil project",
        "target": "Target",
    }
    for key, label in labels.items():
        if key in facts:
            lines.append(f"- {label}: {facts[key]['value']}")
    lines.extend(
        [
            "",
            "## Last known - verify each session",
            "",
            "- Serial port:",
            "- Probe ID:",
            "",
            "## Verification notes",
            "",
            "- Unknown values remain unknown until detected or confirmed.",
            "",
        ]
    )
    return "\n".join(lines)
