"""
ARM CPU Cluster seed — open-source knowledge ingestion.

Sources:
  - ARM Cortex-A55 TRM (ARM DDI 0484)
  - ARM Cortex-A76 TRM (ARM DDI 0526)
  - ARM Cortex-X1 TRM (ARM DDI 0570)
  - ARM DynamIQ Shared Unit (DSU-110) TRM (ARM DDI 0568)
  - ARM CoreSight SoC-600 TRM (ARM DDI 0480)
  - ARM Performance Monitoring Unit (PMU) architecture spec
  - Linux Documentation/arm64/cpu-feature-registers.rst
  - Linux Documentation/driver-api/perf_event.rst

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
# Components — Cortex-A55 (efficiency core)
# ---------------------------------------------------------------------------

_A55_COMPONENTS = [
    ("Cortex-A55-PE",        "cpu",          "ARM", "ARM Cortex-A55 r2p0 — AArch64/AArch32, in-order pipeline, 4-stage decode, ARMv8.2-A; 64KB L1I + 64KB L1D",    "base"),
    ("Cortex-A55-L1I",       "cache",        "ARM", "Cortex-A55 L1 instruction cache — 64KB, 4-way, 64-byte cacheline, VIPT",                                        "base"),
    ("Cortex-A55-L1D",       "cache",        "ARM", "Cortex-A55 L1 data cache — 64KB, 4-way, 64-byte cacheline, VIPT write-through (optional write-back)",            "base"),
    ("Cortex-A55-L2",        "cache",        "ARM", "Cortex-A55 private L2 cache — 64KB–512KB (config), 8-way, ECC protected",                                       "base"),
    ("Cortex-A55-PMU",       "pmu",          "ARM", "Cortex-A55 PMU — 4 programmable event counters + CCNT; ARMv8 PMU architecture, perf-compatible",                "base"),
    ("Cortex-A55-ETM",       "trace",        "ARM", "Cortex-A55 Embedded Trace Macrocell v4.0 — instruction trace, timestamp, cycle-accurate; feeds CoreSight ETF",   "base"),
    ("Cortex-A55-Cluster",   "cpu-cluster",  "ARM", "Cortex-A55 cluster (LITTLE cluster) — typically 4-core DynamIQ, shared L3 via DSU",                             "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-A76 / A78 (performance core)
# ---------------------------------------------------------------------------

_A76_COMPONENTS = [
    ("Cortex-A76-PE",        "cpu",          "ARM", "ARM Cortex-A76 r4p1 — AArch64 out-of-order, 4-wide decode, ARMv8.2-A; 64KB L1I + 64KB L1D; MPAM v0.1",         "base"),
    ("Cortex-A76-L1I",       "cache",        "ARM", "Cortex-A76 L1 instruction cache — 64KB, 4-way, 64-byte cacheline",                                               "base"),
    ("Cortex-A76-L1D",       "cache",        "ARM", "Cortex-A76 L1 data cache — 64KB, 4-way, write-back, MOESI coherency",                                            "base"),
    ("Cortex-A76-L2",        "cache",        "ARM", "Cortex-A76 private L2 — 256KB–512KB, 8-way, write-back; victim cache for L1D evictions",                         "base"),
    ("Cortex-A76-PMU",       "pmu",          "ARM", "Cortex-A76 PMU — 6 programmable counters + CCNT; additional Topdown events (FrontendBound, BackendBound)",        "base"),
    ("Cortex-A76-ETM",       "trace",        "ARM", "Cortex-A76 ETM v4.0 — instruction trace with branch predictor state; compressed branch packet format",            "base"),
    ("Cortex-A76-Cluster",   "cpu-cluster",  "ARM", "Cortex-A76 cluster (BIG cluster) — 4-core DynamIQ, shared L3 via DSU-110",                                       "base"),
]

# ---------------------------------------------------------------------------
# Components — Cortex-X1 (prime core)
# ---------------------------------------------------------------------------

_X1_COMPONENTS = [
    ("Cortex-X1-PE",         "cpu",          "ARM", "ARM Cortex-X1 r1p0 — out-of-order, 8-wide decode, ARMv8.4-A; 64KB L1I + 64KB L1D; 1MB private L2",             "base"),
    ("Cortex-X1-L2",         "cache",        "ARM", "Cortex-X1 private L2 — 512KB–1MB, 16-way; write-back with hardware prefetcher",                                  "base"),
    ("Cortex-X1-PMU",        "pmu",          "ARM", "Cortex-X1 PMU — 6 programmable counters; BRBE (Branch Record Buffer Extension) support",                          "base"),
    ("Cortex-X1-Cluster",    "cpu-cluster",  "ARM", "Cortex-X1 prime cluster — 1-core DynamIQ, highest peak IPC for bursty workloads",                                "base"),
]

# ---------------------------------------------------------------------------
# Components — DynamIQ Shared Unit (DSU)
# ---------------------------------------------------------------------------

_DSU_COMPONENTS = [
    ("DSU-110",              "dsu",          "ARM", "ARM DynamIQ Shared Unit DSU-110 — L3 (SCU-L3) cache 1–16MB, coherent interconnect for LITTLE+BIG+X1 clusters",   "base"),
    ("DSU-L3",               "cache",        "ARM", "DSU-110 L3 cache — 1–16MB configurable, 16-way, MOESI, ECC; shared across all DynamIQ CPUs",                     "base"),
    ("DSU-PMU",              "pmu",          "ARM", "DSU-110 PMU — cluster-level events: L3 hit/miss, bus read/write, cycle count",                                    "base"),
    ("DSU-power-ctrl",       "power",        "ARM", "DSU-110 power controller — per-core power gating, PDPU (Power Domain Process Unit), implements PSCI CPU_OFF",     "base"),
]

# ---------------------------------------------------------------------------
# Components — CoreSight Debug / Trace Infrastructure
# ---------------------------------------------------------------------------

_CORESIGHT_COMPONENTS = [
    ("CoreSight-ETF",        "trace-sink",   "ARM", "Embedded Trace FIFO — on-chip trace buffer (4KB–64KB SRAM); sinks ETM streams; flushed via TPIU or ETR",         "base"),
    ("CoreSight-ETR",        "trace-sink",   "ARM", "Embedded Trace Router — streams trace to DRAM via AXI master; supports large trace capture (>64KB)",               "base"),
    ("CoreSight-TPIU",       "trace-sink",   "ARM", "Trace Port Interface Unit — exports trace to external probe (JTAG/SWD); generates CoreSight TPIU formatter packets","base"),
    ("CoreSight-funnel",     "trace-mux",    "ARM", "CoreSight ATB Funnel — merges multiple ETM ATB streams into single output (up to 8 inputs, priority arbitration)", "base"),
    ("CoreSight-TMC",        "trace-sink",   "ARM", "Trace Memory Controller — configurable as ETF/ETR; supports circular buffer and draining modes",                   "base"),
    ("CoreSight-CTI",        "debug",        "ARM", "Cross Trigger Interface — cross-core trigger propagation; halt-on-fault, power-event correlation",                 "base"),
    ("CoreSight-STM",        "trace-source", "ARM", "System Trace Macrocell — software-generated trace (printk, MIPI STP); low-overhead logging from kernel/user",     "base"),
    ("CoreSight-SoC600",     "debug-hub",    "ARM", "CoreSight SoC-600 debug subsystem — integrates ETM/ETF/ETR/TPIU/CTI with APB-AP access for JTAG debuggers",       "base"),
    ("ADIv6-DAP",            "debug",        "ARM", "ARMv8 Debug Access Port v6 — AHB-AP + APB-AP; SWD and JTAG transport; multi-drop JTAG (SWD with target select)",  "base"),
]

# ---------------------------------------------------------------------------
# Components — CPU PMU / Perf Integration
# ---------------------------------------------------------------------------

_PMU_COMPONENTS = [
    ("linux-perf-arm",       "framework",    "linux", "Linux perf arm backend — arm_pmu driver, perf_event_open() → PMU context switch; supports task/cpu mode",       "base"),
    ("linux-perf-spe",       "framework",    "linux", "ARM Statistical Profiling Extension (SPE) perf backend — sampled load/store latency, TLB miss, branch mispred", "base"),
    ("arm-pmu-driver",       "driver",       "linux", "ARM PMU platform driver — registers perf_pmu per-CPU cluster; handles IRQ_PMU overflow",                        "base"),
    ("perf-event-core",      "framework",    "linux", "Linux perf_event core — context, group leader, ring buffer, mmap; wraps arm_pmu for userspace perf tool",       "base"),
]

# ---------------------------------------------------------------------------
# Components — CPU power management
# ---------------------------------------------------------------------------

_CPU_PM_COMPONENTS = [
    ("cpuidle-arm",          "driver",       "linux", "ARM cpuidle driver — WFI, power-gating states; interfaces PSCI CPU_SUSPEND for deep idle",                     "base"),
    ("cpu-freq-arm",         "driver",       "linux", "ARM CPUFreq driver — OPP table parsing, DVFS request to PMIC/clock; supports schedutil governor",               "base"),
    ("arm-scmi",             "firmware",     "linux", "SCMI (System Control and Management Interface) — ARM spec DEN0056; firmware-mediated CPU/GPU/voltage requests",  "base"),
    ("arm-psci",             "firmware",     "ARM",   "ARM PSCI firmware interface — CPU_ON/CPU_OFF/CPU_SUSPEND/SYSTEM_SUSPEND; DEN0022D; invoked via HVC/SMC",         "base"),
    ("sched-util-arm",       "kernel",       "linux", "Linux schedutil CPUFreq governor — PELT utilization → OPP request; EAS integration for big.LITTLE",             "base"),
]

# ---------------------------------------------------------------------------
# Interrupts — CPU cluster
# ---------------------------------------------------------------------------

_CPU_INTERRUPTS = [
    ("IRQ-PMU-A55",    "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-A76",    "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-X1",     "PPI", 23, "level-high", "base"),
    ("IRQ-CTI-A55",    "PPI", 24, "level-high", "base"),
    ("IRQ-WDT-CPU",    "SPI", 38, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — CPU / CoreSight
# ---------------------------------------------------------------------------

_CPU_FAILURES = [
    ("perf-counter-overflow",
     "perf stat shows bogus event counts; PMU overflow interrupt not handled",
     "PMU PPI not routed to correct CPU affinity; check arm-pmu-driver CPU hotplug callback",
     "cpu",
     "Linux Documentation/driver-api/perf_event.rst",
     "base"),
    ("coresight-trace-lost",
     "CoreSight ETF overflow flag set; trace FIFO full; decoder reports 'lost bytes'",
     "ETF size too small for trace bandwidth; switch to ETR with DRAM backing (≥16MB recommended)",
     "debug",
     "ARM CoreSight SoC-600 TRM (ARM DDI 0480) §4.3",
     "base"),
    ("jtag-cannot-halt",
     "JTAG fails to halt CPU; debug probe reports 'cannot halt core'",
     "CPU in EL3 secure world without debug authentication enabled; check DBGEN/NIDEN fuses",
     "debug",
     "ARM ADIv6 architecture spec §C1 (Debug authentication)",
     "base"),
    ("cluster-power-collapse-fail",
     "Last CPU in cluster does not power off; power domain stays on",
     "CPU hotplug notifier blocked by kthread still running; check CPUidle DSU state preconditions",
     "power",
     "ARM DSU-110 TRM §5.2 (cluster power gating requirements)",
     "base"),
    ("spe-sample-lost",
     "ARM SPE /sys/bus/event_source/devices/arm_spe_N shows 'sample lost' counter incrementing",
     "SPE sampling rate too high for DRAM write bandwidth; reduce sample period or cap via PMSNEVFR_EL1",
     "cpu",
     "Linux Documentation/arm64/perf.rst (SPE)",
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
        _A55_COMPONENTS + _A76_COMPONENTS + _X1_COMPONENTS +
        _DSU_COMPONENTS + _CORESIGHT_COMPONENTS +
        _PMU_COMPONENTS + _CPU_PM_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _CPU_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _CPU_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Cluster → DSU (ROUTES_TO: cluster connects to DSU for L3 access)
    for cluster in ("Cortex-A55-Cluster", "Cortex-A76-Cluster", "Cortex-X1-Cluster"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=cluster, dst_name="DSU-110")

    # PE → private L2
    for pe, l2 in [
        ("Cortex-A55-PE", "Cortex-A55-L2"),
        ("Cortex-A76-PE", "Cortex-A76-L2"),
        ("Cortex-X1-PE",  "Cortex-X1-L2"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l2)

    # PE → L1 caches
    for pe, l1i, l1d in [
        ("Cortex-A55-PE", "Cortex-A55-L1I", "Cortex-A55-L1D"),
        ("Cortex-A76-PE", "Cortex-A76-L1I", "Cortex-A76-L1D"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l1i)
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l1d)

    # ETM → CoreSight funnel → ETF → ETR → TPIU
    for src, dst in [
        ("Cortex-A55-ETM",  "CoreSight-funnel"),
        ("Cortex-A76-ETM",  "CoreSight-funnel"),
        ("CoreSight-funnel","CoreSight-ETF"),
        ("CoreSight-ETF",   "CoreSight-ETR"),
        ("CoreSight-ETF",   "CoreSight-TPIU"),
        ("CoreSight-STM",   "CoreSight-funnel"),
        ("CoreSight-SoC600","ADIv6-DAP"),
        ("ADIv6-DAP",       "CoreSight-CTI"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # PMU → perf framework
    for pmu in ("Cortex-A55-PMU", "Cortex-A76-PMU", "Cortex-X1-PMU", "DSU-PMU"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pmu, dst_name="linux-perf-arm")

    # CPU PM
    for drv in ("cpuidle-arm", "cpu-freq-arm"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=drv, dst_name="arm-psci")

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="arm-scmi", dst_name="arm-psci")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="sched-util-arm", dst_name="cpu-freq-arm")

    # DSU power controller → PSCI
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-power-ctrl", dst_name="arm-psci")

    # Failure → root component
    _fm_causes = [
        ("perf-counter-overflow",       "arm-pmu-driver"),
        ("coresight-trace-lost",        "CoreSight-ETF"),
        ("jtag-cannot-halt",            "ADIv6-DAP"),
        ("cluster-power-collapse-fail", "DSU-power-ctrl"),
        ("spe-sample-lost",             "linux-perf-spe"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-cpu-cluster] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
