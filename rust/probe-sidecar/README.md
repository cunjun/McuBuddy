# McuBuddy probe sidecar

This Rust binary provides the `probe-rs` execution backend for McuBuddy, including ESP32
RISC-V/Xtensa targets exposed by probe-rs.
It communicates with the Python MCP server using newline-delimited JSON-RPC 2.0 over stdio.

Build it with:

```powershell
cargo build --release --manifest-path rust/probe-sidecar/Cargo.toml
```

Then configure McuBuddy with the resulting executable:

```text
configure_probe(
    backend="probe-rs",
    target="esp32c3",
    probe_rs_sidecar_path="rust/probe-sidecar/target/release/McuBuddy-probe-sidecar.exe",
    probe_rs_wire_protocol="jtag",
    probe_rs_speed_khz=5000,
    probe_rs_core_index=0,
)
```

Protocol v2 covers capability negotiation, architecture and core discovery, configurable JTAG/SWD
connections, core control, registers, architecture-specific exception context, memory, hardware
breakpoints, Flash erase/program/verify, and RTT channels. Flash authorization and memory/RTT
limits remain enforced by the Python MCP server.
