from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .mcp_tools import register_all_tools
from .session import SessionState
from .tools.lifecycle import finish_debug_session
from .tool_profiles import ToolProfile, resolve_tool_profile


def create_server(
    session: SessionState | None = None,
    *,
    tool_profile: str | ToolProfile | None = None,
    toolsets: list[str] | tuple[str, ...] | frozenset[str] | None = None,
) -> FastMCP:
    profile = (
        tool_profile
        if isinstance(tool_profile, ToolProfile)
        else resolve_tool_profile(tool_profile, toolsets=toolsets)
    )
    active_session = session or SessionState()

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield {}
        finally:
            async with active_session.execution_lock:
                await asyncio.to_thread(finish_debug_session, active_session)

    app = FastMCP("McuBuddy", lifespan=lifespan)
    register_all_tools(app, active_session, tool_profile=profile)
    return app


mcp = create_server()


def main() -> None:
    from .cli import main as cli_main

    raise SystemExit(cli_main())
