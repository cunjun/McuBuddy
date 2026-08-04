from __future__ import annotations

from typing import Literal

from ..session import SessionState
from ..tools.lifecycle import disconnect_all as _disconnect_all
from ..tools.lifecycle import finish_debug_session as _finish_debug_session
from ..tools.logs import connect_log as _connect_log
from ..tools.logs import disconnect_log as _disconnect_log
from ..tools.logs import tail_logs as _tail_logs
from ..tools.logs import uart_exchange as _uart_exchange
from ..tools.logs import uart_read_bytes as _uart_read_bytes
from ..tools.logs import uart_send as _uart_send
from ..tools.logs import uart_send_with_cleanup as _uart_send_with_cleanup


def register_io_tools(mcp, session: SessionState) -> None:
    @mcp.tool()
    async def elf_load(path: str) -> dict:
        return session.elf.load(path)

    @mcp.tool()
    async def log_connect(port: str, baudrate: int = 115200) -> dict:
        return _connect_log(session, port=port, baudrate=baudrate)

    @mcp.tool()
    async def log_disconnect() -> dict:
        return _disconnect_log(session)

    @mcp.tool()
    async def uart_send(
        data: str,
        data_format: Literal["hex", "text"],
        confirm: bool = False,
    ) -> dict:
        return _uart_send(session, data=data, data_format=data_format)

    @mcp.tool()
    async def uart_send_with_cleanup(
        data: str,
        data_format: Literal["hex", "text"],
        cleanup_data: str,
        cleanup_data_format: Literal["hex", "text"],
        confirm: bool = False,
    ) -> dict:
        """Send an actuator command and register its matching safe-stop command."""
        return _uart_send_with_cleanup(
            session,
            data=data,
            data_format=data_format,
            cleanup_data=cleanup_data,
            cleanup_data_format=cleanup_data_format,
        )

    @mcp.tool()
    async def uart_read_bytes(
        timeout_ms: int = 1000,
        max_bytes: int = 4096,
        idle_timeout_ms: int = 50,
    ) -> dict:
        return _uart_read_bytes(
            session,
            timeout_ms=timeout_ms,
            max_bytes=max_bytes,
            idle_timeout_ms=idle_timeout_ms,
        )

    @mcp.tool()
    async def uart_exchange(
        data: str,
        data_format: Literal["hex", "text"],
        timeout_ms: int = 1000,
        max_bytes: int = 4096,
        idle_timeout_ms: int = 50,
        confirm: bool = False,
    ) -> dict:
        return _uart_exchange(
            session,
            data=data,
            data_format=data_format,
            timeout_ms=timeout_ms,
            max_bytes=max_bytes,
            idle_timeout_ms=idle_timeout_ms,
        )

    @mcp.tool()
    async def log_tail(line_count: int = 50) -> dict:
        return _tail_logs(session, line_count=line_count)

    @mcp.tool()
    async def disconnect_all() -> dict:
        return _disconnect_all(session)

    @mcp.tool()
    async def finish_debug_session() -> dict:
        """Stop registered actuators, reset and run the target, then disconnect."""
        return _finish_debug_session(session)
