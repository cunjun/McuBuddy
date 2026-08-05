from __future__ import annotations

from ...backends.probe.base import ProbeCapability, probe_supports
from ...issue_reporting import issue_details
from ...security_guards import ensure_rtt_scan_allowed, runtime_config_for
from ...session import SessionState


def read_rtt_log(
    session: SessionState,
    channel: int = 0,
    max_bytes: int = 4096,
    search_start: int = 0x20000000,
    search_size: int = 0x50000,
) -> dict:
    backend_result = None
    if probe_supports(session.services.probe, ProbeCapability.RTT_READ):
        try:
            backend_result = session.services.probe.read_rtt_log(channel=channel, max_bytes=max_bytes)
        except Exception as e:
            backend_result = {"status": "error", "summary": str(e)}
        if backend_result.get("status") == "ok":
            return backend_result

    if blocked := ensure_rtt_scan_allowed(runtime_config_for(session), search_size):
        return blocked

    scan_start = search_start
    scan_end = search_start + search_size
    get_regions = getattr(session.services.probe, "get_memory_regions", None)
    if callable(get_regions):
        known_regions = get_regions()
        ram_regions = [
            region
            for region in known_regions
            if str(region.get("kind", "")).lower() == "ram"
            and int(region["end"]) > search_start
            and int(region["start"]) < scan_end
        ]
        if known_regions and not ram_regions:
            return {
                "status": "error",
                "summary": "The requested RTT scan range does not overlap target RAM.",
                "issue": issue_details(
                    "hardware_limit",
                    evidence="Target memory map contains no RAM in the requested scan range.",
                    impact="Scanning this range could cause an SWD/JTAG memory fault.",
                    next_step="Load the correct target pack or pass a RAM-backed search range.",
                ),
            }
        if ram_regions:
            scan_start = max(search_start, min(int(region["start"]) for region in ram_regions))
            scan_end = min(scan_end, max(int(region["end"]) for region in ram_regions))

    magic = b"SEGGER RTT\x00"
    chunk_size = 1024
    overlap = 16

    try:
        cb_addr = None
        end_addr = scan_end
        addr = scan_start

        while addr < end_addr:
            read_size = min(chunk_size, end_addr - addr)
            data = session.services.probe.read_memory(addr, read_size)
            idx = data.find(magic)
            while idx != -1:
                candidate_addr = addr + idx
                header = session.services.probe.read_memory(candidate_addr, 24)
                if header[: len(magic)] == magic:
                    max_num_up = int.from_bytes(header[16:20], "little")
                    if 1 <= max_num_up <= 16:
                        cb_addr = candidate_addr
                        break
                idx = data.find(magic, idx + 1)
            if cb_addr is not None:
                break
            if read_size <= overlap:
                break
            addr += read_size - overlap

        if cb_addr is None:
            return {
                "status": "error",
                "summary": "RTT control block not found in scanned range.",
                "scan_range": {"start": hex(scan_start), "end": hex(scan_end)},
                "issue": issue_details(
                    "firmware_not_applicable",
                    evidence="No SEGGER RTT control block was found inside target RAM.",
                    impact="This firmware may not include or initialize RTT logging.",
                    next_step="Use UART logging or confirm that SEGGER RTT is linked and initialized.",
                ),
            }

        header = session.services.probe.read_memory(cb_addr, 24)
        max_num_up = int.from_bytes(header[16:20], "little")
        if not (1 <= max_num_up <= 16):
            return {
                "status": "error",
                "summary": "RTT control block not found in scanned range.",
            }

        if channel >= max_num_up:
            return {
                "status": "error",
                "summary": f"RTT up-buffer channel {channel} is out of range (max {max_num_up - 1}).",
            }

        up_desc_addr = cb_addr + 24 + channel * 24
        up_desc = session.services.probe.read_memory(up_desc_addr, 24)

        p_buffer = int.from_bytes(up_desc[4:8], "little")
        size_of_buffer = int.from_bytes(up_desc[8:12], "little")
        wr_off = int.from_bytes(up_desc[12:16], "little")
        rd_off = int.from_bytes(up_desc[16:20], "little")

        if size_of_buffer <= 0:
            return {
                "status": "error",
                "summary": f"Invalid RTT buffer size {size_of_buffer} for channel {channel}.",
            }
        if wr_off >= size_of_buffer or rd_off >= size_of_buffer:
            return {
                "status": "error",
                "summary": f"Invalid RTT ring buffer offsets for channel {channel}.",
            }

        if wr_off >= rd_off:
            available = wr_off - rd_off
        else:
            available = size_of_buffer - rd_off + wr_off

        to_read = min(available, max_bytes)
        raw = b""
        if to_read > 0:
            if rd_off + to_read <= size_of_buffer:
                raw = session.services.probe.read_memory(p_buffer + rd_off, to_read)
            else:
                first_len = size_of_buffer - rd_off
                second_len = to_read - first_len
                raw = session.services.probe.read_memory(
                    p_buffer + rd_off, first_len
                ) + session.services.probe.read_memory(p_buffer, second_len)

        return {
            "status": "ok",
            "summary": f"Read {len(raw)} bytes from RTT channel {channel}.",
            "cb_address": hex(cb_addr),
            "channel": channel,
            "buffer_size": size_of_buffer,
            "wr_off": wr_off,
            "rd_off": rd_off,
            "bytes_available": available,
            "text": raw.decode("utf-8", errors="replace"),
            **(
                {"backend_hint": backend_result["summary"]}
                if backend_result and backend_result.get("status") == "error"
                else {}
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "summary": str(e),
        }
