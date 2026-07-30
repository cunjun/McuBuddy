from __future__ import annotations

import base64
import time
from typing import Any

from .base import ProbeBackend, ProbeCapability
from .sidecar_client import SidecarProtocolError, SidecarRpcClient


class ProbeRsBackend(ProbeBackend):
    """probe-rs backend served by the bundled Rust sidecar."""

    def __init__(
        self,
        sidecar_path: str | None = None,
        client: SidecarRpcClient | None = None,
    ) -> None:
        self._sidecar_path = sidecar_path
        self._client = client
        self._handshake_complete = False
        self._features: dict[str, bool] = {
            "flash": True,
            "rtt": True,
            "multi_core": True,
        }
        self._session_id: str | None = None
        self._architecture: str | None = None
        self._core_index = 0
        self._rtt_attached = False
        self._breakpoints: set[int] = set()

    @property
    def capabilities(self) -> frozenset[ProbeCapability]:
        capabilities = set(ProbeBackend.CAPABILITIES)
        if self._architecture in {"riscv", "xtensa"}:
            capabilities.discard(ProbeCapability.FAULT_REGISTERS)
        if self._features.get("flash"):
            capabilities.update({ProbeCapability.FLASH, ProbeCapability.FLASH_IMAGE})
        if self._features.get("rtt"):
            capabilities.add(ProbeCapability.RTT_READ)
        return frozenset(capabilities)

    def _rpc(self) -> Any:
        if self._client is None:
            self._client = SidecarRpcClient.start(self._sidecar_path)
        if not self._handshake_complete:
            hello = self._client.call("hello", {"client": "McuBuddy", "protocol_version": 2})
            if hello.get("protocol_version") != 2:
                raise RuntimeError("probe-rs sidecar protocol version is incompatible")
            self._features.update(
                {str(name): bool(enabled) for name, enabled in hello.get("features", {}).items()}
            )
            self._handshake_complete = True
        return self._client

    def _session_params(self, **params: Any) -> dict[str, Any]:
        if self._session_id is None:
            raise RuntimeError("Probe is not connected")
        return {"session_id": self._session_id, **params}

    def enumerate_probes(self) -> list[dict[str, Any]]:
        return list(self._rpc().call("list_probes"))

    def connect(
        self,
        target: str,
        unique_id: str | None = None,
        *,
        wire_protocol: str | None = None,
        speed_khz: int = 1000,
        core_index: int = 0,
        halt_on_connect: bool = True,
        allow_erase_all: bool = False,
    ) -> dict[str, Any]:
        result = self._rpc().call(
            "connect",
            {
                "target": target,
                "unique_id": unique_id,
                "wire_protocol": wire_protocol,
                "speed_khz": speed_khz,
                "core_index": core_index,
                "halt_on_connect": halt_on_connect,
                "allow_erase_all": allow_erase_all,
            },
        )
        self._session_id = result["session_id"]
        self._architecture = str(result.get("architecture", "unknown"))
        self._core_index = int(result.get("selected_core", core_index))
        return {
            "status": "ok",
            "summary": f"Connected to {result.get('target', target)} through probe-rs.",
            **result,
        }

    def disconnect(self) -> dict[str, Any]:
        if self._session_id is None:
            self.close()
            return {"status": "ok", "summary": "Probe was already disconnected."}
        result = self._rpc().call("disconnect", self._session_params())
        self._session_id = None
        self._architecture = None
        self._rtt_attached = False
        self._breakpoints.clear()
        self.close()
        return {"status": "ok", "summary": "Disconnected probe-rs session.", **result}

    def halt(self) -> dict[str, Any]:
        return self._status_result("halt", "Halted target.")

    def resume(self) -> dict[str, Any]:
        return self._status_result("resume", "Resumed target.")

    def reset(self, halt: bool = False) -> dict[str, Any]:
        result = self._rpc().call("reset", self._session_params(halt=halt))
        self._rtt_attached = False
        return {"status": "ok", "summary": "Reset target.", **result}

    def step(self) -> dict[str, Any]:
        return self._status_result("step", "Stepped target.")

    def _status_result(self, method: str, summary: str) -> dict[str, Any]:
        result = self._rpc().call(method, self._session_params())
        return {"status": "ok", "summary": summary, **result}

    def get_state(self) -> str:
        result = self._rpc().call("get_state", self._session_params())
        return str(result["state"])

    def continue_target(
        self,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.05,
    ) -> dict[str, Any]:
        self.resume()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            state = self.get_state()
            if state != "running":
                registers = self.read_core_registers()
                return {
                    "status": "ok",
                    "summary": "Target stopped.",
                    "state": state,
                    "stop_reason": "target_stopped",
                    "pc": hex(registers["pc"]),
                }
            time.sleep(poll_interval_seconds)
        self.halt()
        registers = self.read_core_registers()
        return {
            "status": "ok",
            "summary": "Timed out waiting for target to stop; target halted.",
            "state": "halted",
            "stop_reason": "timeout",
            "pc": hex(registers["pc"]),
        }

    def read_core_registers(self) -> dict[str, int]:
        result = self._rpc().call("read_core_registers", self._session_params())
        return {name: int(value) for name, value in result["registers"].items()}

    def read_fault_registers(self) -> dict[str, int]:
        if self._architecture in {"riscv", "xtensa"}:
            result = self._rpc().call(
                "read_exception_context",
                self._session_params(core_index=self._core_index),
            )
            return {name: int(value) for name, value in result.get("registers", {}).items()}
        registers = {
            "cfsr": 0xE000ED28,
            "hfsr": 0xE000ED2C,
            "dfsr": 0xE000ED30,
            "mmfar": 0xE000ED34,
            "bfar": 0xE000ED38,
            "afsr": 0xE000ED3C,
        }
        return {
            name: int.from_bytes(self.read_memory(address, 4), "little")
            for name, address in registers.items()
        }

    def read_memory(self, address: int, size: int) -> bytes:
        result = self._rpc().call("read_memory", self._session_params(address=address, size=size))
        data = base64.b64decode(result["data_base64"], validate=True)
        if len(data) != size:
            raise SidecarProtocolError(
                f"sidecar returned {len(data)} byte(s) for a {size}-byte read"
            )
        return data

    def write_memory(self, address: int, data: bytes) -> None:
        result = self._rpc().call(
            "write_memory",
            self._session_params(
                address=address,
                data_base64=base64.b64encode(data).decode("ascii"),
            ),
        )
        if result.get("bytes_written") != len(data):
            raise SidecarProtocolError(
                f"sidecar wrote {result.get('bytes_written')} byte(s) for a {len(data)}-byte write"
            )

    def list_cores(self) -> dict[str, Any]:
        return self._rpc().call("list_cores", self._session_params())

    def erase_flash(
        self,
        start_address: int | None = None,
        end_address: int | None = None,
        chip_erase: bool = False,
    ) -> dict[str, Any]:
        if start_address is not None or end_address is not None:
            raise ValueError("probe-rs range erase is not supported; use chip_erase=True")
        result = self._destructive_rpc(
            "erase_flash",
            self._session_params(chip_erase=chip_erase),
        )
        return {"status": "ok", "summary": "Erased target Flash.", **result}

    def program_flash(
        self,
        address: int,
        data: bytes,
        verify: bool = True,
    ) -> dict[str, Any]:
        result = self._destructive_rpc(
            "program_flash",
            self._session_params(
                address=address,
                data_base64=base64.b64encode(data).decode("ascii"),
                verify=verify,
                erase_mode="none",
                reset_after=False,
            ),
        )
        return {"status": "ok", "summary": "Programmed target Flash.", **result}

    def flash_image(
        self,
        address: int,
        data: bytes,
        erase_mode: str = "sector",
        verify: bool = True,
        reset_after: bool = True,
    ) -> dict[str, Any]:
        if erase_mode not in {"sector", "chip"}:
            raise ValueError("erase_mode must be 'sector' or 'chip'")
        result = self._destructive_rpc(
            "program_flash",
            self._session_params(
                address=address,
                data_base64=base64.b64encode(data).decode("ascii"),
                verify=verify,
                erase_mode=erase_mode,
                reset_after=reset_after,
            ),
        )
        if reset_after:
            self._rtt_attached = False
        return {"status": "ok", "summary": "Flashed target image.", **result}

    def verify_flash(self, address: int, data: bytes) -> dict[str, Any]:
        result = self._rpc().call(
            "verify_flash",
            self._session_params(
                address=address,
                data_base64=base64.b64encode(data).decode("ascii"),
            ),
        )
        return {
            "status": "ok" if result.get("verified") else "error",
            "summary": (
                "Flash verification succeeded."
                if result.get("verified")
                else "Flash verification failed."
            ),
            **result,
        }

    def flash_file(
        self,
        path: str,
        *,
        address: int | None,
        erase_mode: str = "sector",
        verify: bool = True,
        reset_after: bool = True,
    ) -> dict[str, Any]:
        result = self._destructive_rpc(
            "flash_file",
            self._session_params(
                path=path,
                address=address,
                erase_mode=erase_mode,
                verify=verify,
                reset_after=reset_after,
            ),
        )
        if reset_after:
            self._rtt_attached = False
        return {"status": "ok", "summary": "Flashed firmware file.", **result}

    def _destructive_rpc(self, method: str, params: dict[str, Any]) -> Any:
        try:
            return self._rpc().call(method, params, timeout_seconds=120)
        except SidecarProtocolError as exc:
            if self._client is not None:
                self._client.close()
            self._client = None
            self._handshake_complete = False
            self._session_id = None
            self._architecture = None
            self._rtt_attached = False
            self._breakpoints.clear()
            raise SidecarProtocolError(
                f"{exc}; Flash completion is indeterminate and the probe must be reconnected",
                code=exc.code,
                kind=exc.kind,
            ) from exc

    def attach_rtt(self, control_block_address: int | None = None) -> dict[str, Any]:
        result = self._rpc().call(
            "rtt_attach",
            self._session_params(control_block_address=control_block_address),
        )
        self._rtt_attached = True
        return result

    def detach_rtt(self) -> dict[str, Any]:
        result = self._rpc().call("rtt_detach", self._session_params())
        self._rtt_attached = False
        return result

    def list_rtt_channels(self) -> dict[str, Any]:
        return self._rpc().call("rtt_channels", self._session_params())

    def read_rtt_log(self, channel: int = 0, max_bytes: int = 4096) -> dict[str, Any]:
        if not self._rtt_attached:
            self.attach_rtt()
        result = self._rpc().call(
            "rtt_read",
            self._session_params(channel=channel, max_bytes=max_bytes),
        )
        data = base64.b64decode(result["data_base64"], validate=True)
        return {
            "status": "ok",
            "summary": f"Read {len(data)} RTT byte(s).",
            "text": data.decode("utf-8", errors="replace"),
            **result,
        }

    def write_rtt(self, data: bytes, channel: int = 0) -> dict[str, Any]:
        if not self._rtt_attached:
            self.attach_rtt()
        result = self._rpc().call(
            "rtt_write",
            self._session_params(
                channel=channel,
                data_base64=base64.b64encode(data).decode("ascii"),
            ),
        )
        bytes_written = int(result.get("bytes_written", 0))
        if bytes_written != len(data):
            raise SidecarProtocolError(
                f"RTT write was partial: wrote {bytes_written} of {len(data)} byte(s)"
            )
        return {"status": "ok", "summary": "Wrote RTT data.", **result}

    def set_breakpoint(self, address: int) -> dict[str, Any]:
        result = self._rpc().call("set_breakpoint", self._session_params(address=address))
        self._breakpoints.add(address)
        return {"status": "ok", "summary": f"Set breakpoint at {hex(address)}.", **result}

    def clear_breakpoint(self, address: int) -> dict[str, Any]:
        result = self._rpc().call("clear_breakpoint", self._session_params(address=address))
        self._breakpoints.discard(address)
        return {"status": "ok", "summary": f"Cleared breakpoint at {hex(address)}.", **result}

    def clear_all_breakpoints(self) -> dict[str, Any]:
        cleared_count = len(self._breakpoints)
        for address in list(self._breakpoints):
            self.clear_breakpoint(address)
        return {
            "status": "ok",
            "summary": "Cleared all tracked breakpoints.",
            "cleared_count": cleared_count,
        }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._handshake_complete = False
        self._session_id = None
        self._architecture = None
        self._rtt_attached = False
        self._breakpoints.clear()
