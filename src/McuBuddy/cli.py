from __future__ import annotations

import argparse
import json
from typing import Any

from .config import (
    config_for_display,
    config_to_toml,
    load_config,
    parse_cli_overrides,
    validate_config_file,
)
from .codex_integration import (
    inspect_claude_integration,
    inspect_codex_integration,
    remove_claude,
    remove_codex,
    setup_claude,
    setup_codex,
)
from .doctor import build_doctor_error_report, build_doctor_report
from .installation_registry import (
    clear_installation_home,
    get_installation_home,
    set_installation_home,
)
from .pack_manager import diagnose_pack, install_pack
from .session import SessionState, create_probe_backend
from .skill_installer import install_skill


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"
    try:
        if command == "serve":
            return _serve(args)
        if command == "doctor":
            return _doctor(args)
        if command == "config":
            return _config(args)
        if command == "probes":
            return _probes(args)
        if command == "skill":
            return _skill(args)
        if command == "packs":
            return _packs(args)
        if command == "home":
            return _home(args)
        if command == "setup":
            return _setup(args)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    parser.error(f"unknown command: {command}")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="McuBuddy")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Start the MCP stdio server.")
    _add_config_options(serve)

    doctor = subparsers.add_parser("doctor", help="Check local runtime readiness.")
    _add_config_options(doctor)
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    config = subparsers.add_parser("config", help="Generate, validate, or show config.")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("generate", help="Print a sample TOML configuration.")
    validate = config_sub.add_parser("validate", help="Validate a TOML configuration.")
    validate.add_argument("path", help="Path to the config file.")
    show = config_sub.add_parser("show", help="Show the effective configuration.")
    _add_config_options(show)
    show.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    probes = subparsers.add_parser("probes", help="Probe management commands.")
    probes_sub = probes.add_subparsers(dest="probes_command", required=True)
    probe_list = probes_sub.add_parser("list", help="List connected debug probes.")
    _add_config_options(probe_list)
    probe_list.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    skill = subparsers.add_parser("skill", help="Skill management commands.")
    skill_sub = skill.add_subparsers(dest="skill_command", required=True)
    install = skill_sub.add_parser("install", help="Install the mcubuddy assistant skill.")
    install.add_argument("--target", choices=["codex", "claude", "both"], default="codex")
    install.add_argument("--home", help="Home directory used to resolve assistant directories.")
    install.add_argument("--source", help="Source mcubuddy skill directory.")
    install.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    install.add_argument("--force", action="store_true", help="Replace existing installs.")
    install.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    packs = subparsers.add_parser("packs", help="CMSIS-Pack management commands.")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)
    pack_diagnose = packs_sub.add_parser(
        "diagnose", help="Report the required CMSIS-Pack and local verification state."
    )
    pack_diagnose.add_argument("target", help="Target MCU name, for example PY32F030X8.")
    pack_diagnose.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    pack_install = packs_sub.add_parser(
        "install", help="Download and checksum-verify a managed CMSIS-Pack."
    )
    pack_install.add_argument("target", help="Target MCU name, for example PY32F030X8.")
    pack_install.add_argument(
        "--destination", default="packs", help="Directory used to store the verified pack."
    )
    pack_install.add_argument(
        "--confirm", action="store_true", help="Confirm the network download and file write."
    )
    pack_install.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    home = subparsers.add_parser("home", help="Manage the local McuBuddy installation record.")
    home_sub = home.add_subparsers(dest="home_command", required=True)
    home_show = home_sub.add_parser("show", help="Show the default McuBuddy installation.")
    home_show.add_argument("--home", help="Home directory containing the .mcubuddy registry.")
    home_show.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    home_set = home_sub.add_parser("set", help="Save the default McuBuddy checkout.")
    home_set.add_argument("path", help="Path to the local McuBuddy checkout.")
    home_set.add_argument("--home", help="Home directory containing the .mcubuddy registry.")
    home_set.add_argument("--confirm", action="store_true", help="Confirm the user-level write.")
    home_set.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    home_clear = home_sub.add_parser("clear", help="Clear the default McuBuddy checkout.")
    home_clear.add_argument("--home", help="Home directory containing the .mcubuddy registry.")
    home_clear.add_argument("--confirm", action="store_true", help="Confirm the user-level write.")
    home_clear.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    setup = subparsers.add_parser("setup", help="Configure persistent assistant integrations.")
    setup_sub = setup.add_subparsers(dest="setup_command", required=True)
    setup_codex_parser = setup_sub.add_parser("codex", help="Install or repair Codex integration.")
    setup_codex_parser.add_argument("--repo-root", help="McuBuddy source checkout to register.")
    setup_codex_parser.add_argument("--home", help="Home directory used for Skill installation.")
    setup_codex_parser.add_argument(
        "--toolsets", default="probe,diagnose", help="Comma-separated startup toolsets."
    )
    setup_codex_parser.add_argument("--repair", action="store_true")
    setup_codex_parser.add_argument("--confirm", action="store_true")
    setup_codex_parser.add_argument("--json", action="store_true")
    setup_claude_parser = setup_sub.add_parser(
        "claude", help="Install or repair Claude Code integration."
    )
    setup_claude_parser.add_argument("--repo-root", help="McuBuddy source checkout to register.")
    setup_claude_parser.add_argument("--home", help="Home directory used for Skill installation.")
    setup_claude_parser.add_argument(
        "--toolsets", default="probe,diagnose", help="Comma-separated startup toolsets."
    )
    setup_claude_parser.add_argument("--repair", action="store_true")
    setup_claude_parser.add_argument("--confirm", action="store_true")
    setup_claude_parser.add_argument("--json", action="store_true")
    setup_status = setup_sub.add_parser("status", help="Inspect assistant MCP registration.")
    setup_status.add_argument("--repo-root")
    setup_status.add_argument("--target", choices=["codex", "claude"], default="codex")
    setup_status.add_argument("--json", action="store_true")
    setup_remove = setup_sub.add_parser("remove", help="Remove assistant MCP registration.")
    setup_remove.add_argument("--target", choices=["codex", "claude"], default="codex")
    setup_remove.add_argument("--confirm", action="store_true")
    setup_remove.add_argument("--json", action="store_true")

    return parser


def _add_config_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Path to a McuBuddy TOML config file.")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="SECTION.FIELD=VALUE",
        help="Override a config value. May be specified more than once.",
    )


def _load_command_config(args: argparse.Namespace):
    return load_config(
        getattr(args, "config", None),
        cli_overrides=parse_cli_overrides(getattr(args, "set", [])),
    )


def _serve(args: argparse.Namespace) -> int:
    from .server import create_server

    config = _load_command_config(args)
    session = SessionState(config=config)
    session.services.probe = create_probe_backend(
        config.probe.backend,
        jlink_dll_path=config.probe.jlink_dll_path,
        probe_rs_sidecar_path=config.probe.probe_rs_sidecar_path,
    )
    create_server(
        session,
        tool_profile=config.server.tool_profile,
        toolsets=config.server.toolsets,
    ).run(transport="stdio")
    return 0


def _doctor(args: argparse.Namespace) -> int:
    try:
        config = _load_command_config(args)
    except Exception as exc:
        report = build_doctor_error_report(str(exc))
    else:
        report = build_doctor_report(config)
    _print_report(report, as_json=args.json)
    return 0 if report["status"] in ("ok", "warning") else 1


def _config(args: argparse.Namespace) -> int:
    if args.config_command == "generate":
        print(config_to_toml(), end="")
        return 0
    if args.config_command == "validate":
        _, errors = validate_config_file(args.path)
        if errors:
            print("Configuration is invalid.")
            for error in errors:
                loc = ".".join(str(part) for part in error.get("loc", ()))
                print(f"- {loc}: {error.get('msg')}")
            return 1
        print("Configuration is valid.")
        return 0
    if args.config_command == "show":
        config = _load_command_config(args)
        _print_report(config_for_display(config), as_json=args.json)
        return 0
    raise ValueError(f"Unknown config command: {args.config_command}")


def _probes(args: argparse.Namespace) -> int:
    config = _load_command_config(args)
    try:
        session = SessionState()
        session.config = config
        session.services.probe = create_probe_backend(
            config.probe.backend,
            jlink_dll_path=config.probe.jlink_dll_path,
            probe_rs_sidecar_path=config.probe.probe_rs_sidecar_path,
        )
        probes = session.services.probe.enumerate_probes()
        report = {
            "status": "ok",
            "summary": f"Found {len(probes)} connected probe(s)."
            if probes
            else "No probes detected. Check USB connection and driver installation.",
            "probes": probes,
        }
    except Exception as exc:
        report = {"status": "warning", "summary": f"Probe discovery failed: {exc}", "probes": []}
    _print_report(report, as_json=args.json)
    return 0


def _skill(args: argparse.Namespace) -> int:
    if args.skill_command != "install":
        raise ValueError(f"Unknown skill command: {args.skill_command}")
    report = install_skill(
        target=args.target,
        home=args.home,
        source=args.source,
        dry_run=args.dry_run,
        force=args.force,
    )
    _print_report(report, as_json=args.json)
    return 0 if report["status"] == "ok" else 1


def _packs(args: argparse.Namespace) -> int:
    if args.packs_command == "diagnose":
        report = diagnose_pack(args.target)
        _print_report(report, as_json=args.json)
        return 1 if report["status"] == "error" else 0
    if args.packs_command == "install":
        report = install_pack(
            args.target,
            destination=args.destination,
            confirm=args.confirm,
        )
        _print_report(report, as_json=args.json)
        return 0 if report["status"] == "ok" else 1
    raise ValueError(f"Unknown packs command: {args.packs_command}")


def _home(args: argparse.Namespace) -> int:
    if args.home_command == "show":
        report = get_installation_home(home=args.home)
    elif args.home_command == "set":
        report = set_installation_home(
            args.path,
            home=args.home,
            confirm=args.confirm,
        )
    elif args.home_command == "clear":
        report = clear_installation_home(home=args.home, confirm=args.confirm)
    else:
        raise ValueError(f"Unknown home command: {args.home_command}")
    _print_report(report, as_json=args.json)
    return 0 if report["status"] in ("ok", "not_configured") else 1


def _setup(args: argparse.Namespace) -> int:
    if args.setup_command == "codex":
        report = setup_codex(
            repo_root=args.repo_root,
            home=args.home,
            toolsets=[item for item in args.toolsets.split(",") if item.strip()],
            confirm=args.confirm,
            repair=args.repair,
        )
    elif args.setup_command == "claude":
        report = setup_claude(
            repo_root=args.repo_root,
            home=args.home,
            toolsets=[item for item in args.toolsets.split(",") if item.strip()],
            confirm=args.confirm,
            repair=args.repair,
        )
    elif args.setup_command == "status":
        inspect = (
            inspect_claude_integration
            if args.target == "claude"
            else inspect_codex_integration
        )
        report = inspect(repo_root=args.repo_root)
    elif args.setup_command == "remove":
        remove = remove_claude if args.target == "claude" else remove_codex
        report = remove(confirm=args.confirm)
    else:
        raise ValueError(f"Unknown setup command: {args.setup_command}")
    _print_report(report, as_json=args.json)
    return 0 if report["status"] in ("ok", "not_configured") else 1


def _print_report(report: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return
    summary = report.get("summary")
    if summary:
        print(summary)
    if "checks" in report:
        for check in report["checks"]:
            print(f"- {check['name']}: {check['status']} - {check['summary']}")
    if "probes" in report:
        for index, probe in enumerate(report["probes"], start=1):
            print(f"{index}. {probe}")
    if "entries" in report:
        for entry in report["entries"]:
            print(f"{entry['kind']}: {entry['path']} ({entry['status']})")
    if "next_steps" in report:
        for step in report["next_steps"]:
            print(f"- {step}")
    if not any(key in report for key in ("checks", "probes", "entries")) and isinstance(
        report, dict
    ):
        for key, value in report.items():
            print(f"{key}: {value}")
