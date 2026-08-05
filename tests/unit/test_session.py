import pytest

from McuBuddy.session import DebugArtifacts
from McuBuddy.session import SessionLifecycle
from McuBuddy.session import SessionServices
from McuBuddy.session import SessionState


def test_session_state_groups_mutable_responsibilities() -> None:
    session = SessionState()

    assert isinstance(session.services, SessionServices)
    assert isinstance(session.artifacts, DebugArtifacts)
    assert isinstance(session.lifecycle, SessionLifecycle)
    assert session.artifacts.memory_snapshots == {}
    assert session.artifacts.conditional_breakpoints == {}
    assert session.lifecycle.pending_uart_cleanup == []
    assert session.lifecycle.completed_cleanup_steps == set()
    assert session.lifecycle.finish_result is None


@pytest.mark.parametrize(
    "removed_field",
    [
        "probe",
        "log",
        "elf",
        "svd",
        "build",
        "gdb_server",
        "memory_snapshots",
        "conditional_breakpoints",
        "pending_uart_cleanup",
        "debug_session_finish_result",
    ],
)
def test_session_state_removes_flat_service_locator_fields(removed_field: str) -> None:
    session = SessionState()

    with pytest.raises(AttributeError):
        getattr(session, removed_field)
