from __future__ import annotations

from dataclasses import dataclass, field

from ..session import SessionServices
from ..session import SessionState

from .mock_backends import MockProbeBackend
from .mock_elf import MockElfManager
from .mock_logs import MockLogBackend


@dataclass
class MockSessionState(SessionState):
    services: SessionServices = field(
        default_factory=lambda: SessionServices(
            probe=MockProbeBackend(),
            log=MockLogBackend(),
            elf=MockElfManager(),
        )
    )
