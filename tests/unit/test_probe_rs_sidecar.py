from __future__ import annotations

import base64
import json
from collections import deque

import pytest

import McuBuddy.tools.configuration as configuration
from McuBuddy.backends.probe.base import ProbeCapability
from McuBuddy.backends.probe.probe_rs_backend import ProbeRsBackend
from McuBuddy.backends.probe.sidecar_client import SidecarProtocolError, SidecarRpcClient
from McuBuddy.session import create_probe_backend
from McuBuddy.session import SessionState
from McuBuddy.tools.configuration import configure_probe
from McuBuddy.tools.probe import connect_probe


class _MemoryTransport:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = deque(json.dumps(item) for item in responses)
        self.requests: list[dict] = []
        self.read_timeouts: list[float | None] = []
        self.closed = False

    def write_line(self, line: str) -> None:
        self.requests.append(json.loads(line))

    def read_line(self, timeout_seconds: float | None = None) -> str:
        self.read_timeouts.append(timeout_seconds)
        return self.responses.popleft()

    def close(self) -> None:
        self.closed = True


def test_rpc_client_sends_versioned_request_and_returns_result() -> None:
    transport = _MemoryTransport([{"jsonrpc": "2.0", "id": 1, "result": {"protocol_version": 1}}])
    client = SidecarRpcClient(transport)

    result = client.call("hello", {"client": "McuBuddy"})

    assert result == {"protocol_version": 1}
    assert transport.requests == [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "hello",
            "params": {"client": "McuBuddy"},
        }
    ]


def test_rpc_client_applies_a_bounded_response_timeout() -> None:
    transport = _MemoryTransport([{"jsonrpc": "2.0", "id": 1, "result": {}}])
    client = SidecarRpcClient(transport, response_timeout_seconds=0.25)

    client.call("hello")

    assert transport.read_timeouts == [0.25]


def test_rpc_client_allows_a_longer_timeout_for_flash_operations() -> None:
    transport = _MemoryTransport([{"jsonrpc": "2.0", "id": 1, "result": {}}])
    client = SidecarRpcClient(transport, response_timeout_seconds=0.25)

    client.call("program_flash", timeout_seconds=120)

    assert transport.read_timeouts == [120]


def test_rpc_client_rejects_mismatched_response_id() -> None:
    client = SidecarRpcClient(_MemoryTransport([{"jsonrpc": "2.0", "id": 99, "result": {}}]))

    with pytest.raises(SidecarProtocolError, match="response id"):
        client.call("hello")


def test_rpc_client_rejects_non_object_json_response() -> None:
    client = SidecarRpcClient(_MemoryTransport([]))
    client._transport.responses.append("[]")

    with pytest.raises(SidecarProtocolError, match="JSON object"):
        client.call("hello")


def test_rpc_client_surfaces_sidecar_error() -> None:
    client = SidecarRpcClient(
        _MemoryTransport(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {
                        "code": -32000,
                        "message": "probe busy",
                        "data": {"kind": "probe_busy"},
                    },
                }
            ]
        )
    )

    with pytest.raises(SidecarProtocolError, match="probe busy") as captured:
        client.call("connect", {"target": "STM32F103C8"})

    assert captured.value.code == -32000
    assert captured.value.kind == "probe_busy"


class _FakeClient:
    def __init__(self, results: dict[str, dict | list]) -> None:
        self.results = results
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def call(
        self,
        method: str,
        params: dict | None = None,
        *,
        timeout_seconds: float | None = None,
    ):
        self.calls.append((method, params or {}))
        return self.results[method]

    def close(self) -> None:
        self.closed = True


def test_probe_rs_backend_declares_minimal_sidecar_capabilities() -> None:
    backend = ProbeRsBackend(
        client=_FakeClient(
            {
                "hello": {
                    "protocol_version": 2,
                    "features": {
                        "flash": True,
                        "rtt": True,
                        "multi_core": True,
                    },
                }
            }
        )
    )

    assert ProbeCapability.CORE_CONTROL in backend.capabilities
    assert ProbeCapability.CORE_REGISTERS in backend.capabilities
    assert ProbeCapability.MEMORY_READ in backend.capabilities
    assert ProbeCapability.MEMORY_WRITE in backend.capabilities
    assert ProbeCapability.BREAKPOINTS in backend.capabilities
    assert ProbeCapability.FLASH in backend.capabilities
    assert ProbeCapability.FLASH_IMAGE in backend.capabilities
    assert ProbeCapability.RTT_READ in backend.capabilities


def test_probe_rs_backend_connects_and_tracks_session() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "sidecar_version": "0.2.0", "features": {}},
            "connect": {
                "session_id": "session-1",
                "target": "ESP32-C3",
                "architecture": "riscv",
                "core_count": 1,
                "selected_core": 0,
            },
        }
    )
    backend = ProbeRsBackend(client=client)

    result = backend.connect(
        "ESP32-C3",
        unique_id="probe-7",
        wire_protocol="jtag",
        speed_khz=5000,
        core_index=0,
        allow_erase_all=True,
    )

    assert result["status"] == "ok"
    assert result["session_id"] == "session-1"
    assert client.calls == [
        ("hello", {"client": "McuBuddy", "protocol_version": 2}),
        (
            "connect",
            {
                "target": "ESP32-C3",
                "unique_id": "probe-7",
                "wire_protocol": "jtag",
                "speed_khz": 5000,
                "core_index": 0,
                "halt_on_connect": True,
                "allow_erase_all": True,
            },
        ),
    ]


def test_riscv_exception_context_uses_selected_core_and_disables_cortex_fault_capability() -> None:
    client = _FakeClient(
        {
            "hello": {
                "protocol_version": 2,
                "features": {"flash": False, "rtt": False},
            },
            "connect": {
                "session_id": "session-1",
                "target": "esp32c3",
                "architecture": "riscv",
                "selected_core": 1,
            },
            "read_exception_context": {
                "architecture": "riscv",
                "registers": {"mcause": 2, "mepc": 0x42000000},
            },
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("esp32c3", core_index=1)

    context = backend.read_fault_registers()

    assert context == {"mcause": 2, "mepc": 0x42000000}
    assert ProbeCapability.FAULT_REGISTERS not in backend.capabilities
    assert ProbeCapability.FLASH not in backend.capabilities
    assert ProbeCapability.RTT_READ not in backend.capabilities
    assert client.calls[-1] == (
        "read_exception_context",
        {"session_id": "session-1", "core_index": 1},
    )


def test_probe_rs_backend_encodes_and_decodes_memory() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {}},
            "connect": {"session_id": "session-1", "target": "chip"},
            "read_memory": {"data_base64": base64.b64encode(b"\x01\x02").decode()},
            "write_memory": {"bytes_written": 2},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    assert backend.read_memory(0x20000000, 2) == b"\x01\x02"
    backend.write_memory(0x20000000, b"\xaa\x55")

    assert client.calls[-1] == (
        "write_memory",
        {
            "session_id": "session-1",
            "address": 0x20000000,
            "data_base64": "qlU=",
        },
    )


def test_probe_rs_backend_routes_flash_and_rtt_through_sidecar() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {"flash": True, "rtt": True}},
            "connect": {
                "session_id": "session-1",
                "target": "ESP32-C3",
                "architecture": "riscv",
            },
            "program_flash": {
                "bytes_programmed": 2,
                "verified": True,
                "reset": True,
            },
            "flash_file": {"format": "elf", "verified": True, "reset": True},
            "rtt_attach": {"attached": True, "up_channels": 1, "down_channels": 1},
            "rtt_read": {
                "data_base64": base64.b64encode(b"ready\n").decode(),
                "bytes_read": 6,
            },
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("ESP32-C3", wire_protocol="jtag")

    flash = backend.flash_image(
        0x42000000,
        b"\xaa\x55",
        erase_mode="chip",
        verify=True,
        reset_after=True,
    )
    rtt = backend.read_rtt_log(channel=0, max_bytes=64)

    assert flash["bytes_programmed"] == 2
    assert rtt["text"] == "ready\n"
    assert (
        "program_flash",
        {
            "session_id": "session-1",
            "address": 0x42000000,
            "data_base64": "qlU=",
            "verify": True,
            "erase_mode": "chip",
            "reset_after": True,
        },
    ) in client.calls
    assert (
        "rtt_attach",
        {
            "session_id": "session-1",
            "control_block_address": None,
        },
    ) in client.calls

    file_result = backend.flash_file(
        "firmware.elf",
        address=None,
        erase_mode="sector",
        verify=True,
        reset_after=True,
    )
    assert file_result["format"] == "elf"


def test_probe_rs_backend_rejects_partial_rtt_write() -> None:
    client = _FakeClient(
        {
            "hello": {
                "protocol_version": 2,
                "features": {"flash": False, "rtt": True},
            },
            "connect": {"session_id": "session-1", "target": "esp32c3"},
            "rtt_attach": {"attached": True, "up_channels": 1, "down_channels": 1},
            "rtt_write": {"bytes_written": 1},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("esp32c3")

    with pytest.raises(SidecarProtocolError, match="partial"):
        backend.write_rtt(b"abc")


def test_flash_timeout_invalidates_sidecar_session_as_indeterminate() -> None:
    class _TimeoutClient(_FakeClient):
        def call(self, method, params=None, *, timeout_seconds=None):
            if method == "program_flash":
                raise SidecarProtocolError("sidecar response timed out after 120 seconds")
            return super().call(method, params, timeout_seconds=timeout_seconds)

    client = _TimeoutClient(
        {
            "hello": {"protocol_version": 2, "features": {"flash": True}},
            "connect": {"session_id": "session-1", "target": "esp32c3"},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("esp32c3")

    with pytest.raises(SidecarProtocolError, match="indeterminate"):
        backend.flash_image(0, b"\xaa", erase_mode="chip")

    assert backend._session_id is None
    assert backend._client is None


def test_probe_rs_backend_rejects_short_memory_response() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {}},
            "connect": {"session_id": "session-1", "target": "chip"},
            "read_memory": {"data_base64": base64.b64encode(b"\x01").decode()},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    with pytest.raises(SidecarProtocolError, match="returned 1 byte"):
        backend.read_memory(0x20000000, 2)


def test_probe_rs_backend_rejects_partial_memory_write() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {}},
            "connect": {"session_id": "session-1", "target": "chip"},
            "write_memory": {"bytes_written": 1},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    with pytest.raises(SidecarProtocolError, match="wrote 1 byte"):
        backend.write_memory(0x20000000, b"\xaa\x55")


def test_probe_rs_backend_clears_every_tracked_breakpoint() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {}},
            "connect": {"session_id": "session-1", "target": "chip"},
            "set_breakpoint": {},
            "clear_breakpoint": {},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")
    backend.set_breakpoint(0x08000100)
    backend.set_breakpoint(0x08000200)

    result = backend.clear_all_breakpoints()

    assert result["cleared_count"] == 2
    assert [call for call in client.calls if call[0] == "clear_breakpoint"] == [
        ("clear_breakpoint", {"session_id": "session-1", "address": 0x08000100}),
        ("clear_breakpoint", {"session_id": "session-1", "address": 0x08000200}),
    ]


def test_probe_rs_continue_timeout_halts_target_and_reports_context() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {}},
            "connect": {"session_id": "session-1", "target": "chip"},
            "resume": {},
            "halt": {},
            "read_core_registers": {"registers": {"pc": 0x08001234}},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    result = backend.continue_target(timeout_seconds=0)

    assert result == {
        "status": "ok",
        "summary": "Timed out waiting for target to stop; target halted.",
        "state": "halted",
        "stop_reason": "timeout",
        "pc": "0x8001234",
    }
    assert ("halt", {"session_id": "session-1"}) in client.calls


def test_probe_rs_backend_disconnect_closes_sidecar_process() -> None:
    client = _FakeClient(
        {
            "hello": {"protocol_version": 2, "features": {}},
            "connect": {"session_id": "session-1", "target": "chip"},
            "disconnect": {"session_id": "session-1"},
        }
    )
    backend = ProbeRsBackend(client=client)
    backend.connect("chip")

    result = backend.disconnect()

    assert result["status"] == "ok"
    assert client.closed is True


def test_backend_factory_accepts_probe_rs_alias() -> None:
    backend = create_probe_backend("probe-rs")

    assert isinstance(backend, ProbeRsBackend)


def test_connect_probe_forwards_probe_rs_connection_and_erase_policy() -> None:
    class _RecordingProbe:
        capabilities = frozenset()

        def __init__(self) -> None:
            self.kwargs: dict = {}

        def connect(self, **kwargs):
            self.kwargs = kwargs
            return {"status": "ok", "summary": "connected"}

    session = SessionState()
    probe = _RecordingProbe()
    session.services.probe = probe
    session.config.probe.backend = "probe-rs"
    session.config.probe.probe_rs_wire_protocol = "jtag"
    session.config.probe.probe_rs_speed_khz = 5000
    session.config.probe.probe_rs_core_index = 1
    session.config.probe.probe_rs_halt_on_connect = False
    session.config.flash.allow_erase = True

    result = connect_probe(session, "ESP32-S3", unique_id="usb-jtag")

    assert result["status"] == "ok"
    assert probe.kwargs == {
        "target": "esp32s3",
        "unique_id": "usb-jtag",
        "wire_protocol": "jtag",
        "speed_khz": 5000,
        "core_index": 1,
        "halt_on_connect": False,
        "allow_erase_all": True,
    }


def test_configure_probe_records_probe_rs_sidecar_path() -> None:
    session = SessionState()

    result = configure_probe(
        session,
        backend="probe-rs",
        probe_rs_sidecar_path=r"E:\tools\McuBuddy-probe-sidecar.exe",
    )

    assert result["status"] == "ok"
    assert session.config.probe.backend == "probe-rs"
    assert session.config.probe.probe_rs_sidecar_path.endswith("McuBuddy-probe-sidecar.exe")
    assert isinstance(session.services.probe, ProbeRsBackend)


def test_configure_probe_disconnects_old_backend_before_switch(monkeypatch) -> None:
    class _Backend:
        def __init__(self) -> None:
            self.disconnected = False

        def disconnect(self) -> dict:
            self.disconnected = True
            return {"status": "ok"}

    session = SessionState()
    old_backend = _Backend()
    new_backend = _Backend()
    session.services.probe = old_backend
    monkeypatch.setattr(configuration, "create_probe_backend", lambda *args, **kwargs: new_backend)

    result = configure_probe(session, backend="probe-rs")

    assert result["status"] == "ok"
    assert old_backend.disconnected is True
    assert session.services.probe is new_backend
