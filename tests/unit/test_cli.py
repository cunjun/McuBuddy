from __future__ import annotations

import json

import pytest

from McuBuddy import cli
from McuBuddy.config import load_config, parse_cli_overrides


def test_help_lists_management_commands(capsys) -> None:
    parser = cli.build_parser()

    try:
        parser.parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert "doctor" in output
    assert "config" in output
    assert "probes" in output
    assert "skill" in output
    assert "packs" in output
    assert "home" in output
    assert "setup" in output


def test_setup_codex_dispatches_active_registration(monkeypatch, capsys) -> None:
    captured = {}

    def fake_setup(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "summary": "configured", "restart_required": True}

    monkeypatch.setattr(cli, "setup_codex", fake_setup)

    assert cli.main(["setup", "codex", "--toolsets", "probe,diagnose", "--confirm", "--json"]) == 0

    assert captured["toolsets"] == ["probe", "diagnose"]
    assert captured["confirm"] is True
    assert json.loads(capsys.readouterr().out)["restart_required"] is True


def test_setup_status_is_read_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "inspect_codex_integration",
        lambda **kwargs: {"status": "ok", "summary": "registered"},
    )

    assert cli.main(["setup", "status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_serve_uses_stdio_transport(monkeypatch) -> None:
    calls = []

    class _Server:
        def run(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr("McuBuddy.server.create_server", lambda *args, **kwargs: _Server())
    monkeypatch.setattr(cli, "create_probe_backend", lambda *args, **kwargs: object())

    assert cli.main(["serve"]) == 0
    assert calls == [{"transport": "stdio"}]


def test_cli_rejects_network_transport_options() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["serve", "--transport", "http"])


def test_home_set_show_and_clear_json(tmp_path, capsys) -> None:
    checkout = tmp_path / "McuBuddy"
    (checkout / "src" / "McuBuddy").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(
        '[project]\nname = "McuBuddy"\n',
        encoding="utf-8",
    )

    assert (
        cli.main(
            [
                "home",
                "set",
                str(checkout),
                "--home",
                str(tmp_path),
                "--confirm",
                "--json",
            ]
        )
        == 0
    )
    saved = json.loads(capsys.readouterr().out)
    assert saved["installation"]["repo_root"] == str(checkout.resolve())

    assert cli.main(["home", "show", "--home", str(tmp_path), "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["installation"]["repo_root"] == str(checkout.resolve())

    assert cli.main(["home", "clear", "--home", str(tmp_path), "--confirm", "--json"]) == 0
    capsys.readouterr()


def test_config_generate_prints_toml(capsys) -> None:
    assert cli.main(["config", "generate"]) == 0

    output = capsys.readouterr().out
    assert "[server]" in output
    assert "[security]" in output
    assert 'tool_profile = "core"' in output


def test_config_validate_reports_invalid_profile(tmp_path, capsys) -> None:
    config = tmp_path / "mcubuddy.toml"
    config.write_text('[server]\ntool_profile = "expert"\n', encoding="utf-8")

    assert cli.main(["config", "validate", str(config)]) == 1

    output = capsys.readouterr().out
    assert "Configuration is invalid" in output
    assert "server.tool_profile" in output


def test_skill_install_dry_run_json(tmp_path, capsys) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("# mcubuddy\n", encoding="utf-8")

    assert (
        cli.main(
            [
                "skill",
                "install",
                "--target",
                "both",
                "--home",
                str(tmp_path / "home"),
                "--source",
                str(source),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["target"] == "both"
    assert {entry["status"] for entry in report["entries"]} == {"would_install"}


def test_packs_diagnose_json_reports_managed_target(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "diagnose_pack",
        lambda target: {
            "status": "warning",
            "summary": "pack missing",
            "target": target.lower(),
        },
    )

    assert cli.main(["packs", "diagnose", "PY32F030X8", "--json"]) == 0

    assert json.loads(capsys.readouterr().out)["target"] == "py32f030x8"


def test_packs_install_passes_explicit_confirmation(monkeypatch, tmp_path, capsys) -> None:
    calls = []

    def fake_install(target, *, destination, confirm):
        calls.append((target, destination, confirm))
        return {"status": "ok", "summary": "installed"}

    monkeypatch.setattr(cli, "install_pack", fake_install)

    assert (
        cli.main(
            [
                "packs",
                "install",
                "py32f030x8",
                "--destination",
                str(tmp_path),
                "--confirm",
                "--json",
            ]
        )
        == 0
    )
    assert calls == [("py32f030x8", str(tmp_path), True)]
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_probes_list_json_uses_configured_backend(monkeypatch, tmp_path, capsys) -> None:
    config = tmp_path / "mcubuddy.toml"
    config.write_text('[probe]\nbackend = "jlink"\n', encoding="utf-8")
    calls = []

    class _Probe:
        def enumerate_probes(self):
            return [{"identifier": "J-Link", "unique_id": "abc"}]

    def fake_create_backend(name, **kwargs):
        calls.append((name, kwargs))
        return _Probe()

    monkeypatch.setattr(cli, "create_probe_backend", fake_create_backend)

    assert cli.main(["probes", "list", "--config", str(config), "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["probes"] == [{"identifier": "J-Link", "unique_id": "abc"}]
    assert calls[0][0] == "jlink"


def test_doctor_json_reports_loaded_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "build_doctor_report",
        lambda config: {
            "status": "warning",
            "summary": "doctor summary",
            "checks": [{"name": "probe", "status": "warning", "summary": "none"}],
            "profile": config.server.tool_profile,
        },
    )

    assert cli.main(["doctor", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "warning"
    assert report["profile"] == "core"


def test_config_precedence_is_cli_over_environment_over_file(tmp_path) -> None:
    config_path = tmp_path / "mcubuddy.toml"
    config_path.write_text("[memory]\nmax_read_size = 512\n", encoding="utf-8")

    config = load_config(
        config_path,
        environ={"MCUBUDDY_MAX_READ_SIZE": "1024"},
        cli_overrides=parse_cli_overrides(["memory.max_read_size=2048"]),
    )

    assert config.memory.max_read_size == 2048


def test_tool_profile_environment_override_remains_normalized() -> None:
    config = load_config(environ={"MCUBUDDY_TOOL_PROFILE": " CORE "})

    assert config.server.tool_profile == "core"


def test_toolsets_can_be_selected_from_environment() -> None:
    config = load_config(environ={"MCUBUDDY_TOOLSETS": " diagnose,rtos "})

    assert config.server.toolsets == ["diagnose", "rtos"]


def test_parse_cli_overrides_converts_scalar_values() -> None:
    overrides = parse_cli_overrides(
        [
            "memory.max_read_size=8192",
            "memory.allow_write=true",
            "probe.target=stm32f103c8",
        ]
    )

    assert overrides == {
        "memory": {"max_read_size": 8192, "allow_write": True},
        "probe": {"target": "stm32f103c8"},
    }


def test_config_show_applies_set_after_environment(monkeypatch, tmp_path, capsys) -> None:
    config_path = tmp_path / "mcubuddy.toml"
    config_path.write_text("[memory]\nmax_read_size = 512\n", encoding="utf-8")
    monkeypatch.setenv("MCUBUDDY_MAX_READ_SIZE", "1024")

    assert (
        cli.main(
            [
                "config",
                "show",
                "--config",
                str(config_path),
                "--set",
                "memory.max_read_size=2048",
                "--json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["memory"]["max_read_size"] == 2048


def test_unknown_cli_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown config override"):
        parse_cli_overrides(["memory.unknown_limit=1"])


def test_unknown_cli_override_returns_cli_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["config", "show", "--set", "memory.unknown_limit=1"])

    assert exc_info.value.code == 2
    assert "Unknown config override memory.unknown_limit" in capsys.readouterr().err


def test_no_argument_startup_keeps_legacy_serve_behavior(monkeypatch) -> None:
    calls = []

    class _App:
        def run(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.setattr("McuBuddy.server.create_server", lambda *args, **kwargs: _App())

    assert cli.main([]) == 0
    assert calls == [{"transport": "stdio"}]


def test_serve_uses_effective_probe_backend(monkeypatch) -> None:
    captured = {}
    backend = object()

    class _App:
        def run(self, **kwargs) -> None:
            captured["run_kwargs"] = kwargs

    def fake_create_server(session, *, tool_profile, toolsets):
        captured["session"] = session
        captured["tool_profile"] = tool_profile
        captured["toolsets"] = toolsets
        return _App()

    monkeypatch.setattr("McuBuddy.server.create_server", fake_create_server)
    monkeypatch.setattr(cli, "create_probe_backend", lambda name, **kwargs: backend)

    assert cli.main(["serve", "--set", "probe.backend=jlink"]) == 0
    assert captured["session"].services.probe is backend
    assert captured["session"].config.probe.backend == "jlink"
    assert captured["tool_profile"] == "core"
    assert captured["toolsets"] == []
    assert captured["run_kwargs"] == {"transport": "stdio"}


def test_doctor_config_error_keeps_json_schema_version(tmp_path, capsys) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text("[memory\n", encoding="utf-8")

    assert cli.main(["doctor", "--config", str(config_path), "--json"]) == 1

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {
        "schema_version",
        "status",
        "summary",
        "version",
        "checks",
        "config",
    }
    assert report["schema_version"] == "1.0"
    assert report["status"] == "error"
    assert report["config"] is None
