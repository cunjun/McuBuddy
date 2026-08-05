import pytest

from McuBuddy.mcp_tools.build_debug import register_build_debug_tools
from McuBuddy.mcp_tools.diagnostics import register_diagnostic_tools
from McuBuddy.mcp_tools.evidence import register_evidence_tools
from McuBuddy.mcp_tools.io import register_io_tools
from McuBuddy.mcp_tools.probe import register_probe_tools
from McuBuddy.mcp_tools.probe.control import register_probe_control_tools
from McuBuddy.mcp_tools.probe.memory import register_probe_memory_tools
from McuBuddy.mcp_tools.probe.rtos import register_probe_rtos_tools
from McuBuddy.mcp_tools.probe.source import register_probe_source_tools
from McuBuddy.mcp_tools.probe.symbols import register_probe_symbol_tools
from McuBuddy.mcp_tools.probe.trace import register_probe_trace_tools
from McuBuddy.mcp_tools.probe.watch import register_probe_watch_tools
from McuBuddy.mcp_tools.runtime import register_runtime_tools
from McuBuddy.mcp_tools.svd import register_svd_tools
from McuBuddy.session import SessionState


class _RawMcpLikeRegistrar:
    def tool(self, *_args, **_kwargs):
        return lambda callback: callback


@pytest.mark.parametrize(
    "register_group",
    [
        register_build_debug_tools,
        register_diagnostic_tools,
        register_evidence_tools,
        register_io_tools,
        register_probe_tools,
        register_probe_control_tools,
        register_probe_memory_tools,
        register_probe_rtos_tools,
        register_probe_source_tools,
        register_probe_symbol_tools,
        register_probe_trace_tools,
        register_probe_watch_tools,
        register_runtime_tools,
        register_svd_tools,
    ],
)
def test_registration_groups_reject_raw_mcp_objects(register_group) -> None:
    with pytest.raises(TypeError, match="SessionToolRegistrar"):
        register_group(_RawMcpLikeRegistrar(), SessionState())
