"""
Linux DRM Panic & GPU fault recovery seed — open-source knowledge ingestion.

Adds Linux kernel 6.13–6.14 GPU-related features:
  - DRM Panic (kernel panic screen on GPU framebuffer, v6.10+ with AMDGPU in 6.14)
  - GPU job timeout / reset recovery paths
  - AMD XDNA NPU accelerator driver (6.14)
  - PCIe bandwidth cooling for GPU thermal management (6.13)
  - DSU L3 snoop filter internals (DSU-110/DSU-120)

Sources:
  - Phoronix: Linux 6.14 AMDGPU changes (2025-01)
  - 9to5Linux: Linux kernel 6.14 release notes (2025-03)
  - KernelNewbies: Linux 6.13 release notes
  - Linux kernel Documentation/gpu/drm-internals.rst
  - Linux kernel drivers/gpu/drm/drm_panic*.c
  - ARM DynamIQ Shared Unit DSU-110 TRM (ARM DDI 101381)
  - ARM DynamIQ Shared Unit DSU-120 TRM (AnandTech deep dive)

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
# Components — DRM Panic subsystem (Linux 6.10+, AMDGPU support in 6.14)
# ---------------------------------------------------------------------------

_DRM_PANIC_COMPONENTS = [
    ("drm-panic",             "framework",  "linux",
     "DRM Panic (Linux 6.10+) — kernel panic handler that renders panic message "
     "on GPU framebuffer; displays error text and optional QR code for crash info; "
     "replaces blank screen on kernel panic when no VGA console is available; "
     "requires DRM driver to implement panic_flush callback",
     "base"),
    ("drm-panic-qr",          "framework",  "linux",
     "DRM Panic QR code encoder — generates QR code on panic screen containing "
     "panic message, stack trace, and kernel version for easy capture via phone camera; "
     "renders at boot framebuffer resolution",
     "base"),
    ("drm-panic-amdgpu",      "driver",     "linux",
     "AMDGPU DRM Panic support (Linux 6.14) — panic_flush implementation for "
     "AMD Radeon/RDNA GPUs; renders panic screen on AMDGPU framebuffer; "
     "works with DCN display engine",
     "base"),
    ("drm-panic-nouveau",     "driver",     "linux",
     "Nouveau DRM Panic support (Linux 6.13) — panic_flush implementation "
     "for NVIDIA GPUs via open-source nouveau driver",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — GPU fault recovery paths
# ---------------------------------------------------------------------------

_GPU_RECOVERY_COMPONENTS = [
    ("drm-gpu-reset",          "framework",  "linux",
     "DRM GPU reset framework — drm_sched_fault() triggers GPU reset from scheduler; "
     "driver implements .reset callback; resubmits pending jobs after reset; "
     "atomic reset for minimal display disruption",
     "base"),
    ("drm-sched-timeout",      "framework",  "linux",
     "DRM scheduler job timeout — drm_sched_job_timedout() callback when GPU job "
     "exceeds maximum execution time; triggers fault recovery sequence: "
     "stop scheduler → reset GPU → restart scheduler → resubmit jobs",
     "base"),
    ("drm-coredump",           "framework",  "linux",
     "DRM coredump — captures GPU state on hang/fault for post-mortem analysis; "
     "devcoredump integration; stores BO contents, ring buffer state, register dump; "
     "accessible via /sys/class/devcoredump/",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — AMD XDNA NPU driver (Linux 6.14)
# ---------------------------------------------------------------------------

_XDNA_COMPONENTS = [
    ("amdxdna-driver",         "driver",     "linux",
     "AMD XDNA accelerator driver (Linux 6.14) — DRM driver for AMD Ryzen AI NPU; "
     "Neural Processing Unit for on-device AI inference; "
     "supports AIE2 (AI Engine v2) compute tiles; DMA-BUF sharing with GPU",
     "base"),
    ("amdxdna-firmware",       "firmware",   "AMD",
     "AMD XDNA NPU firmware — loaded by amdxdna driver at probe time; "
     "manages AIE2 tile scheduling and power states; "
     "firmware binary distributed via linux-firmware.git",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — DSU-110/DSU-120 L3 cache internals
# ---------------------------------------------------------------------------

_DSU_INTERNALS = [
    ("DSU-L3-slice",           "cache",      "ARM",
     "DSU L3 cache slice — portion of shared L3 with associated snoop filter "
     "and control logic; DSU-110 supports up to 8 slices; DSU-120 up to 8 slices "
     "with 3MB total; each slice independently clock-gatable for power savings",
     "base"),
    ("DSU-snoop-filter",       "cache",      "ARM",
     "DSU Snoop Filter — tracks cacheline ownership across cores; prevents "
     "broadcast snoops for lines not cached by other cores; "
     "DSU-110 reduces leakage by 75% via snoop filter power gating; "
     "overflow causes back-invalidation (evicts tracked lines, increases DRAM traffic)",
     "base"),
    ("DSU-SCU",                "cache",      "ARM",
     "DSU Snoop Control Unit (SCU) — maintains coherency between core L2 caches "
     "and shared L3; handles snoop requests, data forwarding, and "
     "DVM (Distributed Virtual Memory) operations for TLB maintenance",
     "base"),
    ("DSU-L3-tag-ram",         "cache",      "ARM",
     "DSU L3 tag RAM — stores cacheline tags and MOESI state; "
     "parity-protected; independent power domain allows tag retention "
     "while data RAMs are power-gated in deep idle",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_FAILURE_MODES = [
    ("FM-DRM-Panic-No-Output",
     "Kernel panic occurs but screen goes blank; no panic message visible",
     "DRM driver does not implement panic_flush callback; enable CONFIG_DRM_PANIC "
     "and verify driver support; fallback: use serial console or pstore for crash info",
     "gpu", "Linux kernel Documentation/gpu/drm-internals.rst", "medium"),
    ("FM-GPU-Reset-Hang",
     "GPU reset triggered but system hangs during reset; complete lockup",
     "GPU reset sequence fails to quiesce all outstanding DMA; pending PCIe transactions "
     "block reset completion; check for IOMMU faults during reset and PCIe FLR support",
     "gpu", "Linux DRM scheduler / LKML GPU reset discussions", "critical"),
    ("FM-DRM-Sched-Timeout-Loop",
     "GPU jobs repeatedly timeout and reset; system usable but GPU unusable",
     "Persistent GPU hang caused by corrupted firmware state or thermal throttle to near-zero; "
     "check GPU temperature, firmware version, and whether a specific shader triggers the hang; "
     "may need cold reboot to clear firmware state",
     "gpu", "Linux DRM scheduler documentation / Phoronix GPU debugging", "high"),
    ("FM-NPU-Firmware-Load-Fail",
     "amdxdna: firmware load failed; NPU device not available; AI inference errors",
     "NPU firmware binary missing from /lib/firmware or version mismatch; "
     "update linux-firmware package; check dmesg for firmware version requirements; "
     "also verify NPU is not disabled in BIOS/UEFI settings",
     "npu", "Linux 6.14 release notes / AMD XDNA driver", "medium"),
    ("FM-DSU-Snoop-Filter-Thrash",
     "Performance regression under multi-threaded workload; L3 miss rate spikes",
     "DSU snoop filter capacity exceeded by false sharing pattern across cores; "
     "back-invalidation evicts tracked lines; align hot data structures to cacheline "
     "boundaries; reduce cross-core sharing or increase L3 slice count in SoC config",
     "interconnect", "ARM DSU-110 TRM / ARM performance optimization guide", "medium"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_INTERRUPTS = [
    ("IRQ-GPU-RESET-DONE",    "SPI", 224, "level-high", "base"),
    ("IRQ-NPU-JOB-DONE",     "SPI", 240, "level-high", "base"),
    ("IRQ-NPU-FAULT",        "SPI", 241, "level-high", "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _DRM_PANIC_COMPONENTS + _GPU_RECOVERY_COMPONENTS +
        _XDNA_COMPONENTS + _DSU_INTERNALS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, domain, source, severity in _FAILURE_MODES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": domain, "source": source,
            "namespace": "base", "severity": severity,
        }):
            inserted += 1

    # --- Relationships ---

    # DRM Panic framework
    for src, dst in [
        ("drm-panic",         "drm-core"),
        ("drm-panic-qr",      "drm-panic"),
        ("drm-panic-amdgpu",  "drm-panic"),
        ("drm-panic-nouveau", "drm-panic"),
    ]:
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
                   src_name=src, dst_name=dst)

    # GPU recovery framework
    for src, dst in [
        ("drm-gpu-reset",     "drm-scheduler"),
        ("drm-sched-timeout", "drm-scheduler"),
        ("drm-coredump",      "drm-gpu-reset"),
        ("drm-gpu-reset",     "drm-core"),
    ]:
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
                   src_name=src, dst_name=dst)

    # XDNA NPU
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="amdxdna-driver", dst_name="drm-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="amdxdna-driver", dst_name="amdxdna-firmware")
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="amdxdna-driver", dst_name="dma-buf-core")

    # DSU internals → existing DSU nodes
    for src, dst in [
        ("DSU-L3-slice",      "DSU-snoop-filter"),
        ("DSU-SCU",           "DSU-L3-slice"),
        ("DSU-L3-tag-ram",    "DSU-L3-slice"),
        ("DSU-SCU",           "DSU-snoop-filter"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # Link DSU internals to existing DSU-120
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-120", dst_name="DSU-L3-slice")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DSU-120", dst_name="DSU-SCU")

    # Interrupt routing
    create_rel(conn, "ROUTES_TO", "Interrupt", "Component",
               src_name="IRQ-GPU-RESET-DONE", dst_name="drm-gpu-reset")
    create_rel(conn, "ROUTES_TO", "Interrupt", "Component",
               src_name="IRQ-NPU-JOB-DONE", dst_name="amdxdna-driver")
    create_rel(conn, "ROUTES_TO", "Interrupt", "Component",
               src_name="IRQ-NPU-FAULT", dst_name="amdxdna-driver")

    # Failure modes → components
    for fm, comp in [
        ("FM-DRM-Panic-No-Output",      "drm-panic"),
        ("FM-GPU-Reset-Hang",           "drm-gpu-reset"),
        ("FM-DRM-Sched-Timeout-Loop",   "drm-sched-timeout"),
        ("FM-NPU-Firmware-Load-Fail",   "amdxdna-driver"),
        ("FM-DSU-Snoop-Filter-Thrash",  "DSU-snoop-filter"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm, dst_name=comp)

    print(f"[linux-drm-panic-gpu-recovery] Inserted {inserted} nodes.")
    return inserted


if __name__ == "__main__":
    ingest()
