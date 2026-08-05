from __future__ import annotations

from ...mcp_execution import SessionToolRegistrar
from ...mcp_execution import require_session_tool_registrar
from ...session import SessionState
from .control import register_probe_control_tools
from .memory import register_probe_memory_tools
from .rtos import register_probe_rtos_tools
from .source import register_probe_source_tools
from .symbols import register_probe_symbol_tools
from .trace import register_probe_trace_tools
from .watch import register_probe_watch_tools


def register_probe_tools(registrar: SessionToolRegistrar, session: SessionState) -> None:
    require_session_tool_registrar(registrar)
    register_probe_control_tools(registrar, session)
    register_probe_source_tools(registrar, session)
    register_probe_memory_tools(registrar, session)
    register_probe_trace_tools(registrar, session)
    register_probe_rtos_tools(registrar, session)
    register_probe_symbol_tools(registrar, session)
    register_probe_watch_tools(registrar, session)
