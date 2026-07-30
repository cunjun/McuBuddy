use std::collections::BTreeMap;
use std::path::Path;
use std::time::Duration;

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use probe_rs::flashing::{BinOptions, DownloadOptions, ElfOptions, FlashProgress, Format};
use probe_rs::probe::list::Lister;
use probe_rs::probe::WireProtocol;
use probe_rs::rtt::{Rtt, ScanRegion};
use probe_rs::{CoreStatus, MemoryInterface, Permissions, RegisterId, RegisterValue, Session};
use serde::Deserialize;
use serde_json::{json, Value};
use uuid::Uuid;

pub const PROTOCOL_VERSION: u64 = 2;
const MAX_READ_BYTES: usize = 1024 * 1024;
const MAX_WRITE_BYTES: usize = 64 * 1024;

#[derive(Default)]
pub struct SidecarState {
    session: Option<ActiveSession>,
}

struct ActiveSession {
    id: String,
    target: String,
    session: Session,
    core_index: usize,
    architecture: String,
    rtt: Option<Rtt>,
}

#[derive(Deserialize)]
struct Request {
    jsonrpc: String,
    id: Value,
    method: String,
    #[serde(default)]
    params: Value,
}

pub fn handle_request_line(state: &mut SidecarState, line: &str) -> String {
    let request = match serde_json::from_str::<Request>(line) {
        Ok(request) => request,
        Err(error) => {
            return error_response(Value::Null, -32700, &format!("invalid JSON: {error}"));
        }
    };
    let id = request.id.clone();
    if request.jsonrpc != "2.0" {
        return error_response(id, -32600, "jsonrpc must be '2.0'");
    }
    match dispatch(state, &request.method, &request.params) {
        Ok(result) => json!({"jsonrpc": "2.0", "id": id, "result": result}).to_string(),
        Err(RpcFailure::MethodNotFound(message)) => error_response(id, -32601, &message),
        Err(RpcFailure::InvalidParams(message)) => error_response(id, -32602, &message),
        Err(RpcFailure::Operation(message)) => error_response(id, -32000, &message),
    }
}

enum RpcFailure {
    MethodNotFound(String),
    InvalidParams(String),
    Operation(String),
}

fn error_response(id: Value, code: i64, message: &str) -> String {
    let kind = match code {
        -32700 => "invalid_json",
        -32600 => "invalid_request",
        -32601 => "method_not_found",
        -32602 => "invalid_params",
        _ => classify_operation_error(message),
    };
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "error": {"code": code, "message": message, "data": {"kind": kind}}
    })
    .to_string()
}

fn dispatch(state: &mut SidecarState, method: &str, params: &Value) -> Result<Value, RpcFailure> {
    match method {
        "hello" => hello(params),
        "list_probes" => list_probes(),
        "connect" => connect(state, params),
        "disconnect" => disconnect(state, params),
        "halt" => with_core(state, params, |core| {
            core.halt(Duration::from_secs(1)).map_err(operation_error)?;
            Ok(json!({"state": "halted"}))
        }),
        "resume" => with_core(state, params, |core| {
            core.run().map_err(operation_error)?;
            Ok(json!({"state": "running"}))
        }),
        "reset" => reset(state, params),
        "step" => with_core(state, params, |core| {
            core.step().map_err(operation_error)?;
            Ok(json!({"state": "halted"}))
        }),
        "get_state" => with_core(state, params, |core| {
            let status = core.status().map_err(operation_error)?;
            Ok(json!({"state": status_name(status)}))
        }),
        "read_core_registers" => read_core_registers(state, params),
        "list_cores" => list_cores(state, params),
        "read_exception_context" => read_exception_context(state, params),
        "read_memory" => read_memory(state, params),
        "write_memory" => write_memory(state, params),
        "set_breakpoint" => breakpoint(state, params, true),
        "clear_breakpoint" => breakpoint(state, params, false),
        "erase_flash" => erase_flash(state, params),
        "program_flash" => program_flash(state, params),
        "flash_file" => flash_file(state, params),
        "verify_flash" => verify_flash(state, params),
        "rtt_attach" => rtt_attach(state, params),
        "rtt_detach" => rtt_detach(state, params),
        "rtt_channels" => rtt_channels(state, params),
        "rtt_read" => rtt_read(state, params),
        "rtt_write" => rtt_write(state, params),
        _ => Err(RpcFailure::MethodNotFound(format!(
            "unknown method '{method}'"
        ))),
    }
}

fn hello(params: &Value) -> Result<Value, RpcFailure> {
    let requested = optional_u64(params, "protocol_version")?.unwrap_or(PROTOCOL_VERSION);
    if requested != PROTOCOL_VERSION {
        return Err(RpcFailure::Operation(format!(
            "unsupported protocol version {requested}"
        )));
    }
    Ok(json!({
        "protocol_version": PROTOCOL_VERSION,
        "sidecar_version": env!("CARGO_PKG_VERSION"),
        "probe_rs_version": "0.31",
        "features": {
            "architecture_detection": true,
            "flash": true,
            "rtt": true,
            "multi_core": true,
            "structured_errors": true
        },
        "limits": {
            "max_read_bytes": MAX_READ_BYTES,
            "max_write_bytes": MAX_WRITE_BYTES
        }
    }))
}

fn list_probes() -> Result<Value, RpcFailure> {
    let probes = Lister::new()
        .list_all()
        .into_iter()
        .map(|probe| {
            json!({
                "unique_id": probe.serial_number,
                "description": probe.identifier,
                "vendor_id": probe.vendor_id,
                "product_id": probe.product_id,
                "probe_type": format!("{:?}", probe.probe_type())
            })
        })
        .collect::<Vec<_>>();
    Ok(json!(probes))
}

fn connect(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    if state.session.is_some() {
        return Err(RpcFailure::Operation(
            "a probe-rs session is already connected".to_string(),
        ));
    }
    let target = required_str(params, "target")?.to_string();
    let unique_id = optional_str(params, "unique_id")?;
    let speed_khz = u32::try_from(optional_u64(params, "speed_khz")?.unwrap_or(1_000))
        .map_err(|_| RpcFailure::InvalidParams("speed_khz exceeds u32 range".to_string()))?;
    let core_index = usize::try_from(optional_u64(params, "core_index")?.unwrap_or(0))
        .map_err(|_| RpcFailure::InvalidParams("core_index exceeds usize range".to_string()))?;
    let halt_on_connect = optional_bool(params, "halt_on_connect")?.unwrap_or(true);
    let allow_erase_all = optional_bool(params, "allow_erase_all")?.unwrap_or(false);
    let wire_protocol = optional_str(params, "wire_protocol")?;
    let probes = Lister::new().list_all();
    let probe_info = probes
        .into_iter()
        .find(|probe| {
            unique_id.is_none_or(|wanted| {
                probe.serial_number.as_deref() == Some(wanted) || probe.identifier.contains(wanted)
            })
        })
        .ok_or_else(|| RpcFailure::Operation("no matching debug probe found".to_string()))?;
    let description = probe_info.identifier.clone();
    let mut probe = probe_info.open().map_err(operation_error)?;
    if let Some(protocol) = wire_protocol {
        let protocol = match protocol.to_ascii_lowercase().as_str() {
            "jtag" => WireProtocol::Jtag,
            "swd" => WireProtocol::Swd,
            _ => {
                return Err(RpcFailure::InvalidParams(
                    "'wire_protocol' must be 'jtag' or 'swd'".to_string(),
                ));
            }
        };
        probe.select_protocol(protocol).map_err(operation_error)?;
    }
    let actual_speed_khz = probe.set_speed(speed_khz).map_err(operation_error)?;
    let permissions = if allow_erase_all {
        Permissions::new().allow_erase_all()
    } else {
        Permissions::new()
    };
    let mut session = probe
        .attach(&target, permissions)
        .map_err(operation_error)?;
    let cores = session.target().cores.clone();
    let selected = cores.get(core_index).ok_or_else(|| {
        RpcFailure::InvalidParams(format!(
            "core_index {core_index} is out of range for {} core(s)",
            cores.len()
        ))
    })?;
    let architecture = architecture_name(selected.core_type).to_string();
    if halt_on_connect {
        session
            .core(core_index)
            .map_err(operation_error)?
            .halt(Duration::from_secs(1))
            .map_err(operation_error)?;
    }
    let session_id = Uuid::new_v4().to_string();
    state.session = Some(ActiveSession {
        id: session_id.clone(),
        target: target.clone(),
        session,
        core_index,
        architecture: architecture.clone(),
        rtt: None,
    });
    Ok(json!({
        "session_id": session_id,
        "target": target,
        "probe": description,
        "speed_khz": actual_speed_khz,
        "wire_protocol": wire_protocol,
        "architecture": architecture,
        "core_count": cores.len(),
        "selected_core": core_index
    }))
}

fn disconnect(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let session = state.session.take().expect("session checked above");
    Ok(json!({"session_id": session.id, "target": session.target}))
}

fn reset(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let halt = optional_bool(params, "halt")?.unwrap_or(false);
    let result = with_core(state, params, |core| {
        if halt {
            core.reset_and_halt(Duration::from_secs(1))
                .map_err(operation_error)?;
        } else {
            core.reset().map_err(operation_error)?;
        }
        Ok(json!({"state": if halt { "halted" } else { "running" }}))
    })?;
    state.session.as_mut().expect("session checked above").rtt = None;
    Ok(result)
}

fn read_core_registers(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let architecture = state
        .session
        .as_ref()
        .ok_or_else(|| RpcFailure::Operation("no active session".to_string()))?
        .architecture
        .clone();
    with_core(state, params, |core| {
        let descriptions = core.registers().core_registers().collect::<Vec<_>>();
        let mut registers = BTreeMap::new();
        for register in descriptions {
            if let Ok(value) = core.read_core_reg(register) {
                if let Ok(value) = <RegisterValue as TryInto<u64>>::try_into(value) {
                    registers.insert(canonical_register_name(register.name()), value);
                }
            }
        }
        match architecture.as_str() {
            "riscv" => {
                add_register_alias(&mut registers, "lr", "x1");
                add_register_alias(&mut registers, "sp", "x2");
            }
            "xtensa" => {
                add_register_alias(&mut registers, "lr", "a0");
                add_register_alias(&mut registers, "sp", "a1");
            }
            _ => {}
        }
        Ok(json!({"registers": registers}))
    })
}

fn add_register_alias(registers: &mut BTreeMap<String, u64>, alias: &str, source: &str) {
    if !registers.contains_key(alias) {
        if let Some(value) = registers.get(source).copied() {
            registers.insert(alias.to_string(), value);
        }
    }
}

fn list_cores(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let active = state.session.as_ref().expect("session checked above");
    Ok(json!({
        "selected_core": active.core_index,
        "cores": active.session.target().cores.iter().enumerate().map(|(index, core)| {
            json!({
                "index": index,
                "name": core.name,
                "architecture": architecture_name(core.core_type),
                "selected": index == active.core_index
            })
        }).collect::<Vec<_>>()
    }))
}

fn read_exception_context(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let architecture = state
        .session
        .as_ref()
        .expect("session checked above")
        .architecture
        .clone();
    with_core(state, params, |core| {
        let descriptions = core.registers().core_registers().collect::<Vec<_>>();
        let mut registers = BTreeMap::new();
        for register in descriptions {
            let name = canonical_register_name(register.name());
            if name == "pc" {
                if let Ok(value) = core.read_core_reg(register) {
                    if let Ok(value) = <RegisterValue as TryInto<u64>>::try_into(value) {
                        registers.insert(name, value);
                    }
                }
            }
        }
        let exception_registers: &[(&str, u16)] = match architecture.as_str() {
            "riscv" => &[
                ("mstatus", 0x300),
                ("mepc", 0x341),
                ("mcause", 0x342),
                ("mtval", 0x343),
            ],
            "xtensa" => &[
                ("epc1", 0x0100 | 177),
                ("epc2", 0x0100 | 178),
                ("epc3", 0x0100 | 179),
                ("ps", 0x0100 | 230),
                ("exccause", 0x0100 | 232),
                ("excvaddr", 0x0100 | 238),
            ],
            _ => &[],
        };
        for (name, id) in exception_registers {
            let value: RegisterValue = core
                .read_core_reg(RegisterId(*id))
                .map_err(operation_error)?;
            let value = <RegisterValue as TryInto<u64>>::try_into(value)
                .map_err(|error| RpcFailure::Operation(error.to_string()))?;
            registers.insert((*name).to_string(), value);
        }
        Ok(json!({"architecture": architecture, "registers": registers}))
    })
}

pub fn canonical_register_name(name: &str) -> String {
    match name.to_ascii_uppercase().as_str() {
        "R15" => "pc".to_string(),
        "R14" => "lr".to_string(),
        "R13" => "sp".to_string(),
        _ => name.to_ascii_lowercase(),
    }
}

fn read_memory(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    let size = required_u64(params, "size")? as usize;
    if size > MAX_READ_BYTES {
        return Err(RpcFailure::InvalidParams(
            "memory read size exceeds 1 MiB".to_string(),
        ));
    }
    with_core(state, params, |core| {
        let mut data = vec![0_u8; size];
        core.read(address, &mut data).map_err(operation_error)?;
        Ok(json!({"data_base64": BASE64.encode(data), "size": size}))
    })
}

fn write_memory(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    let encoded = required_str(params, "data_base64")?;
    let data = BASE64
        .decode(encoded)
        .map_err(|error| RpcFailure::InvalidParams(format!("invalid base64 data: {error}")))?;
    if data.len() > MAX_WRITE_BYTES {
        return Err(RpcFailure::InvalidParams(
            "memory write size exceeds 64 KiB".to_string(),
        ));
    }
    with_core(state, params, |core| {
        core.write(address, &data).map_err(operation_error)?;
        Ok(json!({"bytes_written": data.len()}))
    })
}

fn breakpoint(state: &mut SidecarState, params: &Value, set: bool) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    with_core(state, params, |core| {
        if set {
            core.set_hw_breakpoint(address).map_err(operation_error)?;
        } else {
            core.clear_hw_breakpoint(address).map_err(operation_error)?;
        }
        Ok(json!({"address": address}))
    })
}

fn erase_flash(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let chip_erase = optional_bool(params, "chip_erase")?.unwrap_or(false);
    if !chip_erase {
        return Err(RpcFailure::InvalidParams(
            "probe-rs sidecar currently requires chip_erase=true; range erase is not safely mapped"
                .to_string(),
        ));
    }
    let active = state.session.as_mut().expect("session checked above");
    let mut progress = FlashProgress::empty();
    probe_rs::flashing::erase_all(&mut active.session, &mut progress, false)
        .map_err(operation_error)?;
    Ok(json!({"chip_erased": true}))
}

fn program_flash(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let address = required_u64(params, "address")?;
    let encoded = required_str(params, "data_base64")?;
    let data = BASE64
        .decode(encoded)
        .map_err(|error| RpcFailure::InvalidParams(format!("invalid base64 data: {error}")))?;
    let verify = optional_bool(params, "verify")?.unwrap_or(true);
    let erase_mode = optional_str(params, "erase_mode")?.unwrap_or("none");
    if !matches!(erase_mode, "none" | "sector" | "chip") {
        return Err(RpcFailure::InvalidParams(
            "'erase_mode' must be 'none', 'sector', or 'chip'".to_string(),
        ));
    }
    let reset_after = optional_bool(params, "reset_after")?.unwrap_or(false);
    let active = state.session.as_mut().expect("session checked above");
    let mut loader = active.session.target().flash_loader();
    loader.add_data(address, &data).map_err(operation_error)?;
    let mut options = DownloadOptions::default();
    options.verify = verify;
    options.do_chip_erase = erase_mode == "chip";
    options.skip_erase = erase_mode == "none";
    loader
        .commit(&mut active.session, options)
        .map_err(operation_error)?;
    if reset_after {
        active
            .session
            .core(active.core_index)
            .map_err(operation_error)?
            .reset()
            .map_err(operation_error)?;
        active.rtt = None;
    }
    Ok(json!({
        "address": address,
        "bytes_programmed": data.len(),
        "verified": verify,
        "erase_mode": erase_mode,
        "reset": reset_after
    }))
}

pub fn firmware_format_name(path: &str) -> Option<&'static str> {
    match Path::new(path)
        .extension()
        .and_then(|extension| extension.to_str())
        .map(str::to_ascii_lowercase)
        .as_deref()
    {
        Some("elf" | "axf") => Some("elf"),
        Some("hex" | "ihex") => Some("hex"),
        Some("bin") => Some("bin"),
        _ => None,
    }
}

fn flash_file(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let path = required_str(params, "path")?;
    let format_name = firmware_format_name(path).ok_or_else(|| {
        RpcFailure::InvalidParams(
            "firmware path must use .elf, .axf, .hex, .ihex, or .bin".to_string(),
        )
    })?;
    let address = optional_u64(params, "address")?;
    let erase_mode = optional_str(params, "erase_mode")?.unwrap_or("sector");
    if !matches!(erase_mode, "sector" | "chip") {
        return Err(RpcFailure::InvalidParams(
            "'erase_mode' must be 'sector' or 'chip'".to_string(),
        ));
    }
    let verify = optional_bool(params, "verify")?.unwrap_or(true);
    let reset_after = optional_bool(params, "reset_after")?.unwrap_or(true);
    let format = match format_name {
        "elf" => Format::Elf(ElfOptions::default()),
        "hex" => Format::Hex,
        "bin" => Format::Bin(BinOptions {
            base_address: address,
            skip: 0,
        }),
        _ => unreachable!("firmware_format_name returned an unknown format"),
    };
    let active = state.session.as_mut().expect("session checked above");
    let mut options = DownloadOptions::default();
    options.verify = verify;
    options.do_chip_erase = erase_mode == "chip";
    probe_rs::flashing::download_file_with_options(
        &mut active.session,
        Path::new(path),
        format,
        options,
    )
    .map_err(operation_error)?;
    if reset_after {
        active
            .session
            .core(active.core_index)
            .map_err(operation_error)?
            .reset()
            .map_err(operation_error)?;
        active.rtt = None;
    }
    Ok(json!({
        "path": path,
        "format": format_name,
        "verified": verify,
        "erase_mode": erase_mode,
        "reset": reset_after
    }))
}

fn verify_flash(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    let address = required_u64(params, "address")?;
    let encoded = required_str(params, "data_base64")?;
    let expected = BASE64
        .decode(encoded)
        .map_err(|error| RpcFailure::InvalidParams(format!("invalid base64 data: {error}")))?;
    with_core(state, params, |core| {
        let mut actual = vec![0_u8; expected.len()];
        core.read(address, &mut actual).map_err(operation_error)?;
        let first_mismatch = expected
            .iter()
            .zip(&actual)
            .position(|(expected, actual)| expected != actual);
        Ok(json!({
            "address": address,
            "bytes_verified": expected.len(),
            "verified": first_mismatch.is_none(),
            "first_mismatch_offset": first_mismatch
        }))
    })
}

fn rtt_attach(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let control_block = optional_u64(params, "control_block_address")?;
    let active = state.session.as_mut().expect("session checked above");
    let mut core = active
        .session
        .core(active.core_index)
        .map_err(operation_error)?;
    let scan_region = control_block.map_or(ScanRegion::Ram, ScanRegion::Exact);
    let mut rtt = Rtt::attach_region(&mut core, &scan_region).map_err(operation_error)?;
    let up_channels = rtt.up_channels().len();
    let down_channels = rtt.down_channels().len();
    active.rtt = Some(rtt);
    Ok(json!({
        "attached": true,
        "up_channels": up_channels,
        "down_channels": down_channels
    }))
}

fn rtt_detach(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let active = state.session.as_mut().expect("session checked above");
    active.rtt = None;
    Ok(json!({"attached": false}))
}

fn rtt_channels(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let active = state.session.as_mut().expect("session checked above");
    let rtt = active
        .rtt
        .as_mut()
        .ok_or_else(|| RpcFailure::Operation("RTT is not attached".to_string()))?;
    let up = rtt
        .up_channels()
        .iter()
        .enumerate()
        .map(|(index, channel)| {
            json!({
                "index": index,
                "name": channel.name(),
                "buffer_size": channel.buffer_size(),
                "direction": "up"
            })
        })
        .collect::<Vec<_>>();
    let down = rtt
        .down_channels()
        .iter()
        .enumerate()
        .map(|(index, channel)| {
            json!({
                "index": index,
                "name": channel.name(),
                "buffer_size": channel.buffer_size(),
                "direction": "down"
            })
        })
        .collect::<Vec<_>>();
    Ok(json!({"up": up, "down": down}))
}

fn rtt_read(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let channel = optional_u64(params, "channel")?.unwrap_or(0) as usize;
    let max_bytes = optional_u64(params, "max_bytes")?.unwrap_or(4096) as usize;
    if max_bytes > MAX_READ_BYTES {
        return Err(RpcFailure::InvalidParams(
            "RTT read size exceeds 1 MiB".to_string(),
        ));
    }
    let active = state.session.as_mut().expect("session checked above");
    let ActiveSession {
        session,
        core_index,
        rtt,
        ..
    } = active;
    let rtt = rtt
        .as_mut()
        .ok_or_else(|| RpcFailure::Operation("RTT is not attached".to_string()))?;
    let mut core = session.core(*core_index).map_err(operation_error)?;
    let up = rtt
        .up_channels()
        .get_mut(channel)
        .ok_or_else(|| RpcFailure::InvalidParams(format!("unknown RTT up channel {channel}")))?;
    let mut data = vec![0_u8; max_bytes];
    let bytes_read = up.read(&mut core, &mut data).map_err(operation_error)?;
    data.truncate(bytes_read);
    Ok(json!({"channel": channel, "data_base64": BASE64.encode(data), "bytes_read": bytes_read}))
}

fn rtt_write(state: &mut SidecarState, params: &Value) -> Result<Value, RpcFailure> {
    require_session_id(state, params)?;
    let channel = optional_u64(params, "channel")?.unwrap_or(0) as usize;
    let data = BASE64
        .decode(required_str(params, "data_base64")?)
        .map_err(|error| RpcFailure::InvalidParams(format!("invalid base64 data: {error}")))?;
    if data.len() > MAX_WRITE_BYTES {
        return Err(RpcFailure::InvalidParams(
            "RTT write size exceeds 64 KiB".to_string(),
        ));
    }
    let active = state.session.as_mut().expect("session checked above");
    let ActiveSession {
        session,
        core_index,
        rtt,
        ..
    } = active;
    let rtt = rtt
        .as_mut()
        .ok_or_else(|| RpcFailure::Operation("RTT is not attached".to_string()))?;
    let mut core = session.core(*core_index).map_err(operation_error)?;
    let down = rtt
        .down_channels()
        .get_mut(channel)
        .ok_or_else(|| RpcFailure::InvalidParams(format!("unknown RTT down channel {channel}")))?;
    let bytes_written = down.write(&mut core, &data).map_err(operation_error)?;
    Ok(json!({"channel": channel, "bytes_written": bytes_written}))
}

fn with_core<F>(state: &mut SidecarState, params: &Value, operation: F) -> Result<Value, RpcFailure>
where
    F: FnOnce(&mut probe_rs::Core<'_>) -> Result<Value, RpcFailure>,
{
    require_session_id(state, params)?;
    let active = state.session.as_mut().expect("session checked above");
    let requested_core = optional_u64(params, "core_index")?
        .map(|value| value as usize)
        .unwrap_or(active.core_index);
    let mut core = active
        .session
        .core(requested_core)
        .map_err(operation_error)?;
    operation(&mut core)
}

fn require_session_id(state: &SidecarState, params: &Value) -> Result<(), RpcFailure> {
    let requested = required_str(params, "session_id")?;
    let active = state
        .session
        .as_ref()
        .ok_or_else(|| RpcFailure::Operation("no active probe-rs session".to_string()))?;
    if active.id != requested {
        return Err(RpcFailure::Operation("unknown session_id".to_string()));
    }
    Ok(())
}

fn required_str<'a>(params: &'a Value, name: &str) -> Result<&'a str, RpcFailure> {
    params
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be a string")))
}

fn optional_str<'a>(params: &'a Value, name: &str) -> Result<Option<&'a str>, RpcFailure> {
    match params.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_str()
            .map(Some)
            .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be a string"))),
    }
}

fn required_u64(params: &Value, name: &str) -> Result<u64, RpcFailure> {
    params
        .get(name)
        .and_then(Value::as_u64)
        .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be an unsigned integer")))
}

fn optional_u64(params: &Value, name: &str) -> Result<Option<u64>, RpcFailure> {
    match params.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value.as_u64().map(Some).ok_or_else(|| {
            RpcFailure::InvalidParams(format!("'{name}' must be an unsigned integer"))
        }),
    }
}

fn optional_bool(params: &Value, name: &str) -> Result<Option<bool>, RpcFailure> {
    match params.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_bool()
            .map(Some)
            .ok_or_else(|| RpcFailure::InvalidParams(format!("'{name}' must be a boolean"))),
    }
}

fn status_name(status: CoreStatus) -> &'static str {
    match status {
        CoreStatus::Running => "running",
        CoreStatus::Halted(_) => "halted",
        CoreStatus::LockedUp => "locked-up",
        CoreStatus::Sleeping => "sleeping",
        CoreStatus::Unknown => "unknown",
    }
}

fn architecture_name(core_type: probe_rs::CoreType) -> &'static str {
    match core_type {
        probe_rs::CoreType::Riscv => "riscv",
        probe_rs::CoreType::Xtensa => "xtensa",
        _ => "arm",
    }
}

fn operation_error(error: impl std::fmt::Display) -> RpcFailure {
    RpcFailure::Operation(error.to_string())
}

fn classify_operation_error(message: &str) -> &'static str {
    let message = message.to_ascii_lowercase();
    if message.contains("probe")
        && (message.contains("not found") || message.contains("no matching"))
    {
        "probe_not_found"
    } else if message.contains("permission") || message.contains("access denied") {
        "permission_denied"
    } else if message.contains("target") && message.contains("not found") {
        "target_not_found"
    } else if message.contains("timeout") || message.contains("timed out") {
        "timeout"
    } else if message.contains("flash") {
        "flash_error"
    } else if message.contains("rtt") {
        "rtt_error"
    } else {
        "operation_failed"
    }
}
