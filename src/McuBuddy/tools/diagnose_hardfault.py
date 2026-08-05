from __future__ import annotations

from ..models.diagnostics import HardFaultDiagnosis, LogContext, StackSnapshot, SymbolContext
from ..issue_reporting import issue_details
from ..session import SessionState
from .diagnostic_context import collect_diagnostic_context
from .diagnose_faults import _classify_fault, _describe_fault


def diagnose_hardfault(
    session: SessionState,
    auto_halt: bool = True,
    include_logs: bool = True,
    log_tail_lines: int = 50,
    resolve_symbols: bool = True,
    include_fault_registers: bool = True,
    include_stack_snapshot: bool = True,
    stack_snapshot_bytes: int = 64,
    suspected_stage: str | None = None,
) -> dict:
    if auto_halt:
        session.services.probe.halt()

    context = collect_diagnostic_context(
        session,
        include_fault_registers=include_fault_registers,
        include_logs=include_logs,
        log_tail_lines=log_tail_lines,
        resolve_symbols=resolve_symbols,
    )
    core = context.core
    fault_registers = context.fault_registers
    pc_symbol = context.pc_symbol
    lr_symbol = context.lr_symbol
    source = context.source
    log_lines = context.log_lines
    last_meaningful = context.last_meaningful_log

    stack_snapshot = StackSnapshot()
    if include_stack_snapshot:
        raw = session.services.probe.read_memory(core["sp"], stack_snapshot_bytes)
        stack_snapshot = StackSnapshot(
            included=True,
            start_address=hex(core["sp"]),
            size_bytes=stack_snapshot_bytes,
            data_hex=raw.hex(" "),
        )

    cfsr = fault_registers.get("cfsr", 0)
    hfsr = fault_registers.get("hfsr", 0)
    ipsr = core.get("xpsr", 0) & 0x1FF
    handler_active = bool(pc_symbol and "hardfault" in pc_symbol.lower()) or ipsr == 3
    fault_detected = bool(cfsr or (hfsr & 0x40000002) or handler_active)
    fault_class = _classify_fault(fault_registers) if fault_detected else "none"
    summary_stage = suspected_stage or "startup"
    summary = (
        f"Target entered HardFault shortly after {summary_stage}."
        if fault_detected
        else "No HardFault evidence was found in the captured target state."
    )

    mmfar = fault_registers.get("mmfar", 0)
    bfar = fault_registers.get("bfar", 0)
    shcsr = fault_registers.get("shcsr", 0)

    evidence: list[str] = []
    if last_meaningful:
        evidence.append(f"Last meaningful UART line = '{last_meaningful}'.")
    evidence.append(f"PC = {hex(core['pc'])}" + (f" ({pc_symbol})" if pc_symbol else "") + ".")
    evidence.append(f"LR = {hex(core['lr'])}" + (f" ({lr_symbol})" if lr_symbol else "") + ".")
    evidence.append(f"SP = {hex(core['sp'])}.")
    evidence.append(f"xPSR = {hex(core['xpsr'])}.")
    if source:
        evidence.append(f"Source = {source}.")
    evidence.append(f"CFSR = {hex(cfsr)}.")
    evidence.append(f"HFSR = {hex(hfsr)}.")
    evidence.append(f"MMFAR = {hex(mmfar)}.")
    evidence.append(f"BFAR = {hex(bfar)}.")
    evidence.append(f"SHCSR = {hex(shcsr)}.")
    if pc_symbol:
        evidence.append(f"PC symbol = {pc_symbol}.")
    if lr_symbol:
        evidence.append(f"LR symbol = {lr_symbol}.")
    if cfsr & 0x00000001:
        evidence.append("CFSR IACCVIOL bit set.")
    if cfsr & 0x00000002:
        evidence.append("CFSR DACCVIOL bit set.")
    if cfsr & 0x00000008:
        evidence.append("CFSR MUNSTKERR bit set.")
    if cfsr & 0x00000010:
        evidence.append("CFSR MSTKERR bit set.")
    if cfsr & 0x00000020:
        evidence.append("CFSR MLSPERR bit set.")
    if cfsr & 0x00000080:
        evidence.append(f"CFSR MMARVALID bit set, MMFAR = {hex(mmfar)}.")
    if cfsr & 0x00000100:
        evidence.append("CFSR IBUSERR bit set.")
    if cfsr & 0x00000200:
        evidence.append("CFSR PRECISERR bit set.")
    if cfsr & 0x00000400:
        evidence.append("CFSR IMPRECISERR bit set.")
    if cfsr & 0x00000800:
        evidence.append("CFSR UNSTKERR bit set.")
    if cfsr & 0x00001000:
        evidence.append("CFSR STKERR bit set.")
    if cfsr & 0x00002000:
        evidence.append("CFSR LSPERR bit set.")
    if cfsr & 0x00008000:
        evidence.append(f"CFSR BFARVALID bit set, BFAR = {hex(bfar)}.")
    if cfsr & 0x00010000:
        evidence.append("CFSR UNDEFINSTR bit set.")
    if cfsr & 0x00020000:
        evidence.append("CFSR INVSTATE bit set.")
    if cfsr & 0x00040000:
        evidence.append("CFSR INVPC bit set.")
    if cfsr & 0x00080000:
        evidence.append("CFSR NOCP bit set.")
    if cfsr & 0x01000000:
        evidence.append("CFSR UNALIGNED bit set.")
    if cfsr & 0x02000000:
        evidence.append("CFSR DIVBYZERO bit set.")
    if hfsr & 0x00000002:
        evidence.append("HFSR VECTTBL bit set.")
    if hfsr & 0x40000000:
        evidence.append("HFSR FORCED bit set.")
    if pc_symbol == "HardFault_Handler":
        evidence.append("PC resolves to HardFault_Handler.")
    if core.get("pc") == 0xFFFFFFFF:
        evidence.append("PC = 0xffffffff.")

    diagnosis = HardFaultDiagnosis(
        status="ok" if fault_detected else "partial",
        diagnosis_type="hardfault_detected" if fault_detected else "no_hardfault_evidence",
        summary=summary,
        confidence="high" if fault_detected and cfsr else ("medium" if fault_detected else "low"),
        target_state={"halted": True, "reason": "halted_for_analysis"},
        fault={
            "fault_detected": fault_detected,
            "fault_handler_active": handler_active,
            "fault_class": fault_class if fault_detected else None,
            "fault_description": _describe_fault(fault_class) if fault_detected else None,
            "escalated_to_hardfault": bool(hfsr & 0x40000000),
            "registers": {
                "pc": hex(core["pc"]),
                "lr": hex(core["lr"]),
                "sp": hex(core["sp"]),
                "xpsr": hex(core["xpsr"]),
                **{name: hex(value) for name, value in fault_registers.items()},
            },
        },
        symbol_context=SymbolContext(
            pc_symbol=pc_symbol,
            lr_symbol=lr_symbol,
            source=source,
        ),
        log_context=LogContext(
            included=include_logs,
            last_lines=log_lines,
            last_meaningful_line=last_meaningful,
            log_stopped_abruptly=bool(last_meaningful),
        ),
        stack_snapshot=stack_snapshot,
        evidence=evidence,
        raw_refs=context.raw_refs,
        issue=(
            None
            if fault_detected
            else issue_details(
                "insufficient_evidence",
                evidence="CFSR/HFSR are clear and execution is not in HardFault_Handler.",
                impact="A HardFault conclusion would be a false positive.",
                next_step="Capture the target at the failure moment or provide crash logs before retrying.",
            )
        ),
    )
    return diagnosis.model_dump()
