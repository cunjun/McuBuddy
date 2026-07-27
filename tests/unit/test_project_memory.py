from pathlib import Path

from McuBuddy.config import RuntimeConfig
from McuBuddy.tools.project_memory import inspect_project_memory, write_project_memory


def _make_keil_project(root: Path) -> Path:
    project_dir = root / "MDK-ARM"
    project_dir.mkdir(parents=True)
    project = project_dir / "Project.uvprojx"
    project.write_text(
        "<Project><TargetName>Debug</TargetName><Device>PY32F030X8</Device></Project>",
        encoding="utf-8",
    )
    return project


def test_inspect_prefers_explicit_target_over_current_workspace(tmp_path: Path) -> None:
    tool_root = tmp_path / "McuBuddy"
    firmware_root = tmp_path / "firmware"
    tool_root.mkdir()
    _make_keil_project(firmware_root)

    result = inspect_project_memory(
        str(firmware_root),
        current_root=str(tool_root),
    )

    assert result["status"] == "missing"
    assert result["target_root"] == str(firmware_root.resolve())
    assert result["memory"]["proposed_path"] == str(
        firmware_root.resolve() / ".mcubuddy" / "project-memory.md"
    )
    assert result["discovery"]["keil_projects"][0]["devices"] == ["PY32F030X8"]
    assert not (firmware_root / ".mcubuddy").exists()


def test_inspect_reads_existing_memory_and_marks_volatile_values_last_known(
    tmp_path: Path,
) -> None:
    memory = tmp_path / "MEMORY.md"
    memory.write_text(
        "# Project Debug Memory\n\n"
        "## Confirmed\n\n"
        "- MCU: PY32F030X8\n"
        "- Keil project: MDK-ARM/Project.uvprojx\n\n"
        "## Last known\n\n"
        "- Serial port: COM10\n"
        "- Probe ID: ABC123\n",
        encoding="utf-8",
    )

    result = inspect_project_memory(str(tmp_path))

    assert result["status"] == "ok"
    assert result["memory"]["path"] == str(memory.resolve())
    assert result["facts"]["mcu"] == {
        "value": "PY32F030X8",
        "state": "confirmed",
    }
    assert result["facts"]["serial_port"] == {
        "value": "COM10",
        "state": "last_known",
    }


def test_inspect_reports_ambiguous_memory_files(tmp_path: Path) -> None:
    (tmp_path / "MEMORY.md").write_text("# one\n", encoding="utf-8")
    (tmp_path / "PROJECT_MEMORY.md").write_text("# two\n", encoding="utf-8")

    result = inspect_project_memory(str(tmp_path))

    assert result["status"] == "ambiguous"
    assert len(result["memory"]["candidates"]) == 2


def test_write_requires_confirmation_and_stays_inside_target(tmp_path: Path) -> None:
    preview = write_project_memory(
        str(tmp_path),
        "# Project Debug Memory\n",
        config=RuntimeConfig(),
    )
    assert preview["status"] == "confirmation_required"
    assert not (tmp_path / ".mcubuddy" / "project-memory.md").exists()

    result = write_project_memory(
        str(tmp_path),
        "# Project Debug Memory\n",
        config=RuntimeConfig(),
        confirm=True,
    )
    assert result["status"] == "ok"
    assert (tmp_path / ".mcubuddy" / "project-memory.md").read_text(
        encoding="utf-8"
    ) == "# Project Debug Memory\n"


def test_write_respects_allowed_file_paths(tmp_path: Path) -> None:
    target = tmp_path / "target"
    allowed = tmp_path / "allowed"
    target.mkdir()
    allowed.mkdir()
    config = RuntimeConfig.model_validate(
        {"security": {"allowed_file_paths": [str(allowed)]}}
    )

    result = write_project_memory(
        str(target),
        "# Project Debug Memory\n",
        config=config,
        confirm=True,
    )

    assert result["status"] == "error"
    assert result["security"]["guard"] == "security.allowed_file_paths"
    assert not (target / ".mcubuddy").exists()


def test_write_refuses_mcubuddy_root_without_explicit_override(tmp_path: Path) -> None:
    (tmp_path / "skills" / "mcubuddy").mkdir(parents=True)
    (tmp_path / "skills" / "mcubuddy" / "SKILL.md").write_text("", encoding="utf-8")
    (tmp_path / "src" / "McuBuddy").mkdir(parents=True)

    result = write_project_memory(
        str(tmp_path),
        "# Project Debug Memory\n",
        config=RuntimeConfig(),
        confirm=True,
    )

    assert result["status"] == "error"
    assert result["guard"] == "target_project_root"
