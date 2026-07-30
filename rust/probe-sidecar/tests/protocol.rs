use mcu_buddy_probe_sidecar::{
    canonical_register_name, firmware_format_name, handle_request_line, SidecarState,
};
use serde_json::{json, Value};

#[test]
fn hello_reports_compatible_protocol_version() {
    let mut state = SidecarState::default();
    let response = handle_request_line(
        &mut state,
        r#"{"jsonrpc":"2.0","id":1,"method":"hello","params":{"protocol_version":2}}"#,
    );
    let value: Value = serde_json::from_str(&response).unwrap();

    assert_eq!(value["jsonrpc"], "2.0");
    assert_eq!(value["id"], 1);
    assert_eq!(value["result"]["protocol_version"], 2);
    assert_eq!(value["result"]["features"]["flash"], true);
    assert_eq!(value["result"]["features"]["rtt"], true);
    assert_eq!(value["result"]["features"]["multi_core"], true);
    assert_eq!(value["result"]["limits"]["max_read_bytes"], 1024 * 1024);
    assert_eq!(value["result"]["limits"]["max_write_bytes"], 64 * 1024);
}

#[test]
fn unknown_method_returns_json_rpc_method_not_found() {
    let mut state = SidecarState::default();
    let response = handle_request_line(
        &mut state,
        &json!({"jsonrpc": "2.0", "id": 7, "method": "missing", "params": {}}).to_string(),
    );
    let value: Value = serde_json::from_str(&response).unwrap();

    assert_eq!(value["id"], 7);
    assert_eq!(value["error"]["code"], -32601);
}

#[test]
fn cortex_m_register_names_match_mcu_buddy_contract() {
    assert_eq!(canonical_register_name("R15"), "pc");
    assert_eq!(canonical_register_name("R14"), "lr");
    assert_eq!(canonical_register_name("R13"), "sp");
    assert_eq!(canonical_register_name("XPSR"), "xpsr");
    assert_eq!(canonical_register_name("R0"), "r0");
}

#[test]
fn riscv_register_names_preserve_architecture_registers() {
    assert_eq!(canonical_register_name("PC"), "pc");
    assert_eq!(canonical_register_name("X2"), "x2");
    assert_eq!(canonical_register_name("MCAUSE"), "mcause");
}

#[test]
fn firmware_formats_cover_elf_hex_and_bin_images() {
    assert_eq!(firmware_format_name("firmware.elf"), Some("elf"));
    assert_eq!(firmware_format_name("firmware.axf"), Some("elf"));
    assert_eq!(firmware_format_name("firmware.hex"), Some("hex"));
    assert_eq!(firmware_format_name("firmware.bin"), Some("bin"));
    assert_eq!(firmware_format_name("firmware.txt"), None);
}
