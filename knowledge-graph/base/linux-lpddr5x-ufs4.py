"""
LPDDR5X memory subsystem and UFS 4.0 storage — seed knowledge ingestion.

Adds LPDDR5X (JEDEC JESD79-5B) and UFS 4.0 (JESD220F) components that
extend existing LPDDR5/UFS coverage in linux-platform-devices.py:
  - LPDDR5X speed bins (6400/7500/8533 Mbps) and power states
  - LPDDR5X memory controller and PHY
  - UFS 4.0 gear configuration (HS-G5) and MIPI M-PHY Gen4
  - UFS 4.0 host controller (UFSHCI v4.0)
  - Clock sources for DRAM and UFS subsystems
  - Power domains and failure modes

Sources:
  - JEDEC JESD79-5B LPDDR5X specification (public summary)
  - JEDEC JESD220F UFS 4.0 specification (public summary)
  - MIPI M-PHY specification overview (public)
  - Linux Documentation/scsi/ufs.rst
  - Linux drivers/ufs/ source code (UFSHCI v4.0 support, kernel 6.1+)
  - Micron LPDDR5X product brief (public)
  - Samsung LPDDR5X white paper (public)
  - Qualcomm UFS 4.0 implementation notes (Snapdragon 8 Gen 2 public docs)

Namespace: base (open-source only)
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _HERE)

import kuzu
import schema as _schema
from _ingest_helpers import upsert_node, create_rel

# ---------------------------------------------------------------------------
# Components — LPDDR5X memory subsystem
# ---------------------------------------------------------------------------

_LPDDR5X_COMPONENTS = [
    ("LPDDR5X-MC",           "memory-controller",  "JEDEC",
     "LPDDR5X Memory Controller — JEDEC JESD79-5B; supports 6400/7500/8533 Mbps "
     "data rates (vs LPDDR5 max 6400 Mbps); dual-channel, 32-bit channels; "
     "command/address interface at 1/4 data rate; tRCD and tRP timing updated; "
     "backgating power savings via BSST (Bank Subset Shutdown)",
     "base"),
    ("LPDDR5X-PHY",          "phy",                "JEDEC",
     "LPDDR5X Physical Layer Interface — differential CA/DQ signaling; "
     "on-die ECC (optional); ZQ calibration per channel; "
     "RDQS (Read DQS) for improved read margin at 8533 Mbps; "
     "temperature-compensated auto-refresh (TCSR register)",
     "base"),
    ("LPDDR5X-Channel-A",    "memory-channel",     "JEDEC",
     "LPDDR5X Channel A — 16-bit data + 2-bit ECC; up to 8533 Mbps; "
     "independent power domain from Channel B; "
     "DRAM array organized in 8 banks per bank group",
     "base"),
    ("LPDDR5X-Channel-B",    "memory-channel",     "JEDEC",
     "LPDDR5X Channel B — 16-bit data + 2-bit ECC; mirrors Channel A; "
     "can be independently self-refreshed during partial activity",
     "base"),
    ("LPDDR5X-BSST",         "power-feature",      "JEDEC",
     "LPDDR5X Bank Subset Shutdown (BSST) — shuts down unused bank groups; "
     "reduces DRAM active power by up to 30% at light load; "
     "supported from JESD79-5B onwards; enabled via MR register programming",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — UFS 4.0 subsystem
# ---------------------------------------------------------------------------

_UFS4_COMPONENTS = [
    ("UFS-4.0-HCI",          "storage-controller", "JEDEC",
     "UFS 4.0 Host Controller Interface (UFSHCI v4.0) — JEDEC JESD220F; "
     "doubles bandwidth vs UFS 3.1 (2.9 GB/s → 4.2 GB/s per lane); "
     "HS-G5 gear (23.4 Gbps MIPI M-PHY); two lanes supported; "
     "Write Booster 2.0 for sustained write performance; "
     "Linux driver: drivers/ufs/core/ufshcd.c (kernel 6.1+ UFSHCI v4.0)",
     "base"),
    ("UFS-4.0-M-PHY-Gen4",   "phy",                "MIPI",
     "MIPI M-PHY Gen4 — physical layer for UFS 4.0 HS-G5; "
     "Gear 5 rate: 23.4 Gbps per lane; HS-A/HS-B amplitude modes; "
     "PWM-G1 gear for low-power short transfers; "
     "gear-switch handshake via Unipro PACP_PWR_REQ/PACP_PWR_CNF",
     "base"),
    ("UFS-4.0-UniPro",       "protocol",           "MIPI",
     "MIPI UniPro v2.0 — transport layer for UFS 4.0; "
     "L4 transport: command queuing (MCQ, up to 32 queues); "
     "Multi-Circular Queue (MCQ) in UFS 4.0 for parallel I/O; "
     "Linux UFS MCQ: drivers/ufs/core/ufs-mcq.c (kernel 6.4+)",
     "base"),
    ("UFS-4.0-WriteBooster",  "storage-feature",   "JEDEC",
     "UFS 4.0 Write Booster 2.0 — SLC-mode buffer for sustained writes; "
     "up to 20GB buffer on 256GB device; auto-flush management; "
     "sysfs: /sys/class/block/sda/device/write_booster_enable; "
     "must be explicitly enabled by host in descriptor bWriteBoosterEnable",
     "base"),
    ("linux-ufshcd",          "driver",             "linux",
     "Linux UFS host controller driver (drivers/ufs/core/ufshcd.c) — "
     "UFSHCI v4.0 support since kernel 6.1; MCQ (Multi-Circular Queue) since 6.4; "
     "Write Booster management; gear-switch via PACP; "
     "perf mode: /sys/class/block/sda/queue/scheduler",
     "base"),
    ("linux-ufs-mcq",         "driver",             "linux",
     "Linux UFS Multi-Circular Queue driver (drivers/ufs/core/ufs-mcq.c) — "
     "parallel I/O with up to 32 submission queues; "
     "reduces latency tail at high queue depth vs legacy single-queue; "
     "enabled by default on UFSHCI 4.0 controllers; requires kernel 6.4+",
     "base"),
]

# ---------------------------------------------------------------------------
# Power domains
# ---------------------------------------------------------------------------

_LPDDR5X_POWER_DOMAINS = [
    ("LPDDR5X-VDD1-1.8V",   1800,  0,     "base"),
    ("LPDDR5X-VDD2-1.05V",  1050,  0,     "base"),
    ("LPDDR5X-VDDQ-0.5V",   500,   0,     "base"),
    ("UFS-VCCQ2-1.8V",      1800,  0,     "base"),
    ("UFS-VCC-2.5V",        2500,  0,     "base"),
]

# ---------------------------------------------------------------------------
# Clock sources
# ---------------------------------------------------------------------------

_LPDDR5X_CLOCKS = [
    ("clk-ddr-8533",         8533000000,  "",               "base"),
    ("clk-ddr-7500",         7500000000,  "",               "base"),
    ("clk-ddr-6400",         6400000000,  "",               "base"),
    ("clk-ufs-hs-g5",        23400000000, "",               "base"),
    ("clk-ufs-ref-26m",      26000000,    "clk-tcxo",       "base"),
]

# ---------------------------------------------------------------------------
# Registers — LPDDR5X mode registers and UFS
# ---------------------------------------------------------------------------

_LPDDR5X_REGISTERS = [
    ("MR1-LPDDR5X",   "0x01",  "RW",  "0x06",  "LPDDR5X-MC",
     "LPDDR5X Mode Register 1 — nWR timing, write recovery; "
     "bits[5:0]: nWR value; updated for 8533 Mbps timing requirements",
     "base"),
    ("MR18-LPDDR5X",  "0x12",  "RW",  "0x00",  "LPDDR5X-MC",
     "LPDDR5X MR18 — Write-X (WRX) entry mode control; "
     "enables Bank Subset Shutdown (BSST); bit[0]: BSST enable",
     "base"),
    ("MR30-LPDDR5X",  "0x1E",  "RW",  "0x00",  "LPDDR5X-MC",
     "LPDDR5X MR30 — on-die ECC control; bit[3:0]: ECC mode select; "
     "0b0001: byte mode ECC; 0b0011: link ECC mode",
     "base"),
    ("UFSHCI-CAP",    "0x000", "RO",  "0x00000000", "UFS-4.0-HCI",
     "UFSHCI Capabilities Register — host controller version, "
     "number of UTP task management slots, UTP transfer request slots; "
     "bits[23:16]: controller version (0x400 = UFS 4.0)",
     "base"),
    ("UFSHCI-MCQ-CFG","0x380", "RW",  "0x00000000", "UFS-4.0-HCI",
     "UFSHCI MCQ Configuration Register — enables Multi-Circular Queue mode; "
     "bit[0]: MCQ_CFG_ENABLE; bits[7:1]: number of queues (max 32); "
     "Linux kernel sets this during MCQ initialization",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_LPDDR5X_FAILURES = [
    ("FM-LPDDR5X-Timing-Violation",
     "System crash or data corruption under heavy memory load at high data rate (8533 Mbps)",
     "LPDDR5X tRCD/tRP timing parameters not updated for 8533 Mbps speed bin in MC config; "
     "or VDD2 supply drooping under peak load; "
     "verify MC timing registers match JEDEC JESD79-5B Table 62; "
     "check VDD2 ripple with oscilloscope under memtester load",
     "memory",
     "JEDEC JESD79-5B LPDDR5X specification §12 AC Electrical Characteristics",
     "base"),
    ("FM-LPDDR5X-ZQ-Calibration-Timeout",
     "dmesg: LPDDR5X ZQ calibration timeout; sporadic memory errors",
     "ZQ calibration (output impedance matching) not completing within tZQCAL window; "
     "DRAM not receiving ZQCAL command due to MC register misconfiguration; "
     "or VDDQ supply unstable during calibration; "
     "check MC ZQ calibration interval registers and VDDQ supply noise",
     "memory",
     "JEDEC JESD79-5B §14.6 ZQ Calibration; Linux drivers/memory/ ZQ handling",
     "base"),
    ("FM-LPDDR5X-Temperature-Refresh-Fail",
     "System instability at high ambient temperature (>80°C); random bit errors",
     "TCSR (Temperature Compensated Self Refresh) not programmed; "
     "DRAM requires faster refresh at elevated temperature (>85°C: tREFI/2); "
     "check MR4[2:0] temperature readout and MC refresh rate doubling logic",
     "memory",
     "JEDEC JESD79-5B §7.8 Temperature Compensated Self Refresh",
     "base"),
    ("FM-UFS4-Gear-Switch-Timeout",
     "UFS device not found after gear switch; mount fails; dmesg: 'ufshcd: gear switch timeout'",
     "UniPro PACP_PWR_CNF not received within timeout after PACP_PWR_REQ; "
     "M-PHY Gen4 PLL lock timeout at HS-G5 rate; or M-PHY termination resistance mismatch; "
     "reduce gear to HS-G4 as workaround; "
     "check M-PHY control registers and UniPro L4 attribute PA_ActiveTxDataLanes",
     "storage",
     "JEDEC JESD220F §10 M-PHY Gear Switch; Linux drivers/ufs/core/ufshcd.c",
     "base"),
    ("FM-UFS4-WriteBooster-Flush-Stall",
     "High write latency spike (>100ms) on UFS device; I/O scheduler shows queue stall",
     "Write Booster SLC buffer full; device flushing WB buffer to MLC while host I/O continues; "
     "configure I/O scheduler to respect UFS WB flush state; "
     "sysfs: /sys/class/block/sda/device/write_booster_buffer_status; "
     "reduce write burst rate or increase WB buffer size (MR57 programming)",
     "storage",
     "JEDEC JESD220F §13 Write Booster 2.0; Linux UFS sysfs documentation",
     "base"),
    ("FM-UFS4-MCQ-Submission-Error",
     "UFS MCQ queue overflow; I/O errors in dmesg: 'ufs-mcq: submission queue full'",
     "MCQ queue depth not matched to workload; or MCQ not properly initialized (MCQ_CFG_ENABLE=0); "
     "verify UFSHCI-MCQ-CFG register and queue depth via /sys/class/block/sda/queue/nr_requests; "
     "reduce I/O concurrency or increase queue depth",
     "storage",
     "Linux drivers/ufs/core/ufs-mcq.c; UFSHCI v4.0 spec §7 MCQ",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    # Components
    all_components = _LPDDR5X_COMPONENTS + _UFS4_COMPONENTS
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # Power domains
    for name, voltage_mv, current_ma, ns in _LPDDR5X_POWER_DOMAINS:
        if upsert_node(conn, "PowerDomain", {
            "name": name, "voltage_mv": voltage_mv,
            "current_ma": current_ma, "namespace": ns,
        }):
            inserted += 1

    # Clock sources
    for name, freq_hz, parent_clk, ns in _LPDDR5X_CLOCKS:
        if upsert_node(conn, "ClockSource", {
            "name": name, "frequency_hz": freq_hz,
            "parent_clk": parent_clk, "namespace": ns,
        }):
            inserted += 1

    # Registers
    for name, addr, access, reset, component, desc, ns in _LPDDR5X_REGISTERS:
        if upsert_node(conn, "Register", {
            "name": name, "address": addr, "access_type": access,
            "reset_value": reset, "component": component,
            "namespace": ns,
        }):
            inserted += 1

    # Failure modes
    for name, symptom, root_cause, affected_domain, source, ns in _LPDDR5X_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # LPDDR5X MC → channels
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="LPDDR5X-MC", dst_name="LPDDR5X-Channel-A")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="LPDDR5X-MC", dst_name="LPDDR5X-Channel-B")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="LPDDR5X-MC", dst_name="LPDDR5X-PHY")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="LPDDR5X-BSST", dst_name="LPDDR5X-MC")

    # UFS 4.0 stack
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-4.0-HCI", dst_name="UFS-4.0-UniPro")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-4.0-UniPro", dst_name="UFS-4.0-M-PHY-Gen4")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-4.0-WriteBooster", dst_name="UFS-4.0-HCI")

    # Linux drivers → hardware
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-ufshcd", dst_name="UFS-4.0-HCI")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-ufs-mcq", dst_name="UFS-4.0-HCI")

    # Link to existing LPDDR5/UFS from linux-platform-devices.py
    create_rel(conn, "SHARED_WITH", "Component", "Component",
               src_name="LPDDR5X-MC", dst_name="LPDDR5")
    create_rel(conn, "SHARED_WITH", "Component", "Component",
               src_name="UFS-4.0-HCI", dst_name="UFS")

    # Power domain → component supplies
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="LPDDR5X-VDD1-1.8V", dst_name="LPDDR5X-MC")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="LPDDR5X-VDD2-1.05V", dst_name="LPDDR5X-PHY")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="UFS-VCC-2.5V", dst_name="UFS-4.0-HCI")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="UFS-VCCQ2-1.8V", dst_name="UFS-4.0-M-PHY-Gen4")

    # Clock → component
    create_rel(conn, "CLOCKS", "ClockSource", "Component",
               src_name="clk-ddr-8533", dst_name="LPDDR5X-MC")
    create_rel(conn, "CLOCKS", "ClockSource", "Component",
               src_name="clk-ddr-7500", dst_name="LPDDR5X-MC")
    create_rel(conn, "CLOCKS", "ClockSource", "Component",
               src_name="clk-ufs-hs-g5", dst_name="UFS-4.0-M-PHY-Gen4")
    create_rel(conn, "CLOCKS", "ClockSource", "Component",
               src_name="clk-ufs-ref-26m", dst_name="UFS-4.0-HCI")

    # Clock dependencies
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "ClockSource",
               src_name="LPDDR5X-MC", dst_name="clk-ddr-8533")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "ClockSource",
               src_name="UFS-4.0-HCI", dst_name="clk-ufs-ref-26m")

    # Failure modes → root components
    for fm_name, comp_name in [
        ("FM-LPDDR5X-Timing-Violation",        "LPDDR5X-MC"),
        ("FM-LPDDR5X-ZQ-Calibration-Timeout",  "LPDDR5X-PHY"),
        ("FM-LPDDR5X-Temperature-Refresh-Fail", "LPDDR5X-MC"),
        ("FM-UFS4-Gear-Switch-Timeout",         "UFS-4.0-M-PHY-Gen4"),
        ("FM-UFS4-WriteBooster-Flush-Stall",    "UFS-4.0-WriteBooster"),
        ("FM-UFS4-MCQ-Submission-Error",        "UFS-4.0-HCI"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    # Power domain affects
    create_rel(conn, "AFFECTS_IF_REMOVED", "PowerDomain", "Component",
               src_name="LPDDR5X-VDD2-1.05V", dst_name="LPDDR5X-PHY")
    create_rel(conn, "AFFECTS_IF_REMOVED", "PowerDomain", "Component",
               src_name="UFS-VCC-2.5V", dst_name="UFS-4.0-HCI")

    print(f"[linux-lpddr5x-ufs4] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
