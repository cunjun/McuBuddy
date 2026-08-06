from pathlib import Path

from McuBuddy.session import SessionState
from McuBuddy.tools.project import configure_keil_project, discover_keil_projects


def test_discover_keil_projects_reports_targets_and_outputs(tmp_path: Path) -> None:
    project_dir = tmp_path / "MDK-ARM"
    build_dir = project_dir / "Build"
    build_dir.mkdir(parents=True)
    (project_dir / "Demo.uvprojx").write_text(
        (
            "<Project><Targets><Target><TargetName>Debug</TargetName>"
            "<OutputDirectory>.\\Build\\</OutputDirectory>"
            "</Target></Targets></Project>"
        ),
        encoding="utf-8",
    )
    (project_dir / "Demo.uvoptx").write_text(
        "<Project><TargetName>Debug</TargetName><Device>VendorPart</Device></Project>",
        encoding="utf-8",
    )
    (build_dir / "Demo.axf").write_bytes(b"axf")

    result = discover_keil_projects(str(tmp_path))

    assert result["status"] == "ok"
    assert len(result["projects"]) == 1
    project = result["projects"][0]
    assert project["targets"] == ["Debug"]
    assert project["devices"] == ["VendorPart"]
    assert project["output_dirs"] == [".\\Build\\"]
    assert project["firmware_outputs"][0]["path"].endswith("Demo.axf")
    assert Path(result["root"]).is_absolute()
    assert Path(project["project_path"]).is_absolute()


def test_configure_keil_project_sets_build_and_elf_from_discovery(tmp_path: Path) -> None:
    project_dir = tmp_path / "MDK-ARM"
    objects_dir = project_dir / "Objects"
    objects_dir.mkdir(parents=True)
    (project_dir / "Demo.uvprojx").write_text(
        "<Project><TargetName>Debug</TargetName></Project>",
        encoding="utf-8",
    )
    axf = objects_dir / "Demo.axf"
    axf.write_bytes(b"axf")

    session = SessionState()
    result = configure_keil_project(
        session,
        root=str(tmp_path),
        uv4_path=r"C:\Keil_v5\UV4\UV4.exe",
    )

    assert result["status"] == "ok"
    assert session.config.build.project_path.endswith("Demo.uvprojx")
    assert session.config.build.target_name == "Debug"
    assert session.config.elf.path == str(axf)


def test_configure_keil_project_normalizes_explicit_relative_paths(tmp_path, monkeypatch) -> None:
    project_dir = tmp_path / "firmware"
    project_dir.mkdir()
    project = project_dir / "Demo.uvprojx"
    project.write_text("<Project><TargetName>Debug</TargetName></Project>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    session = SessionState()
    configure_keil_project(session, project_path="firmware/Demo.uvprojx")

    assert session.config.build.project_path == str(project.resolve())
