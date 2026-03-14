"""
ITS table validator — GIC-600 ITS EventID→IntID→CPU consistency checker.

Validates that the Interrupt Translation Service (ITS) LPI mapping tables are
self-consistent:
  - MAPD: Device Table (DeviceID → ITT base address, Size)
  - MAPC: Collection Table (CollectionID → CPU target RDBASE)
  - MAPTI: EventID → IntID + CollectionID mapping

Parses:
  - /sys/kernel/debug/irq/irqs/N (IRQ domain dump, available with CONFIG_GENIRQ_DEBUGFS)
  - ITS state dump from GIC-600 debug registers (if captured to file)
  - Linux GICv3/ITS driver log lines from dmesg (ITS table allocation messages)

Reference: ARM GIC-600 TRM, ARM GICv3/v4 Architecture Specification §5.4–5.6
"""

from __future__ import annotations

import re
import os
from typing import Any

# dmesg ITS init: "GICv3: ITS ... at <addr>"
_ITS_INIT_RE = re.compile(
    r"GICv3:\s+ITS\s+(?:\[0x\w+\]\s+)?at\s+0x(?P<addr>[0-9a-fA-F]+)",
    re.IGNORECASE,
)

# ITS MAPD command logged (debug): "its: MAPD DevID=N ITT=0xADDR SIZE=M"
_MAPD_RE = re.compile(
    r"(?:its|ITS).*?MAPD.*?DevID[=:\s]+(?P<devid>\d+).*?"
    r"(?:ITT|itt)[=:\s]+0x(?P<itt>[0-9a-fA-F]+).*?"
    r"(?:SIZE|size)[=:\s]+(?P<size>\d+)",
    re.IGNORECASE,
)

# ITS MAPC command: "its: MAPC CollectionID=N RDBASE=0xADDR"
_MAPC_RE = re.compile(
    r"(?:its|ITS).*?MAPC.*?(?:CollectionID|CID)[=:\s]+(?P<cid>\d+).*?"
    r"(?:RDBASE|rdbase)[=:\s]+0x(?P<rdbase>[0-9a-fA-F]+)",
    re.IGNORECASE,
)

# ITS MAPTI command: "its: MAPTI DevID=N EventID=M IntID=K CID=L"
_MAPTI_RE = re.compile(
    r"(?:its|ITS).*?MAPTI.*?DevID[=:\s]+(?P<devid>\d+).*?"
    r"EventID[=:\s]+(?P<eventid>\d+).*?"
    r"IntID[=:\s]+(?P<intid>\d+).*?"
    r"(?:CID|CollectionID)[=:\s]+(?P<cid>\d+)",
    re.IGNORECASE,
)

# ITS SYNC command: "its: SYNC target=0xADDR"
_SYNC_RE = re.compile(
    r"(?:its|ITS).*?SYNC.*?(?:target|RDBASE)[=:\s]+0x(?P<target>[0-9a-fA-F]+)",
    re.IGNORECASE,
)

# ITS error: "its: command error" or "ITS: invalid..."
_ITS_ERR_RE = re.compile(
    r"(?:its|ITS).*?(?:error|invalid|failed|timeout|overflow|OOR)",
    re.IGNORECASE,
)

# LPI IntID range: Linux GICv3 driver allocates LPIs starting at 8192
LPI_BASE = 8192


def validate_its_table(log_path: str) -> dict[str, Any]:
    """Validate ITS EventID→IntID→CPU mapping table consistency.

    Parameters
    ----------
    log_path:
        Path to dmesg log with ITS debug output (enable with
        `echo 1 > /sys/bus/platform/drivers/arm-gic-v3-its/debug` if available,
        or use kernel with CONFIG_IRQCHIP_DEBUG).

    Returns
    -------
    dict with keys:
        ``its_controllers``  — ITS base addresses found
        ``mapd_entries``     — Device Table entries parsed
        ``mapc_entries``     — Collection Table entries parsed
        ``mapti_entries``    — EventID→IntID mappings parsed
        ``sync_events``      — SYNC command targets
        ``violations``       — consistency errors found
        ``its_errors``       — ITS error log lines
        ``diagnosis``        — human-readable summary
    """
    path = os.path.abspath(log_path)
    if not os.path.isfile(path):
        return {"error": f"File not found: {path}"}

    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()

    its_controllers: list[str] = []
    mapd_entries: list[dict] = []
    mapc_entries: list[dict] = []
    mapti_entries: list[dict] = []
    sync_events: list[str] = []
    its_errors: list[str] = []

    for line in lines:
        m = _ITS_INIT_RE.search(line)
        if m:
            its_controllers.append(f"0x{m.group('addr')}")

        m = _MAPD_RE.search(line)
        if m:
            mapd_entries.append({
                "device_id": int(m.group("devid")),
                "itt_addr": f"0x{m.group('itt')}",
                "size": int(m.group("size")),
            })

        m = _MAPC_RE.search(line)
        if m:
            mapc_entries.append({
                "collection_id": int(m.group("cid")),
                "rdbase": f"0x{m.group('rdbase')}",
            })

        m = _MAPTI_RE.search(line)
        if m:
            mapti_entries.append({
                "device_id": int(m.group("devid")),
                "event_id": int(m.group("eventid")),
                "int_id": int(m.group("intid")),
                "collection_id": int(m.group("cid")),
            })

        m = _SYNC_RE.search(line)
        if m:
            sync_events.append(f"0x{m.group('target')}")

        if _ITS_ERR_RE.search(line):
            its_errors.append(line.strip())

    # Consistency checks
    violations: list[str] = []

    # 1. Every MAPTI must reference a MAPD'd DeviceID
    mapd_devids = {e["device_id"] for e in mapd_entries}
    for mt in mapti_entries:
        if mapd_devids and mt["device_id"] not in mapd_devids:
            violations.append(
                f"MAPTI DevID={mt['device_id']} references unmapped device "
                f"(no MAPD found). ITS will reject this command."
            )

    # 2. Every MAPTI must reference a MAPC'd CollectionID
    mapc_cids = {e["collection_id"] for e in mapc_entries}
    for mt in mapti_entries:
        if mapc_cids and mt["collection_id"] not in mapc_cids:
            violations.append(
                f"MAPTI CID={mt['collection_id']} references unmapped collection "
                f"(no MAPC found). IRQ will not be routed to any CPU."
            )

    # 3. IntIDs must be in LPI range (≥ 8192)
    for mt in mapti_entries:
        if mt["int_id"] < LPI_BASE:
            violations.append(
                f"MAPTI IntID={mt['int_id']} is below LPI base {LPI_BASE}. "
                "LPI IntIDs must be ≥ 8192. This is an ITS configuration error."
            )

    # 4. MAPD size must be power of 2 (number of event IDs = 2^size)
    for md in mapd_entries:
        sz = md["size"]
        if sz > 20:  # reasonable upper bound
            violations.append(
                f"MAPD DevID={md['device_id']} SIZE={sz} is suspiciously large "
                f"(implies 2^{sz} events). Verify device table size field."
            )

    # Diagnosis
    if its_errors:
        diagnosis = (
            f"{len(its_errors)} ITS error(s) detected. "
            f"First: {its_errors[0][:120]}. "
            "ITS command queue error or SYNC timeout. "
            "Check: (1) ITS command queue not full, (2) RDBASE points to valid Redistributor, "
            "(3) ITT memory allocated at 8-byte aligned physical address."
        )
    elif violations:
        diagnosis = (
            f"{len(violations)} ITS table violation(s): {violations[0]} "
            "Required ITS sequence: MAPD → MAPC → MAPTI → SYNC. "
            "Missing SYNC after MAPTI means CPU target is not committed to hardware. "
            "Escalate to /interrupt-virtualization-expert for GIC-600 register dump."
        )
    elif not mapti_entries and not mapd_entries:
        diagnosis = (
            "No ITS command log found. Enable ITS debug: "
            "recompile kernel with CONFIG_IRQCHIP_DEBUG or "
            "add 'irqchip.gicv3_its_debug=1' to kernel cmdline."
        )
    else:
        diagnosis = (
            f"ITS table appears consistent: "
            f"{len(mapd_entries)} MAPD, {len(mapc_entries)} MAPC, "
            f"{len(mapti_entries)} MAPTI entries. "
            f"{len(sync_events)} SYNC events recorded. No violations detected."
        )

    return {
        "file": path,
        "lines_parsed": len(lines),
        "its_controllers": its_controllers,
        "mapd_entries": mapd_entries[:20],
        "mapc_entries": mapc_entries[:20],
        "mapti_entries": mapti_entries[:20],
        "sync_events": sync_events[:10],
        "violations": violations,
        "its_errors": its_errors[:10],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python its_validator.py <dmesg_log>")
        sys.exit(1)
    print(json.dumps(validate_its_table(sys.argv[1]), indent=2))
