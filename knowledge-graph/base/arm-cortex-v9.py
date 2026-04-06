"""
ARM Cortex ARMv9 generation seed — open-source knowledge ingestion.

Adds newer-generation ARM CPU cores not covered by arm-cpu-cluster.py:
  - Cortex-A520 (efficiency, ARMv9.2, in-order, merged-core)
  - Cortex-A720 (performance, ARMv9.2, out-of-order)
  - Cortex-A725 (performance, ARMv9.2, successor to A720)
  - Cortex-X4 (prime, ARMv9.2, 8-wide decode)
  - Cortex-X925 (prime, ARMv9.2, 10-wide decode)
  - DSU-120 (DynamIQ Shared Unit, successor to DSU-110)

Sources:
  - ARM Cortex-A520 TRM (ARM DDI 0621) — developer.arm.com
  - ARM Cortex-A720 TRM (ARM DDI 102530) — developer.arm.com
  - ARM Cortex-A725 TRM (ARM DDI 107652) — developer.arm.com
  - ARM Cortex-X4 TRM (ARM DDI 102484) — developer.arm.com
  - ARM Cortex-X925 TRM (ARM DDI 102807) — developer.arm.com
  - ARM DSU-120 TRM — developer.arm.com
  - ARM A-Profile Architecture Developments 2024 blog post

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
# Components — Cortex-A520 (efficiency core, ARMv9.2)
# ---------------------------------------------------------------------------

_A520_COMPONENTS = [
    ("Cortex-A520-PE",      "cpu",         "ARM",
     "ARM Cortex-A520 — ARMv9.2-A, in-order, merged-core microarchitecture (2 cores/complex), "
     "AArch64-only, SVE2, 64KB L1I + 64KB L1D; optimized for power efficiency",
     "base"),
    ("Cortex-A520-L1I",     "cache",       "ARM",
     "Cortex-A520 L1 instruction cache — 64KB, 4-way, 64-byte cacheline",
     "base"),
    ("Cortex-A520-L1D",     "cache",       "ARM",
     "Cortex-A520 L1 data cache — 64KB, 4-way, 64-byte cacheline",
     "base"),
    ("Cortex-A520-L2",      "cache",       "ARM",
     "Cortex-A520 shared L2 cache — 128KB–512KB per merged-core complex, 8-way",
     "base"),
    ("Cortex-A520-PMU",     "pmu",         "ARM",
     "Cortex-A520 PMU — 6 programmable event counters, ARMv9 PMU extensions, BRBE support",
     "base"),
    ("Cortex-A520-ETM",     "trace",       "ARM",
     "Cortex-A520 ETM v4.6 — ETE (Embedded Trace Extension), TRBE support for self-hosted trace",
     "base"),
    ("Cortex-A520-Cluster", "cpu-cluster", "ARM",
     "Cortex-A520 efficiency cluster — up to 4 cores (2 merged-core complexes), "
     "DynamIQ via DSU-120; replaces A510 in TCS24 configurations",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-A720 (performance core, ARMv9.2)
# ---------------------------------------------------------------------------

_A720_COMPONENTS = [
    ("Cortex-A720-PE",      "cpu",         "ARM",
     "ARM Cortex-A720 — ARMv9.2-A, out-of-order, 5-wide decode, AArch64-only, "
     "SVE2, MTE (Memory Tagging Extension), 64KB L1I + 64KB L1D",
     "base"),
    ("Cortex-A720-L1I",     "cache",       "ARM",
     "Cortex-A720 L1 instruction cache — 64KB, 4-way, 64-byte cacheline",
     "base"),
    ("Cortex-A720-L1D",     "cache",       "ARM",
     "Cortex-A720 L1 data cache — 64KB, 4-way, write-back, MOESI",
     "base"),
    ("Cortex-A720-L2",      "cache",       "ARM",
     "Cortex-A720 private L2 — 256KB–512KB, 8-way, write-back",
     "base"),
    ("Cortex-A720-PMU",     "pmu",         "ARM",
     "Cortex-A720 PMU — 6 programmable counters, BRBE, Topdown L2 events",
     "base"),
    ("Cortex-A720-Cluster", "cpu-cluster", "ARM",
     "Cortex-A720 performance cluster — up to 4 cores, DynamIQ via DSU-120",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-A725 (premium efficiency, ARMv9.2)
# ---------------------------------------------------------------------------

_A725_COMPONENTS = [
    ("Cortex-A725-PE",      "cpu",         "ARM",
     "ARM Cortex-A725 — ARMv9.2-A, out-of-order, 5-wide decode, AArch64-only, "
     "SVE2, MTE, 35% perf/efficiency improvement over A720; optimized for 3nm process",
     "base"),
    ("Cortex-A725-L1I",     "cache",       "ARM",
     "Cortex-A725 L1 instruction cache — 64KB, 4-way, 64-byte cacheline",
     "base"),
    ("Cortex-A725-L1D",     "cache",       "ARM",
     "Cortex-A725 L1 data cache — 64KB, 4-way, write-back",
     "base"),
    ("Cortex-A725-L2",      "cache",       "ARM",
     "Cortex-A725 private L2 — 256KB–1MB, 8-way, write-back; larger than A720 L2",
     "base"),
    ("Cortex-A725-PMU",     "pmu",         "ARM",
     "Cortex-A725 PMU — 6 programmable counters, BRBE, enhanced Topdown metrics",
     "base"),
    ("Cortex-A725-Cluster", "cpu-cluster", "ARM",
     "Cortex-A725 premium performance cluster — up to 4 cores, DynamIQ via DSU-120; "
     "replaces A720 in TCS24 flagship SoCs",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-X4 (prime core, ARMv9.2)
# ---------------------------------------------------------------------------

_X4_COMPONENTS = [
    ("Cortex-X4-PE",        "cpu",         "ARM",
     "ARM Cortex-X4 — ARMv9.2-A, out-of-order, 8-wide decode+dispatch, AArch64-only, "
     "SVE2, MTE; 64KB L1I + 64KB L1D, up to 2MB private L2",
     "base"),
    ("Cortex-X4-L2",        "cache",       "ARM",
     "Cortex-X4 private L2 — 512KB–2MB, 16-way, write-back, hardware prefetcher",
     "base"),
    ("Cortex-X4-PMU",       "pmu",         "ARM",
     "Cortex-X4 PMU — 6+ programmable counters, BRBE, full Topdown L2 support",
     "base"),
    ("Cortex-X4-Cluster",   "cpu-cluster", "ARM",
     "Cortex-X4 prime cluster — 1–2 cores, DynamIQ via DSU-120; peak single-thread IPC",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-X925 (prime core, ARMv9.2, 2024)
# ---------------------------------------------------------------------------

_X925_COMPONENTS = [
    ("Cortex-X925-PE",      "cpu",         "ARM",
     "ARM Cortex-X925 'Blackhawk' — ARMv9.2-A, out-of-order, 10-wide decode+dispatch, "
     "AArch64-only, SVE2, MTE; 64KB L1I + 64KB L1D with 2x L1I bandwidth; up to 3MB L2; "
     "optimized for 3nm, clocks >3.6 GHz",
     "base"),
    ("Cortex-X925-L2",      "cache",       "ARM",
     "Cortex-X925 private L2 — up to 3MB, 16-way, write-back; largest L2 in Cortex family",
     "base"),
    ("Cortex-X925-PMU",     "pmu",         "ARM",
     "Cortex-X925 PMU — 8 programmable counters, BRBE, full Topdown L2, AMU v1.1",
     "base"),
    ("Cortex-X925-Cluster", "cpu-cluster", "ARM",
     "Cortex-X925 prime cluster — typically 1 core, DynamIQ via DSU-120; "
     "flagship single-thread perf, 46% better than X4-based clusters in combined AI/gaming",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — DSU-120 (DynamIQ Shared Unit, successor to DSU-110)
# ---------------------------------------------------------------------------

_DSU120_COMPONENTS = [
    ("DSU-120",             "dsu",         "ARM",
     "ARM DynamIQ Shared Unit DSU-120 — L3 cache 2–16MB, supports A520+A725+X925 clusters, "
     "CHI interface to SoC interconnect, MPAM support, ECC on L3",
     "base"),
    ("DSU-120-L3",          "cache",       "ARM",
     "DSU-120 L3 cache — 2–16MB configurable, 16-way, MOESI, ECC; "
     "shared across all DynamIQ CPUs in the cluster complex",
     "base"),
    ("DSU-120-PMU",         "pmu",         "ARM",
     "DSU-120 PMU — cluster-level events: L3 hit/miss, snoop filter activity, CHI transactions",
     "base"),
    ("DSU-120-power-ctrl",  "power",       "ARM",
     "DSU-120 power controller — per-core/per-cluster power gating, PSCI integration, "
     "improved power-down latency vs DSU-110",
     "base"),
]

# ---------------------------------------------------------------------------
# ARMv9 architecture feature components
# ---------------------------------------------------------------------------

_ARMV9_FEATURES = [
    ("ARMv9-SVE2",          "isa-extension", "ARM",
     "Scalable Vector Extension v2 (SVE2) — mandatory in ARMv9, variable-length SIMD (128–2048 bit), "
     "integer/crypto/bit-manipulation ops beyond SVE; replaces optional NEON for ARMv9 cores",
     "base"),
    ("ARMv9-MTE",           "isa-extension", "ARM",
     "Memory Tagging Extension (MTE) — hardware-assisted memory safety, 4-bit tag per 16-byte granule, "
     "detects use-after-free and buffer overflow at hardware speed; ARMv8.5/ARMv9 feature",
     "base"),
    ("ARMv9-BRBE",          "isa-extension", "ARM",
     "Branch Record Buffer Extension (BRBE) — hardware branch recording without external trace, "
     "low-overhead profiling for perf tool; available on A720+, X4+, X925 cores",
     "base"),
    ("ARMv9-ETE",           "trace",       "ARM",
     "Embedded Trace Extension (ETE) — successor to ETM v4, ARMv9 trace architecture, "
     "supports TRBE (Trace Buffer Extension) for self-hosted trace to memory",
     "base"),
    ("ARMv9-TRBE",          "trace",       "ARM",
     "Trace Buffer Extension (TRBE) — self-hosted trace buffer in system memory, "
     "no external trace port needed; integrates with perf and CoreSight",
     "base"),
    ("ARMv9-AMU",           "pmu",         "ARM",
     "Activity Monitors Unit (AMU) v1.1 — always-on counters for CPU frequency, "
     "cycle count, instruction retired; used by EAS for accurate capacity estimation",
     "base"),
    ("ARMv9-MPAM",          "qos",         "ARM",
     "Memory Partitioning and Monitoring (MPAM) — cache/memory bandwidth allocation per partition, "
     "QoS enforcement in DSU L3 and interconnect; supported by DSU-120 and CMN-700",
     "base"),
    ("ARMv9-RME",           "security",    "ARM",
     "Realm Management Extension (RME) — fourth security state (Realm), "
     "hardware isolation for confidential computing; CCA (Confidential Compute Architecture) foundation",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_V9_INTERRUPTS = [
    ("IRQ-PMU-A520",   "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-A720",   "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-A725",   "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-X4",     "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-X925",   "PPI", 23, "level-high", "base"),
    ("IRQ-TRBE-A720",  "PPI", 22, "level-high", "base"),
    ("IRQ-TRBE-X925",  "PPI", 22, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_V9_FAILURES = [
    ("FM-MTE-Tag-Check-Fault",
     "MTE tag check fault: SEGV_MTESERR or SEGV_MTEAERR; process killed or logged",
     "Buffer overflow or use-after-free detected by MTE hardware tag mismatch; "
     "verify allocation/deallocation patterns and pointer arithmetic",
     "memory",
     "ARM MTE documentation / Android MTE deployment guide",
     "base"),
    ("FM-SVE2-SIGILL",
     "SIGILL on SVE2 instruction; process crashes on ARMv9 target",
     "Kernel CONFIG_ARM64_SVE not enabled or SVE vector length not configured in DT; "
     "check /proc/sys/abi/sve_default_vector_length",
     "cpu",
     "Linux Documentation/arm64/sve.rst",
     "base"),
    ("FM-TRBE-Overflow",
     "TRBE buffer full; trace data lost; perf reports incomplete trace",
     "TRBE buffer size too small for trace bandwidth; increase buffer or reduce trace scope; "
     "check /sys/bus/event_source/devices/arm_trbe/",
     "debug",
     "Linux Documentation/trace/coresight/trbe.rst",
     "base"),
    ("FM-MPAM-Partition-Starvation",
     "Workload in MPAM partition gets unexpectedly low cache/memory bandwidth",
     "MPAM partition configuration too restrictive; L3 cache portion or memory bandwidth "
     "cap set below workload requirement; check resctrl mount",
     "qos",
     "Linux Documentation/arch/arm64/mpam.rst",
     "base"),
    ("FM-DSU120-L3-ECC-Error",
     "DSU-120 L3 ECC correctable/uncorrectable error; kernel EDAC or RAS report",
     "L3 SRAM bit flip due to voltage droop or aging; correctable errors are informational, "
     "uncorrectable triggers machine check; verify VDD_CPU supply stability",
     "memory",
     "ARM DSU-120 TRM §6 (RAS)",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _A520_COMPONENTS + _A720_COMPONENTS + _A725_COMPONENTS +
        _X4_COMPONENTS + _X925_COMPONENTS +
        _DSU120_COMPONENTS + _ARMV9_FEATURES
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _V9_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _V9_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Clusters → DSU-120
    for cluster in ("Cortex-A520-Cluster", "Cortex-A720-Cluster", "Cortex-A725-Cluster",
                    "Cortex-X4-Cluster", "Cortex-X925-Cluster"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=cluster, dst_name="DSU-120")

    # PE → private L2
    for pe, l2 in [
        ("Cortex-A520-PE", "Cortex-A520-L2"),
        ("Cortex-A720-PE", "Cortex-A720-L2"),
        ("Cortex-A725-PE", "Cortex-A725-L2"),
        ("Cortex-X4-PE",   "Cortex-X4-L2"),
        ("Cortex-X925-PE", "Cortex-X925-L2"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l2)

    # PE → L1 caches
    for pe, l1i, l1d in [
        ("Cortex-A520-PE", "Cortex-A520-L1I", "Cortex-A520-L1D"),
        ("Cortex-A720-PE", "Cortex-A720-L1I", "Cortex-A720-L1D"),
        ("Cortex-A725-PE", "Cortex-A725-L1I", "Cortex-A725-L1D"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l1i)
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l1d)

    # DSU-120 internal
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-120", dst_name="DSU-120-L3")

    # PMU → linux perf
    for pmu in ("Cortex-A520-PMU", "Cortex-A720-PMU", "Cortex-A725-PMU",
                "Cortex-X4-PMU", "Cortex-X925-PMU", "DSU-120-PMU"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pmu, dst_name="linux-perf-arm")

    # ETM → ETE → TRBE chain
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Cortex-A520-ETM", dst_name="ARMv9-ETE")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9-ETE", dst_name="ARMv9-TRBE")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9-ETE", dst_name="CoreSight-funnel")

    # DSU-120 power → PSCI
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-120-power-ctrl", dst_name="arm-psci")

    # AMU → schedutil for capacity estimation
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9-AMU", dst_name="sched-util-arm")

    # MPAM → DSU-120 L3 partitioning
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9-MPAM", dst_name="DSU-120-L3")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-MTE-Tag-Check-Fault",      "ARMv9-MTE"),
        ("FM-SVE2-SIGILL",              "ARMv9-SVE2"),
        ("FM-TRBE-Overflow",            "ARMv9-TRBE"),
        ("FM-MPAM-Partition-Starvation", "ARMv9-MPAM"),
        ("FM-DSU120-L3-ECC-Error",      "DSU-120-L3"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-cortex-v9] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
