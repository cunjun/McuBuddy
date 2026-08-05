from __future__ import annotations

from ...backends.probe.base import ProbeCapability, probe_supports
from ...chip_matcher import match_chip_name as _match_chip_name
from ...config import connect_attempts_to_dicts
from ...device_patch_manager import resolve_device_patch as _resolve_device_patch
from ...session import SessionState


def list_connected_probes(session: SessionState) -> dict:
    probes = session.services.probe.enumerate_probes()
    return {
        "status": "ok",
        "summary": f"Found {len(probes)} connected probe(s).",
        "probes": probes,
        "hint": "Use 'unique_id' from this list with probe_connect() to target a specific probe."
        if probes
        else "No probes detected. Check USB connection and driver installation.",
    }


def connect_probe(session: SessionState, target: str, unique_id: str | None = None) -> dict:
    match_result = _match_chip_name(target, backend=session.config.probe.backend)
    patch_result = _resolve_device_patch(target, backend=session.config.probe.backend)
    if probe_supports(session.services.probe, ProbeCapability.CONNECT_HINTS):
        custom_attempts = getattr(session.config.probe, "connect_attempts", [])
        hints = (
            {"attempts": connect_attempts_to_dicts(custom_attempts)}
            if custom_attempts
            else patch_result["connect_hints"]
        )
        session.services.probe.set_connect_hints(hints)
    if probe_supports(session.services.probe, ProbeCapability.PACK_PATHS):
        session.services.probe.set_pack_paths(getattr(session.config.probe, "pack_paths", []))
    if session.config.probe.backend == "probe-rs":
        result = session.services.probe.connect(
            target=match_result["matched_target"],
            unique_id=unique_id,
            wire_protocol=session.config.probe.probe_rs_wire_protocol,
            speed_khz=session.config.probe.probe_rs_speed_khz,
            core_index=session.config.probe.probe_rs_core_index,
            halt_on_connect=session.config.probe.probe_rs_halt_on_connect,
            allow_erase_all=session.config.flash.allow_erase,
        )
    else:
        result = session.services.probe.connect(target=match_result["matched_target"], unique_id=unique_id)
    if result.get("status") == "ok":
        result["target_match"] = match_result
        result["target_patch"] = patch_result
        checks = patch_result.get("post_connect_checks", {})
        if checks:
            post_connect: dict[str, object] = {"checks_requested": checks}
            if checks.get("halt"):
                post_connect["halt"] = session.services.probe.halt()
            if checks.get("read_state"):
                post_connect["state"] = session.services.probe.get_state()
            if checks.get("read_core_registers"):
                try:
                    post_connect["core_registers"] = session.services.probe.read_core_registers()
                except Exception as exc:
                    post_connect["core_registers_error"] = str(exc)
            result["post_connect"] = post_connect
        if match_result["matched_target"] != target:
            result["summary"] = (
                result["summary"]
                + f" Matched target '{target}' to '{match_result['matched_target']}'."
            )
    return result


def disconnect_probe(session: SessionState) -> dict:
    return session.services.probe.disconnect()


def halt_target(session: SessionState) -> dict:
    return session.services.probe.halt()


def resume_target(session: SessionState) -> dict:
    return session.services.probe.resume()


def reset_target(session: SessionState, halt: bool = False) -> dict:
    return session.services.probe.reset(halt=halt)
