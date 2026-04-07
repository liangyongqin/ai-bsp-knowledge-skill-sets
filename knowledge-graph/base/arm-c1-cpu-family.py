"""
ARM C1 CPU family seed — open-source knowledge ingestion.

Adds ARM's new C-series CPU cores (announced September 2025), replacing
the Cortex-A/X naming convention:
  - C1-Ultra (flagship, replaces Cortex-X series)
  - C1-Premium (sub-flagship big core)
  - C1-Pro (performance, replaces Cortex-A7xx series)
  - C1-Nano (efficiency, replaces Cortex-A5xx series)
  - Lumex CSS (Compute SubSystem platform)
  - Mali-G1 GPU (paired with C1 family)

All cores are ARMv9.3-A with SME2 (Scalable Matrix Extension 2).

Sources:
  - ARM C1-Ultra product page — arm.com/products/silicon-ip-cpu/c1-ultra
  - ARM C1-Nano product page — arm.com/products/silicon-ip-cpu/c1-nano
  - ARM Lumex CSS announcement — arm.com (September 2025)
  - ARM A-Profile Architecture Developments 2025 blog
  - TF-A 2.14 release notes (C1 CPU support) — trustedfirmware.org

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
# Components — C1-Ultra (flagship, ARMv9.3-A)
# ---------------------------------------------------------------------------

_C1_ULTRA_COMPONENTS = [
    ("C1-Ultra-PE", "cpu", "ARM",
     "ARM C1-Ultra — ARMv9.3-A flagship core, successor to Cortex-X925; "
     "SME2, SVE2, MTE, +25% single-thread perf over X925; "
     "widest decode in ARM portfolio",
     "base"),
    ("C1-Ultra-L2", "cache", "ARM",
     "C1-Ultra private L2 cache — up to 3MB, 16-way, write-back; "
     "largest per-core L2 in C1 family",
     "base"),
    ("C1-Ultra-PMU", "pmu", "ARM",
     "C1-Ultra PMU — 8+ programmable counters, BRBE, AMU v1.1, "
     "full Topdown L2 metrics, SME event counters",
     "base"),
    ("C1-Ultra-Cluster", "cpu-cluster", "ARM",
     "C1-Ultra prime cluster — typically 1-2 cores, DynamIQ; "
     "peak single-thread IPC for flagship SoCs",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — C1-Premium (sub-flagship big core, ARMv9.3-A)
# ---------------------------------------------------------------------------

_C1_PREMIUM_COMPONENTS = [
    ("C1-Premium-PE", "cpu", "ARM",
     "ARM C1-Premium — ARMv9.3-A sub-flagship core; "
     "SME2, SVE2, MTE; near-flagship perf with better area/power efficiency; "
     "positioned between C1-Ultra and C1-Pro",
     "base"),
    ("C1-Premium-L2", "cache", "ARM",
     "C1-Premium private L2 cache — up to 2MB, 16-way, write-back",
     "base"),
    ("C1-Premium-PMU", "pmu", "ARM",
     "C1-Premium PMU — 8 programmable counters, BRBE, AMU v1.1",
     "base"),
    ("C1-Premium-Cluster", "cpu-cluster", "ARM",
     "C1-Premium sub-flagship cluster — 1-2 cores, DynamIQ; "
     "balances area and performance for multi-core configs",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — C1-Pro (performance core, ARMv9.3-A)
# ---------------------------------------------------------------------------

_C1_PRO_COMPONENTS = [
    ("C1-Pro-PE", "cpu", "ARM",
     "ARM C1-Pro — ARMv9.3-A performance core, successor to Cortex-A725; "
     "SME2, SVE2, MTE; +16% sustained perf over A725; "
     "out-of-order, optimized for sustained multi-thread workloads",
     "base"),
    ("C1-Pro-L2", "cache", "ARM",
     "C1-Pro private L2 cache — 256KB-1MB, 8-way, write-back",
     "base"),
    ("C1-Pro-PMU", "pmu", "ARM",
     "C1-Pro PMU — 6 programmable counters, BRBE, AMU v1.1",
     "base"),
    ("C1-Pro-Cluster", "cpu-cluster", "ARM",
     "C1-Pro performance cluster — up to 4 cores, DynamIQ; "
     "main workhorse cluster for sustained throughput",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — C1-Nano (efficiency core, ARMv9.3-A)
# ---------------------------------------------------------------------------

_C1_NANO_COMPONENTS = [
    ("C1-Nano-PE", "cpu", "ARM",
     "ARM C1-Nano — ARMv9.3-A efficiency core, successor to Cortex-A520; "
     "SME2, SVE2, MTE; +26% efficiency over A520; "
     "in-order merged-core design for maximum power efficiency",
     "base"),
    ("C1-Nano-L2", "cache", "ARM",
     "C1-Nano shared L2 cache — 128KB-512KB per merged-core complex, 8-way",
     "base"),
    ("C1-Nano-PMU", "pmu", "ARM",
     "C1-Nano PMU — 6 programmable counters, BRBE, AMU v1.1",
     "base"),
    ("C1-Nano-Cluster", "cpu-cluster", "ARM",
     "C1-Nano efficiency cluster — up to 4 cores (2 merged-core complexes), "
     "DynamIQ; lowest power tier in C1 family",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Lumex CSS and Mali-G1
# ---------------------------------------------------------------------------

_PLATFORM_COMPONENTS = [
    ("Lumex-CSS", "platform", "ARM",
     "ARM Lumex Compute SubSystem (CSS) — pre-integrated platform combining "
     "C1 CPU cores, Mali-G1 GPU, DSU, CMN interconnect, and system IPs; "
     "successor to Total Compute Solutions (TCS); "
     "announced September 2025 for 2026 flagship SoCs",
     "base"),
    ("Mali-G1-GPU", "gpu", "ARM",
     "ARM Mali-G1 GPU — next-generation GPU paired with Lumex CSS; "
     "successor to Mali-G720/G725 Immortalis; "
     "ray tracing, Vulkan 1.3, OpenGL ES 3.2",
     "base"),
    ("ARMv9.3-SME2", "isa-extension", "ARM",
     "Scalable Matrix Extension v2 (SME2) — matrix operations for AI/ML inference, "
     "multi-vector operations, mandatory in ARMv9.3-A C1 family; "
     "accelerates GEMM, convolutions without dedicated NPU",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_C1_INTERRUPTS = [
    ("IRQ-PMU-C1-Ultra", "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-C1-Premium", "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-C1-Pro", "PPI", 23, "level-high", "base"),
    ("IRQ-PMU-C1-Nano", "PPI", 23, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_C1_FAILURES = [
    ("FM-SME2-SIGILL",
     "SIGILL on SME2 instruction; process crashes on C1-family target",
     "Kernel CONFIG_ARM64_SME not enabled or SME streaming mode not configured; "
     "check /proc/sys/abi/sme_default_vector_length and kernel config",
     "cpu",
     "Linux Documentation/arm64/sme.rst / ARM SME Programmer's Guide",
     "base"),
    ("FM-C1-EAS-Misplacement",
     "Tasks scheduled on wrong C1 core tier; C1-Ultra underutilized while C1-Nano overloaded",
     "EAS energy model not updated for 4-tier C1 configuration; "
     "capacities and energy costs must reflect Ultra/Premium/Pro/Nano hierarchy; "
     "check /sys/devices/system/cpu/cpu*/capacity and Energy Model sysfs",
     "power",
     "Linux Documentation/scheduler/sched-energy.rst",
     "base"),
    ("FM-Lumex-CSS-Boot-ID-Unknown",
     "Bootloader does not recognize C1 CPU MIDR; falls back to generic ARMv9 code paths",
     "MIDR_EL1 values for C1 family not in bootloader CPU table; "
     "update BL31 CPU library with C1 CPU ops (errata, reset, power-down); "
     "TF-A 2.14+ includes C1 support",
     "boot",
     "TF-A 2.14 release notes — trustedfirmware.org",
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
        _C1_ULTRA_COMPONENTS + _C1_PREMIUM_COMPONENTS +
        _C1_PRO_COMPONENTS + _C1_NANO_COMPONENTS +
        _PLATFORM_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _C1_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _C1_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Clusters → DSU (connect to existing DSU-120 for now; C1 may use DSU-130)
    for cluster in ("C1-Ultra-Cluster", "C1-Premium-Cluster",
                    "C1-Pro-Cluster", "C1-Nano-Cluster"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=cluster, dst_name="DSU-120")

    # PE → private L2
    for pe, l2 in [
        ("C1-Ultra-PE", "C1-Ultra-L2"),
        ("C1-Premium-PE", "C1-Premium-L2"),
        ("C1-Pro-PE", "C1-Pro-L2"),
        ("C1-Nano-PE", "C1-Nano-L2"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pe, dst_name=l2)

    # Lumex CSS contains all C1 clusters and Mali-G1
    for comp in ("C1-Ultra-Cluster", "C1-Premium-Cluster",
                 "C1-Pro-Cluster", "C1-Nano-Cluster", "Mali-G1-GPU"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="Lumex-CSS", dst_name=comp)

    # SME2 → all C1 PEs (mandatory ISA extension)
    for pe in ("C1-Ultra-PE", "C1-Premium-PE", "C1-Pro-PE", "C1-Nano-PE"):
        create_rel(conn, "SHARED_WITH", "Component", "Component",
                   src_name="ARMv9.3-SME2", dst_name=pe)

    # PMU → linux perf
    for pmu in ("C1-Ultra-PMU", "C1-Premium-PMU", "C1-Pro-PMU", "C1-Nano-PMU"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=pmu, dst_name="linux-perf-arm")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-SME2-SIGILL", "ARMv9.3-SME2"),
        ("FM-C1-EAS-Misplacement", "C1-Pro-Cluster"),
        ("FM-Lumex-CSS-Boot-ID-Unknown", "Lumex-CSS"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-c1-cpu-family] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
