import asyncio

from McuBuddy.server import create_server
from McuBuddy.session import SessionState
from McuBuddy.tools.lifecycle import disconnect_all
from McuBuddy.tools.lifecycle import finish_debug_session
from McuBuddy.tools.logs import disconnect_log
from McuBuddy.tools.logs import uart_send_with_cleanup
from McuBuddy.tools.probe import disconnect_probe


class _FakeDisconnectable:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.called = False

    def disconnect(self) -> dict:
        self.called = True
        return {"status": "ok", "summary": self.summary}


def test_probe_disconnect_calls_backend() -> None:
    session = SessionState()
    session.services.probe = _FakeDisconnectable("probe disconnected")

    result = disconnect_probe(session)

    assert result["status"] == "ok"
    assert session.services.probe.called is True


def test_log_disconnect_calls_backend() -> None:
    session = SessionState()
    session.services.log = _FakeDisconnectable("log disconnected")

    result = disconnect_log(session)

    assert result["status"] == "ok"
    assert session.services.log.called is True


def test_disconnect_all_disconnects_probe_and_log() -> None:
    session = SessionState()
    session.services.probe = _FakeDisconnectable("probe disconnected")
    session.services.log = _FakeDisconnectable("log disconnected")

    result = disconnect_all(session)

    assert result["status"] == "ok"
    assert session.services.probe.called is True
    assert session.services.log.called is True
    assert "probe" in result["results"]
    assert "log" in result["results"]


class _SafeProbe(_FakeDisconnectable):
    def __init__(self, *, fail_reset: bool = False) -> None:
        super().__init__("probe disconnected")
        self.fail_reset = fail_reset
        self.actions: list[str] = []

    def clear_all_breakpoints(self) -> dict:
        self.actions.append("clear_breakpoints")
        return {"status": "ok", "summary": "breakpoints cleared"}

    def halt(self) -> dict:
        self.actions.append("halt")
        return {"status": "ok", "summary": "halted"}

    def reset(self, halt: bool = False) -> dict:
        self.actions.append(f"reset:{halt}")
        if self.fail_reset:
            raise RuntimeError("reset failed")
        return {"status": "ok", "summary": "reset"}

    def resume(self) -> dict:
        self.actions.append("resume")
        return {"status": "ok", "summary": "resumed"}

    def disconnect(self) -> dict:
        self.actions.append("disconnect")
        return super().disconnect()


class _SafeLog(_FakeDisconnectable):
    def __init__(self, *, fail_payload: bytes | None = None) -> None:
        super().__init__("log disconnected")
        self.fail_payload = fail_payload
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        if data == self.fail_payload:
            raise RuntimeError("stop failed")
        return len(data)


def test_finish_debug_session_stops_actuators_then_resets_runs_and_disconnects() -> None:
    session = SessionState()
    session.services.probe = _SafeProbe()
    session.services.log = _SafeLog()

    uart_send_with_cleanup(
        session,
        data="a1 01",
        data_format="hex",
        cleanup_data="a1 00",
        cleanup_data_format="hex",
    )
    result = finish_debug_session(session)

    assert result["status"] == "ok"
    assert session.services.log.writes == [b"\xa1\x01", b"\xa1\x00"]
    assert session.services.probe.actions == [
        "clear_breakpoints",
        "reset:True",
        "resume",
        "disconnect",
    ]


def test_finish_debug_session_continues_after_cleanup_and_reset_failures() -> None:
    session = SessionState()
    session.services.probe = _SafeProbe(fail_reset=True)
    session.services.log = _SafeLog(fail_payload=b"stop")
    uart_send_with_cleanup(
        session,
        data="start",
        data_format="text",
        cleanup_data="stop",
        cleanup_data_format="text",
    )

    result = finish_debug_session(session)

    assert result["status"] == "partial"
    assert set(result["errors"]) == {"actuator_cleanup_1", "probe_reset_halt"}
    assert "resume" not in session.services.probe.actions
    assert "disconnect" in session.services.probe.actions
    assert session.services.log.called is True
    assert session.lifecycle.pending_uart_cleanup == [b"stop"]


def test_finish_debug_session_retries_only_failed_steps() -> None:
    session = SessionState()
    session.services.probe = _SafeProbe(fail_reset=True)
    session.services.log = _SafeLog(fail_payload=b"stop")
    uart_send_with_cleanup(
        session,
        data="start",
        data_format="text",
        cleanup_data="stop",
        cleanup_data_format="text",
    )

    first = finish_debug_session(session)
    session.services.probe.fail_reset = False
    session.services.log.fail_payload = None
    second = finish_debug_session(session)

    assert first["status"] == "partial"
    assert second["status"] == "ok"
    assert second["already_finished"] is False
    assert session.services.log.writes == [b"start", b"stop", b"stop"]
    assert session.services.probe.actions.count("clear_breakpoints") == 1
    assert session.services.probe.actions.count("reset:True") == 2
    assert session.services.probe.actions.count("resume") == 1
    assert session.services.probe.actions.count("disconnect") == 1


def test_finish_debug_session_is_idempotent() -> None:
    session = SessionState()
    session.services.probe = _SafeProbe()
    session.services.log = _SafeLog()

    first = finish_debug_session(session)
    second = finish_debug_session(session)

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert second["already_finished"] is True
    assert session.services.probe.actions.count("reset:True") == 1


def test_failed_actuator_start_is_not_registered_for_cleanup() -> None:
    session = SessionState()
    session.services.log = _SafeLog(fail_payload=b"start")

    try:
        uart_send_with_cleanup(
            session,
            data="start",
            data_format="text",
            cleanup_data="stop",
            cleanup_data_format="text",
        )
    except RuntimeError:
        pass

    assert session.lifecycle.pending_uart_cleanup == []


def test_logs_toolset_exposes_safe_uart_and_finish_tools() -> None:
    app = create_server(SessionState(), toolsets=["logs"])

    assert app._tool_manager.get_tool("uart_send_with_cleanup") is not None
    assert app._tool_manager.get_tool("finish_debug_session") is not None


def test_server_lifespan_finishes_debug_session_on_shutdown() -> None:
    session = SessionState()
    session.services.probe = _SafeProbe()
    session.services.log = _SafeLog()
    app = create_server(session, toolsets=["probe"])

    async def run_lifespan() -> None:
        async with app._mcp_server.lifespan(app._mcp_server):
            assert session.lifecycle.finish_result is None

    asyncio.run(run_lifespan())

    assert session.lifecycle.finish_result is not None
    assert session.services.probe.actions == [
        "clear_breakpoints",
        "reset:True",
        "resume",
        "disconnect",
    ]


def test_new_execution_change_reopens_a_finished_debug_session() -> None:
    session = SessionState()
    session.services.probe = _SafeProbe()
    session.services.log = _SafeLog()
    app = create_server(session, toolsets=["probe"])

    async def scenario() -> dict:
        await app._tool_manager.get_tool("finish_debug_session").run({})
        await app._tool_manager.get_tool("probe_halt").run({})
        return await app._tool_manager.get_tool("finish_debug_session").run({})

    result = asyncio.run(scenario())

    assert result["already_finished"] is False
    assert session.services.probe.actions.count("reset:True") == 2
