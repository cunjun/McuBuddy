from McuBuddy.session import SessionState
from McuBuddy.tools.configuration import get_runtime_config


def test_runtime_config_explains_how_to_enable_probe_debug_tools() -> None:
    session = SessionState()

    result = get_runtime_config(session)

    assert result["tool_surface"]["default_tool_count"] == 19
    assert result["tool_surface"]["selected_toolsets"] == []
    assert result["tool_surface"]["restart_required"] is True
    assert "MCUBUDDY_TOOLSETS=probe" in result["tool_surface"]["debug_tool_hint"]


def test_runtime_config_reports_selected_probe_toolset_without_enable_hint() -> None:
    session = SessionState()
    session.config.server.toolsets = ["probe"]

    result = get_runtime_config(session)

    assert result["tool_surface"]["selected_toolsets"] == ["probe"]
    assert result["tool_surface"]["probe_debug_tools_enabled"] is True
