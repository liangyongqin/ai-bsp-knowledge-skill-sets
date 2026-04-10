"""
ARM 2024 Client Compute Subsystem (CSS v2) — seed knowledge ingestion.

Sources:
  - ARM Cortex-X925 TRM (ARM DDI 0614, r0p2, publicly available)
  - ARM Cortex-A725 TRM (ARM DDI 0612, publicly available)
  - ARM Cortex-A520 TRM (ARM DDI 0598, publicly available)
  - ARM DSU-120 TRM (ARM DDI 0616, publicly available)
  - ARM Immortalis-G925 product page (arm.com)
  - Chips and Cheese analysis: "Arm's Cortex-X925: Reaching Desktop Performance"
  - WikiChip Fuse: "Arm Unveils 2024 Compute Platform"

Covers:
  - Cortex-X925 (prime core): ARMv9.2-A, 10-wide decode, 3MB L2
  - Cortex-A725 (performance core): ARMv9.2-A, 5-wide decode, 1MB L2
  - Cortex-A520 (efficiency core): ARMv9.2-A, in-order, 512KB L2
  - DSU-120: up to 14 cores, up to 32MB L3, dynamic cache slice power gating
  - Immortalis-G925 GPU: 10th gen Mali architecture
  - Cache hierarchy, power domains, failure modes

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

DEFAULT_DB_PATH = os.path.join(_HERE, "bsp_base.db")

# ---------------------------------------------------------------------------
# Components — Cortex-X925 (prime core, ARMv9.2-A)
# ---------------------------------------------------------------------------

_X925_COMPONENTS = [
    ("Cortex-X925-PE", "cpu", "ARM",
     "ARM Cortex-X925 r0p2 — ARMv9.2-A, 10-wide decode, out-of-order; "
     "64KB L1I + 64KB L1D; 4-cycle L1 latency; 4x128-bit read/write paths; "
     "SVE2, SME, MPAM; 3nm process target",
     "base"),
    ("Cortex-X925-L1I", "cache", "ARM",
     "Cortex-X925 L1 instruction cache — 64KB, 4-way, 64-byte cacheline, VIPT",
     "base"),
    ("Cortex-X925-L1D", "cache", "ARM",
     "Cortex-X925 L1 data cache — 64KB, 4-way, 64-byte cacheline; "
     "4x128-bit read paths, 4x128-bit write paths; 64B/cycle load bandwidth",
     "base"),
    ("Cortex-X925-L2", "cache", "ARM",
     "Cortex-X925 private L2 — 2MB (8-way) or 3MB (12-way) configurable; "
     "write-back, ECC protected; hardware prefetcher with stride/stream detection",
     "base"),
    ("Cortex-X925-PMU", "pmu", "ARM",
     "Cortex-X925 PMU — 8 programmable event counters + CCNT; "
     "BRBE (Branch Record Buffer Extension); Topdown L2 metrics; SPE v1.4",
     "base"),
    ("Cortex-X925-ETM", "trace", "ARM",
     "Cortex-X925 Embedded Trace Macrocell v4.6 — instruction trace, "
     "branch trace, timestamp; ETE (Embedded Trace Extension)",
     "base"),
    ("Cortex-X925-Cluster", "cpu-cluster", "ARM",
     "Cortex-X925 prime cluster — 1-2 core DynamIQ via DSU-120; "
     "highest single-thread IPC for bursty workloads",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-A725 (performance core, ARMv9.2-A)
# ---------------------------------------------------------------------------

_A725_COMPONENTS = [
    ("Cortex-A725-PE", "cpu", "ARM",
     "ARM Cortex-A725 — ARMv9.2-A, 5-wide decode, out-of-order; "
     "64KB L1I + 64KB L1D; SVE2, MPAM; replaces A720 with 35% energy reduction",
     "base"),
    ("Cortex-A725-L1I", "cache", "ARM",
     "Cortex-A725 L1 instruction cache — 64KB, 4-way, 64-byte cacheline",
     "base"),
    ("Cortex-A725-L1D", "cache", "ARM",
     "Cortex-A725 L1 data cache — 64KB, 4-way, write-back",
     "base"),
    ("Cortex-A725-L2", "cache", "ARM",
     "Cortex-A725 private L2 — 512KB or 1MB configurable, 8-way, "
     "write-back, ECC protected",
     "base"),
    ("Cortex-A725-PMU", "pmu", "ARM",
     "Cortex-A725 PMU — 6 programmable event counters + CCNT; "
     "Topdown metrics support; SPE v1.3",
     "base"),
    ("Cortex-A725-Cluster", "cpu-cluster", "ARM",
     "Cortex-A725 performance cluster — typically 3-4 cores in DSU-120; "
     "balanced perf/power for sustained workloads",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-A520 (efficiency core, ARMv9.2-A)
# ---------------------------------------------------------------------------

_A520_COMPONENTS = [
    ("Cortex-A520-PE", "cpu", "ARM",
     "ARM Cortex-A520 — ARMv9.2-A, in-order pipeline, 4-stage decode; "
     "64KB L1I + 64KB L1D; SVE2 support; replaces A510 with 22% perf increase",
     "base"),
    ("Cortex-A520-L1I", "cache", "ARM",
     "Cortex-A520 L1 instruction cache — 64KB, 4-way, VIPT",
     "base"),
    ("Cortex-A520-L1D", "cache", "ARM",
     "Cortex-A520 L1 data cache — 64KB, 4-way, VIPT, write-through or write-back",
     "base"),
    ("Cortex-A520-L2", "cache", "ARM",
     "Cortex-A520 private L2 — 128KB-512KB configurable, 8-way, ECC protected",
     "base"),
    ("Cortex-A520-PMU", "pmu", "ARM",
     "Cortex-A520 PMU — 4 programmable event counters + CCNT",
     "base"),
    ("Cortex-A520-Cluster", "cpu-cluster", "ARM",
     "Cortex-A520 efficiency cluster — typically 4 cores in DSU-120; "
     "lowest power for background tasks",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — DSU-120 (DynamIQ Shared Unit)
# ---------------------------------------------------------------------------

_DSU120_COMPONENTS = [
    ("DSU-120", "dsu", "ARM",
     "ARM DynamIQ Shared Unit DSU-120 — supports up to 14 heterogeneous cores; "
     "L3 cache up to 32MB; dynamic cache slice power gating (stall-free); "
     "CHI interconnect; replaces DSU-110 for 2024 CSS",
     "base"),
    ("DSU-120-L3", "cache", "ARM",
     "DSU-120 L3 cache — up to 32MB, 16-way, MOESI, ECC; "
     "individual cache slices can be powered on/off without causing stalls; "
     "shared across all DynamIQ CPUs in the cluster",
     "base"),
    ("DSU-120-PMU", "pmu", "ARM",
     "DSU-120 PMU — cluster-level events: L3 hit/miss, bus read/write, "
     "snoop filter events, power gating counters",
     "base"),
    ("DSU-120-power-ctrl", "power", "ARM",
     "DSU-120 power controller — per-core power gating, dynamic L3 slice "
     "power management (can turn off cache slices without stalls); "
     "PSCI CPU_OFF, retention states",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Immortalis-G925 GPU
# ---------------------------------------------------------------------------

_GPU_COMPONENTS = [
    ("Immortalis-G925", "gpu", "ARM",
     "ARM Immortalis-G925 — 10th gen Mali architecture, 2024 CSS; "
     "up to 14 shader cores; ray tracing v2; 3.5 TFLOPS FP32; "
     "DVS (Dynamic Voltage Scaling) for per-core power management",
     "base"),
    ("Immortalis-G925-MMU", "iommu", "ARM",
     "Immortalis-G925 GPU MMU — per-core page table walker, "
     "4-level page tables, SMMU integration for system memory isolation",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts — CSS v2
# ---------------------------------------------------------------------------

_CSS_INTERRUPTS = [
    ("IRQ-PMU-X925", "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-A725", "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-A520", "PPI", 23, "level-high", "base"),
    ("IRQ-CTI-X925", "PPI", 24, "level-high", "base"),
    ("SPI-G925-Job", "SPI", 198, "level-high", "base"),
    ("SPI-G925-MMU-Fault", "SPI", 199, "level-high", "base"),
    ("SPI-G925-GPU-Fault", "SPI", 200, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — 2024 CSS specific
# ---------------------------------------------------------------------------

_CSS_FAILURES = [
    ("x925-l2-ecc-uce",
     "Machine check exception on Cortex-X925; L2 cache uncorrectable ECC error logged via ARM RAS",
     "L2 ECC failure on 3nm silicon; check ERXMISC0_EL1 for syndrome; "
     "may indicate SRAM retention voltage marginal at low-power states",
     "cpu",
     "ARM Cortex-X925 TRM §12 (RAS)",
     "base"),
    ("dsu120-l3-slice-power-stuck",
     "DSU-120 L3 cache slice fails to power up; L3 hit rate drops suddenly; "
     "perf stat shows unexpected L3 miss spike",
     "L3 slice power controller stuck in off state; check DSU-120 power "
     "sequence FSM via CoreSight debug; may need PSCI SYSTEM_RESET to recover",
     "power",
     "ARM DSU-120 TRM §5.3 (dynamic L3 slice power gating)",
     "base"),
    ("a725-sve2-illegal-instruction",
     "SIGILL on SVE2 instruction in user process; but /proc/cpuinfo shows sve2",
     "SVE vector length mismatch between big and LITTLE cores after migration; "
     "check prctl(PR_SVE_SET_VL) and ensure EL1 ZCR_EL1.LEN is consistent across clusters",
     "cpu",
     "ARM Architecture Reference Manual ARMv9.2-A §SVE2",
     "base"),
    ("g925-gpu-hang-dvs",
     "GPU job timeout; Mali kbase reports GPU_FAULT; screen freeze during 3D rendering",
     "Immortalis-G925 DVS voltage too low for shader clock frequency; "
     "check devfreq OPP table voltage corners; may need silicon-specific AVS trim",
     "gpu",
     "ARM Immortalis-G925 product docs, Mali kbase driver source",
     "base"),
    ("css-v2-chi-timeout",
     "System hang; CHI interconnect timeout reported in SoC error register; "
     "no bus response from target component",
     "CHI coherency request stalled due to snoop filter full or target power "
     "domain unexpectedly off; check DSU-120 snoop filter capacity and power domain state",
     "interconnect",
     "ARM CHI Architecture Specification, ARM DSU-120 TRM §4 (CHI interface)",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _X925_COMPONENTS + _A725_COMPONENTS + _A520_COMPONENTS +
        _DSU120_COMPONENTS + _GPU_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _CSS_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _CSS_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # -- Relationships --

    # PE → L1 caches
    for pe, l1i, l1d in [
        ("Cortex-X925-PE", "Cortex-X925-L1I", "Cortex-X925-L1D"),
        ("Cortex-A725-PE", "Cortex-A725-L1I", "Cortex-A725-L1D"),
        ("Cortex-A520-PE", "Cortex-A520-L1I", "Cortex-A520-L1D"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l1i)
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l1d)

    # PE → private L2
    for pe, l2 in [
        ("Cortex-X925-PE", "Cortex-X925-L2"),
        ("Cortex-A725-PE", "Cortex-A725-L2"),
        ("Cortex-A520-PE", "Cortex-A520-L2"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l2)

    # Cluster → DSU-120 (L3 access)
    for cluster in ("Cortex-X925-Cluster", "Cortex-A725-Cluster", "Cortex-A520-Cluster"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=cluster, dst_name="DSU-120")

    # DSU-120 → L3 cache
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-120", dst_name="DSU-120-L3")

    # DSU-120 power controller → PSCI
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-120-power-ctrl", dst_name="arm-psci")

    # PMU → perf framework
    for pmu in ("Cortex-X925-PMU", "Cortex-A725-PMU", "Cortex-A520-PMU", "DSU-120-PMU"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pmu, dst_name="linux-perf-arm")

    # ETM → CoreSight funnel
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Cortex-X925-ETM", dst_name="CoreSight-funnel")

    # GPU → interconnect
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Immortalis-G925", dst_name="Immortalis-G925-MMU")

    # Failure → root component
    _fm_causes = [
        ("x925-l2-ecc-uce", "Cortex-X925-L2"),
        ("dsu120-l3-slice-power-stuck", "DSU-120-power-ctrl"),
        ("a725-sve2-illegal-instruction", "Cortex-A725-PE"),
        ("g925-gpu-hang-dvs", "Immortalis-G925"),
        ("css-v2-chi-timeout", "DSU-120"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-css-v2-2024] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
