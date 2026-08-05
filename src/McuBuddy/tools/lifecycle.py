from __future__ import annotations

from ..session import SessionState


def finish_debug_session(session: SessionState) -> dict:
    lifecycle = session.lifecycle
    if lifecycle.finish_result is not None and lifecycle.finish_result["status"] == "ok":
        return {**session.lifecycle.finish_result, "already_finished": True}

    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    def run(name: str, action, *, remember: bool = True) -> bool:
        if remember and name in lifecycle.completed_cleanup_steps:
            return True
        try:
            result = action()
            results[name] = result
            if isinstance(result, dict) and result.get("status") == "error":
                errors[name] = result.get("summary", "operation reported an error")
                return False
        except Exception as exc:
            errors[name] = str(exc)
            return False
        if remember:
            lifecycle.completed_cleanup_steps.add(name)
        return True

    cleanup_payloads = list(reversed(lifecycle.pending_uart_cleanup))
    for index, payload in enumerate(cleanup_payloads, start=1):
        if run(
            f"actuator_cleanup_{index}",
            lambda payload=payload: {
                "status": "ok",
                "summary": f"Sent {session.services.log.write(payload)} actuator cleanup byte(s).",
                "payload_hex": payload.hex(" "),
            },
            remember=False,
        ):
            lifecycle.pending_uart_cleanup.remove(payload)

    if run("clear_breakpoints", session.services.probe.clear_all_breakpoints):
        session.artifacts.conditional_breakpoints.clear()
    reset_ok = run("probe_reset_halt", lambda: session.services.probe.reset(halt=True))
    if reset_ok:
        run("probe_resume", session.services.probe.resume)
    run("probe_disconnect", session.services.probe.disconnect)
    run("log_disconnect", session.services.log.disconnect)
    gdb_server = session.services.gdb_server
    if hasattr(gdb_server, "stop"):
        run("gdb_server_stop", gdb_server.stop)

    result = {
        "status": "ok" if not errors else "partial",
        "summary": (
            "Finished the debug session in the safe reset-and-run state."
            if not errors
            else "Finished debug-session cleanup, but some final states could not be confirmed."
        ),
        "already_finished": False,
        "results": results,
        "errors": errors,
    }
    lifecycle.finish_result = result
    return result


def disconnect_all(session: SessionState) -> dict:
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    actions: dict[str, object] = {
        "probe": session.services.probe.disconnect,
        "log": session.services.log.disconnect,
    }
    gdb_server = session.services.gdb_server
    if hasattr(gdb_server, "stop"):
        actions["gdb_server"] = gdb_server.stop

    for name, action in actions.items():
        try:
            results[name] = action()
        except Exception as exc:
            errors[name] = str(exc)

    return {
        "status": "ok" if not errors else "partial",
        "summary": (
            "Disconnected all active hardware resources."
            if not errors
            else "Disconnected available resources, but some disconnect operations failed."
        ),
        "results": results,
        "errors": errors,
    }
