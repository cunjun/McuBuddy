from types import SimpleNamespace

from McuBuddy.tools.probe import run_to_function, run_to_source


class _Elf:
    is_loaded = True

    def resolve_symbol(self, name):
        return {"address": "0x08001235" if name == "target" else None}

    def source_to_addrs(self, file, line):
        return [0x08001234]

    def addr_to_source(self, address):
        return {"file": "other.c", "line": 9}

    def resolve_address(self, address):
        return {"symbol": "other", "source": "other.c:9"}


class _Probe:
    def __init__(self, result):
        self.result = result
        self._breakpoints = set()

    @property
    def breakpoint_addresses(self):
        return frozenset(self._breakpoints)

    def set_breakpoint(self, address):
        self._breakpoints.add(address)
        return {"status": "ok"}

    def clear_breakpoint(self, address):
        self._breakpoints.discard(address)
        return {"status": "ok"}

    def continue_target(self, **kwargs):
        return dict(self.result)


def _session(result):
    return SimpleNamespace(services=SimpleNamespace(probe=_Probe(result), elf=_Elf()))


def test_run_to_function_reports_timeout_without_claiming_target_was_reached():
    result = run_to_function(
        _session({"status": "ok", "stop_reason": "timeout", "pc": "0x08009998"}),
        "target",
    )

    assert result["status"] == "timeout"
    assert result["target_reached"] is False
    assert "did not reach" in result["summary"].lower()


def test_run_to_source_reports_other_stop_without_claiming_target_was_reached():
    result = run_to_source(
        _session({"status": "ok", "stop_reason": "breakpoint_hit", "pc": "0x08009998"}),
        "main.c",
        42,
    )

    assert result["status"] == "stopped"
    assert result["target_reached"] is False
    assert "stopped before reaching" in result["summary"]
