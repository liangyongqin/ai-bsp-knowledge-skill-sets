"""
LPDDR6 memory subsystem — seed knowledge ingestion.

Adds LPDDR6 (JEDEC JESD209-6, published July 9, 2025) components that extend
the existing LPDDR5/LPDDR5X coverage. LPDDR6 is expected in products starting
2026 for mobile + edge AI workloads.

Key differences vs LPDDR5X (relevant for BSP bring-up):
  - 4 × 24-bit sub-channels (vs LPDDR5 4 × 16-bit)
  - 10,667 – 14,400 MT/s data rates, 28.5 – 38.4 GB/s effective bandwidth
  - On-die ECC mandatory (was optional on LPDDR5)
  - Command/address parity checking (new)
  - Memory-region isolation (new security feature)
  - Lower VDD2 voltage; two VDD2 supplies mandated

Sources:
  - JEDEC JESD209-6 LPDDR6 Standard (public press release + product brief)
    https://www.jedec.org/standards-documents/docs/jesd209-6
  - JEDEC press release 2025-07-09 "JEDEC Releases New LPDDR6 Standard"
  - JESD209-6 public specification summary (bandwidth, sub-channel, ECC)

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
# Components — LPDDR6 memory subsystem
# ---------------------------------------------------------------------------

_LPDDR6_COMPONENTS = [
    ("LPDDR6-MC",            "memory-controller",  "JEDEC",
     "LPDDR6 Memory Controller — JEDEC JESD209-6 (Jul 2025); data rates "
     "10667/12000/14400 MT/s; four 24-bit sub-channels per channel (vs LPDDR5 "
     "4x16-bit); 28.5-38.4 GB/s effective bandwidth; mandatory on-die ECC; "
     "command/address parity checking; memory region isolation (MRI) for "
     "security-sensitive workloads (TrustZone / REE partitioning)",
     "base"),
    ("LPDDR6-PHY",           "phy",                "JEDEC",
     "LPDDR6 PHY — differential CA signaling; DQ forwarded clock (FWDCK); "
     "CA parity (per-sub-channel); ZQ calibration per sub-channel; link ECC "
     "(SECDED) on DQ + metadata lanes; PHY training extended for 14.4 GT/s "
     "signal integrity; temperature-compensated self-refresh retained",
     "base"),
    ("LPDDR6-SubChannel",    "memory-sub-channel", "JEDEC",
     "LPDDR6 24-bit sub-channel — new granularity unit in LPDDR6; four per "
     "channel; each sub-channel can independently enter self-refresh or "
     "power-down; enables higher concurrency vs LPDDR5 16-bit channels; "
     "improves random-access latency on AI inference workloads",
     "base"),
    ("LPDDR6-ODECC",         "memory-feature",     "JEDEC",
     "LPDDR6 On-Die ECC (ODECC) — MANDATORY per JESD209-6 (was optional on "
     "LPDDR5); SECDED per codeword; error counters exposed via mode registers; "
     "driver must scrape error counts into Linux EDAC subsystem "
     "(drivers/edac/); persistent uncorrectable errors trigger page offlining",
     "base"),
    ("LPDDR6-CAPAR",         "memory-feature",     "JEDEC",
     "LPDDR6 Command/Address Parity (CA Parity) — NEW in JESD209-6; detects "
     "command-link errors that prior generations silently corrupted; MC must "
     "replay commands on parity error; excessive CA-parity errors indicate "
     "PDN noise or PCB SI degradation",
     "base"),
    ("LPDDR6-MRI",           "memory-feature",     "JEDEC",
     "LPDDR6 Memory Region Isolation (MRI) — NEW in JESD209-6; hardware-"
     "enforced access control on DRAM regions; used by TrustZone / REE to "
     "prevent Normal-World access to Secure-World pages; MC programs MRI table "
     "at boot; violations raise DRAM access fault to EL3",
     "base"),
    ("LPDDR6-BSST",          "power-feature",      "JEDEC",
     "LPDDR6 Bank-Subset Self-Refresh — finer granularity than LPDDR5X BSST; "
     "per-sub-channel self-refresh entry; auto-entry after idle window "
     "programmable via MR; typical mobile idle power delta vs full-active: "
     "–45 mW per channel (vendor white-paper estimates, to be verified on SoC)",
     "base"),
]

# ---------------------------------------------------------------------------
# Power domains
# ---------------------------------------------------------------------------

_LPDDR6_POWER_DOMAINS = [
    ("LPDDR6-VDD1-1.8V",     1800,  0,  "base"),
    ("LPDDR6-VDD2H-1.00V",   1000,  0,  "base"),
    ("LPDDR6-VDD2L-0.95V",    950,  0,  "base"),
    ("LPDDR6-VDDQ-0.4V",      400,  0,  "base"),
]

# ---------------------------------------------------------------------------
# Clock sources
# ---------------------------------------------------------------------------

_LPDDR6_CLOCKS = [
    ("clk-ddr-14400",        14400000000,  "",  "base"),
    ("clk-ddr-12000",        12000000000,  "",  "base"),
    ("clk-ddr-10667",        10667000000,  "",  "base"),
]

# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------

_LPDDR6_REGISTERS = [
    ("MR30-LPDDR6",   "0x1E",  "RW",  "0x01",  "LPDDR6-MC",
     "LPDDR6 MR30 — On-Die ECC (ODECC) control; bit[0]: ODECC enable (reset=1, "
     "mandatory); bits[3:1]: ECC reporting mode (0=off, 1=count only, 2=log); "
     "Linux EDAC driver reads MR30 error counters via DRAM controller",
     "base"),
    ("MR31-LPDDR6",   "0x1F",  "RW",  "0x00",  "LPDDR6-MC",
     "LPDDR6 MR31 — CA parity control; bit[0]: CAPAR enable; bit[1]: "
     "replay-on-error enable; bit[2]: parity-error interrupt to host; "
     "bits[7:4]: CAPAR error counter (cleared on read)",
     "base"),
    ("MR40-LPDDR6",   "0x28",  "RW",  "0x00",  "LPDDR6-MC",
     "LPDDR6 MR40 — Memory Region Isolation (MRI) control; bit[0]: MRI enable; "
     "bits[7:4]: number of isolation regions (up to 16); programmed by "
     "Secure-World firmware before Normal-World DRAM access",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_LPDDR6_FAILURES = [
    ("FM-LPDDR6-ODECC-Uncorrectable",
     "kernel panic: 'EDAC DRAM: Uncorrectable ECC error, offlining page'",
     "LPDDR6 on-die ECC detected an uncorrectable double-bit error; check "
     "VDD2H/VDD2L ripple under worst-case load; verify DRAM temperature "
     "(MR4 readout) is not >85°C without TCSR active; persistent UEs on "
     "same sub-channel indicate dying DRAM die — schedule board RMA",
     "memory",
     "JEDEC JESD209-6 §9 On-Die ECC; Linux drivers/edac/edac_mc.c",
     "base"),
    ("FM-LPDDR6-CAPAR-Storm",
     "dmesg: 'LPDDR6 MC: CA parity error count 1024 in 1s; replaying'",
     "Command/Address parity error burst; root-cause options: PDN (Power "
     "Distribution Network) ripple on VDD1 under CPU DVFS transient, PCB "
     "impedance discontinuity on CA lanes, or CA slew-rate misprogrammed in "
     "MC training. Verify MR31 error counter; scope VDD1 during DVFS ramp",
     "memory",
     "JEDEC JESD209-6 §10.3 CA Parity; Linux drivers/memory/ integration",
     "base"),
    ("FM-LPDDR6-MRI-Access-Fault",
     "EL3 abort: 'DRAM access fault, VA=0x... MRI region=2, op=Normal-World-write'",
     "Normal-World (Linux kernel or userspace) attempted write to a DRAM "
     "region reserved for Secure-World; caused by incorrect MRI programming "
     "at boot (ATF BL2 stage) or Linux allocator overlapping a reserved-memory "
     "range; cross-check device-tree /reserved-memory ranges vs ATF MRI table",
     "memory",
     "JEDEC JESD209-6 §11 Memory Region Isolation; ARM Trusted Firmware docs",
     "base"),
    ("FM-LPDDR6-SubChannel-Refresh-Imbalance",
     "performance regression on memory-heavy workloads after LPDDR6 enablement",
     "One sub-channel entering self-refresh more aggressively than others due "
     "to traffic-pattern skew; MC per-sub-channel idle-window threshold "
     "misprogrammed; verify MR programming for all 4 sub-channels matches; "
     "reduce BSST aggressiveness if inference workload is sensitive to exit "
     "latency",
     "memory",
     "JEDEC JESD209-6 §7 Power States; vendor BSP integration guides",
     "base"),
    ("FM-LPDDR6-PHY-Training-Fail",
     "bootloader hang: 'LPDDR6 PHY training failed at 14.4 GT/s; fallback to 12.0 GT/s'",
     "PHY read/write training cannot close eye margin at 14400 MT/s; causes: "
     "PCB trace-length mismatch across 24-bit sub-channel lanes, ZQ resistor "
     "out of spec (240Ω ±1%), VDD2H/VDD2L delta exceeding JEDEC tolerance. "
     "Bootloader auto-fallback to next-lower speed bin is expected recovery; "
     "audit PCB + PMIC bring-up for volume production",
     "memory",
     "JEDEC JESD209-6 §12 PHY Training; vendor bootloader LPDDR init flow",
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
    for name, ctype, vendor, desc, ns in _LPDDR6_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # Power domains
    for name, voltage_mv, current_ma, ns in _LPDDR6_POWER_DOMAINS:
        if upsert_node(conn, "PowerDomain", {
            "name": name, "voltage_mv": voltage_mv,
            "current_ma": current_ma, "namespace": ns,
        }):
            inserted += 1

    # Clock sources
    for name, freq_hz, parent_clk, ns in _LPDDR6_CLOCKS:
        if upsert_node(conn, "ClockSource", {
            "name": name, "frequency_hz": freq_hz,
            "parent_clk": parent_clk, "namespace": ns,
        }):
            inserted += 1

    # Registers
    for name, addr, access, reset, component, desc, ns in _LPDDR6_REGISTERS:
        if upsert_node(conn, "Register", {
            "name": name, "address": addr, "access_type": access,
            "reset_value": reset, "component": component,
            "namespace": ns,
        }):
            inserted += 1

    # Failure modes
    for name, symptom, root_cause, affected_domain, source, ns in _LPDDR6_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Internal topology
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="LPDDR6-MC", dst_name="LPDDR6-PHY")
    for sub in ("LPDDR6-SubChannel",):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="LPDDR6-MC", dst_name=sub)
    for feat in ("LPDDR6-ODECC", "LPDDR6-CAPAR", "LPDDR6-MRI", "LPDDR6-BSST"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=feat, dst_name="LPDDR6-MC")

    # Generational link — LPDDR5X → LPDDR6
    create_rel(conn, "SHARED_WITH", "Component", "Component",
               src_name="LPDDR6-MC", dst_name="LPDDR5X-MC")

    # Power supplies
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="LPDDR6-VDD1-1.8V",   dst_name="LPDDR6-MC")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="LPDDR6-VDD2H-1.00V", dst_name="LPDDR6-PHY")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="LPDDR6-VDD2L-0.95V", dst_name="LPDDR6-PHY")
    create_rel(conn, "SUPPLIES", "PowerDomain", "Component",
               src_name="LPDDR6-VDDQ-0.4V",   dst_name="LPDDR6-SubChannel")

    # Clock → controller
    for clk in ("clk-ddr-14400", "clk-ddr-12000", "clk-ddr-10667"):
        create_rel(conn, "CLOCKS", "ClockSource", "Component",
                   src_name=clk, dst_name="LPDDR6-MC")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "ClockSource",
               src_name="LPDDR6-MC", dst_name="clk-ddr-14400")

    # Failure modes → components
    for fm_name, comp_name in [
        ("FM-LPDDR6-ODECC-Uncorrectable",           "LPDDR6-ODECC"),
        ("FM-LPDDR6-CAPAR-Storm",                   "LPDDR6-CAPAR"),
        ("FM-LPDDR6-MRI-Access-Fault",              "LPDDR6-MRI"),
        ("FM-LPDDR6-SubChannel-Refresh-Imbalance",  "LPDDR6-SubChannel"),
        ("FM-LPDDR6-PHY-Training-Fail",             "LPDDR6-PHY"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    # Power domain removal impact
    create_rel(conn, "AFFECTS_IF_REMOVED", "PowerDomain", "Component",
               src_name="LPDDR6-VDD2H-1.00V", dst_name="LPDDR6-PHY")
    create_rel(conn, "AFFECTS_IF_REMOVED", "PowerDomain", "Component",
               src_name="LPDDR6-VDD1-1.8V",   dst_name="LPDDR6-MC")

    print(f"[jedec-lpddr6] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
