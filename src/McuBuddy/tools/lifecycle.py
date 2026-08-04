from __future__ import annotations

from ..session import SessionState


def finish_debug_session(session: SessionState) -> dict:
    if session.debug_session_finish_result is not None:
        return {**session.debug_session_finish_result, "already_finished": True}

    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    def run(name: str, action) -> None:
        try:
            result = action()
            results[name] = result
            if isinstance(result, dict) and result.get("status") == "error":
                errors[name] = result.get("summary", "operation reported an error")
        except Exception as exc:
            errors[name] = str(exc)

    cleanup_payloads = list(reversed(session.pending_uart_cleanup))
    session.pending_uart_cleanup.clear()
    for index, payload in enumerate(cleanup_payloads, start=1):
        run(
            f"actuator_cleanup_{index}",
            lambda payload=payload: {
                "status": "ok",
                "summary": f"Sent {session.log.write(payload)} actuator cleanup byte(s).",
                "payload_hex": payload.hex(" "),
            },
        )

    run("clear_breakpoints", session.probe.clear_all_breakpoints)
    if hasattr(session, "conditional_breakpoints"):
        session.conditional_breakpoints.clear()
    run("probe_reset_halt", lambda: session.probe.reset(halt=True))
    run("probe_resume", session.probe.resume)
    run("probe_disconnect", session.probe.disconnect)
    run("log_disconnect", session.log.disconnect)
    gdb_server = getattr(session, "gdb_server", None)
    if gdb_server is not None and hasattr(gdb_server, "stop"):
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
    session.debug_session_finish_result = result
    return result


def disconnect_all(session: SessionState) -> dict:
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    actions: dict[str, object] = {
        "probe": session.probe.disconnect,
        "log": session.log.disconnect,
    }
    gdb_server = getattr(session, "gdb_server", None)
    if gdb_server is not None and hasattr(gdb_server, "stop"):
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
