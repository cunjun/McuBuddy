from __future__ import annotations

import json
import os
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

REGISTRY_SCHEMA_VERSION = "1.0"


def inspect_runtime_installation() -> dict[str, Any]:
    """Describe the installed distribution independently of any source checkout."""
    try:
        distribution = metadata.distribution("McuBuddy")
    except metadata.PackageNotFoundError:
        distribution = None

    executable = shutil.which("McuBuddy")
    package_root = Path(__file__).resolve().parent
    checkout_root = _find_checkout_root(package_root)
    return {
        "status": "ok" if distribution is not None else "warning",
        "summary": (
            f"McuBuddy {distribution.version} is installed."
            if distribution is not None
            else "McuBuddy is importable, but installed distribution metadata was not found."
        ),
        "distribution_version": distribution.version if distribution is not None else None,
        "package_root": str(package_root),
        "python_executable": sys.executable,
        "command_executable": executable,
        "source_checkout": str(checkout_root) if checkout_root is not None else None,
    }


def get_installation_home(*, home: str | Path | None = None) -> dict[str, Any]:
    registry_path = _registry_path(home)
    if not registry_path.is_file():
        return {
            "status": "not_configured",
            "summary": "No default McuBuddy installation is configured.",
            "registry_path": str(registry_path),
            "installation": None,
        }

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "summary": f"Could not read McuBuddy installation registry: {exc}",
            "registry_path": str(registry_path),
            "installation": None,
        }

    installation = data.get("default")
    if not isinstance(installation, dict):
        return {
            "status": "not_configured",
            "summary": "No default McuBuddy installation is configured.",
            "registry_path": str(registry_path),
            "installation": None,
        }
    return {
        "status": "ok",
        "summary": f"Default McuBuddy installation: {installation.get('repo_root')}",
        "registry_path": str(registry_path),
        "installation": installation,
    }


def set_installation_home(
    repo_root: str | Path,
    *,
    home: str | Path | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve()
    registry_path = _registry_path(home)
    installation = _inspect_checkout(root)
    if installation is None:
        return {
            "status": "error",
            "summary": (
                f"{root} is not a McuBuddy checkout; expected pyproject.toml "
                "and src/McuBuddy."
            ),
            "registry_path": str(registry_path),
            "installation": None,
        }
    if not confirm:
        return {
            "status": "needs_confirmation",
            "summary": f"Confirm saving {root} as the default McuBuddy installation.",
            "registry_path": str(registry_path),
            "installation": installation,
        }

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "default": installation,
    }
    temporary_path = registry_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(registry_path)
    return {
        "status": "ok",
        "summary": f"Saved {root} as the default McuBuddy installation.",
        "registry_path": str(registry_path),
        "installation": installation,
    }


def clear_installation_home(
    *,
    home: str | Path | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    registry_path = _registry_path(home)
    current = get_installation_home(home=home)
    if current["status"] == "not_configured":
        return {
            "status": "ok",
            "summary": "No default McuBuddy installation was configured.",
            "registry_path": str(registry_path),
            "installation": None,
        }
    if current["status"] == "error":
        return current
    if not confirm:
        return {
            "status": "needs_confirmation",
            "summary": "Confirm clearing the default McuBuddy installation.",
            "registry_path": str(registry_path),
            "installation": current["installation"],
        }

    registry_path.unlink()
    return {
        "status": "ok",
        "summary": "Cleared the default McuBuddy installation.",
        "registry_path": str(registry_path),
        "installation": None,
    }


def _registry_path(home: str | Path | None) -> Path:
    if home is not None:
        base = Path(home).expanduser()
    else:
        env_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
        base = Path(env_home).expanduser() if env_home else Path.home()
    return (base / ".mcubuddy" / "installations.json").resolve()


def _inspect_checkout(root: Path) -> dict[str, str | None] | None:
    if not (root / "pyproject.toml").is_file():
        return None
    if not (root / "src" / "McuBuddy").is_dir():
        return None

    candidates = [
        root / ".venv" / "Scripts" / "McuBuddy.exe",
        root / ".venv" / "Scripts" / "McuBuddy",
        root / ".venv" / "bin" / "McuBuddy",
    ]
    executable = next((path.resolve() for path in candidates if path.is_file()), None)
    return {
        "repo_root": str(root),
        "executable": str(executable) if executable is not None else None,
    }


def _find_checkout_root(package_root: Path) -> Path | None:
    for candidate in package_root.parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "McuBuddy"
        ).is_dir():
            return candidate
    return None
