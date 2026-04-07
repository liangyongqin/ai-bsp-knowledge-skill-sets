"""
Linux kernel power management updates seed — kernel 6.9 through 6.16.

Adds newer Linux kernel developments not covered by existing seed scripts:
  - Runtime-modifiable Energy Model (6.9)
  - Panthor GPU driver for Mali 10th gen (6.10+)
  - MediaTek DVFS Resource Collector (6.11)
  - MT6357/MT6358/MT6359 PMIC ADC for thermal (6.11)
  - PREEMPT_RT on ARM64 (6.12)
  - DRM Color Pipeline API (6.16+)
  - Intel EAS in P-State (6.16)

Sources:
  - KernelNewbies: Linux 6.9, 6.10, 6.11, 6.12
  - Collabora blog: kernel 6.11 power moves, Panthor driver
  - Phoronix: Linux 6.10/6.16 power management
  - Linux kernel Documentation/scheduler/sched-energy.rst
  - Linux kernel Documentation/gpu/panthor.rst

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
# Components — Energy Model updates (Linux 6.9)
# ---------------------------------------------------------------------------

_EM_COMPONENTS = [
    ("linux-em-runtime-mod", "framework", "Linux",
     "Runtime-Modifiable Energy Model (Linux 6.9) — EM power values changeable at "
     "runtime via sysfs; enables accurate EAS task placement on SoCs with dynamic "
     "voltage/frequency characteristics; replaces static DT-based EM tables",
     "base"),
    ("linux-em-perf-domain", "framework", "Linux",
     "Energy Model Performance Domain — groups CPUs with identical power characteristics; "
     "each domain has an OPP table with power/frequency pairs; "
     "runtime modification updates these per-domain values",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Panthor GPU driver (Linux 6.10+)
# ---------------------------------------------------------------------------

_PANTHOR_COMPONENTS = [
    ("panthor-drm-driver", "driver", "Linux",
     "Panthor DRM driver (Linux 6.10+) — open-source kernel driver for ARM Mali "
     "10th gen (Valhall architecture) GPUs: G310, G510, G610, G710, G715, G720, G725; "
     "uses Command Stream Frontend (CSF) instead of Job Manager; "
     "achieved OpenGL ES 3.1 conformance on Mali-G610",
     "base"),
    ("panthor-CSF", "gpu-subsystem", "ARM",
     "Command Stream Frontend (CSF) — Mali 10th gen GPU command submission mechanism; "
     "replaces Job Manager (JM) from older Mali architectures; "
     "hardware command scheduler with priority queues and preemption; "
     "kernel submits command streams, GPU firmware schedules execution",
     "base"),
    ("panthor-heap", "gpu-subsystem", "ARM",
     "Panthor Tiler Heap — dynamically growing heap for tile list storage; "
     "automatic growth via GPU page faults; avoids pre-allocating worst-case "
     "memory for tiling; buffer object labeling added in kernel 6.16 for debugging",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — MediaTek platform support (Linux 6.11)
# ---------------------------------------------------------------------------

_MTK_COMPONENTS = [
    ("mtk-dvfs-resource-collector", "driver", "MediaTek",
     "MediaTek DVFS Resource Collector (Linux 6.11) — regulator and interconnect "
     "drivers for MediaTek SoC DVFS; manages voltage regulator requests and "
     "interconnect bandwidth votes from multiple consumers",
     "base"),
    ("mtk-pmic-auxadc", "driver", "MediaTek",
     "MT6357/MT6358/MT6359 PMIC Auxiliary ADC (Linux 6.11) — thermal monitoring "
     "via PMIC ADC channels; reads die temperature, battery voltage, VBAT; "
     "feeds Linux thermal framework for DVFS and throttling decisions",
     "base"),
    ("mtk-mt8188-power-domains", "driver", "MediaTek",
     "MT8188 Power Domains (Linux 6.11) — SoC power domain driver for MediaTek MT8188; "
     "GPU, ISP, VDOSYS display controller, GCE mailbox power management; "
     "Panfrost Mali GPU support on MT8188 upstreamed",
     "base"),
    ("mtk-svs-voltage-opt", "driver", "MediaTek",
     "MediaTek Smart Voltage Scaling (SVS) IP — per-die voltage optimization; "
     "reads eFuse calibration data to adjust OPP voltages; "
     "fixes for MT8192/MT8195 Chromebooks in Linux 6.11",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — PREEMPT_RT on ARM64 (Linux 6.12)
# ---------------------------------------------------------------------------

_RT_COMPONENTS = [
    ("linux-preempt-rt-arm64", "framework", "Linux",
     "PREEMPT_RT on ARM64 (Linux 6.12) — full real-time preemption support merged "
     "for ARM64; enables deterministic scheduling latencies for RT workloads; "
     "critical for automotive, industrial, and audio BSP use cases; "
     "requires careful IRQ threading and lock annotation in BSP drivers",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — DRM Color Pipeline API (Linux 6.16+)
# ---------------------------------------------------------------------------

_COLOR_PIPELINE_COMPONENTS = [
    ("drm-color-pipeline-api", "framework", "Linux",
     "DRM Per-Plane Color Pipeline API (Linux 6.16+) — prescriptive API exposing "
     "hardware color processing blocks directly to compositors; "
     "enables hardware-accelerated HDR without compositor guessing HW capabilities; "
     "each plane exposes a chain of color operations (degamma, CTM, gamma, LUT)",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Other kernel updates
# ---------------------------------------------------------------------------

_MISC_COMPONENTS = [
    ("linux-axp717-power", "driver", "Linux",
     "AXP717 Battery/USB Power Supply driver (Linux 6.12) — X-Powers AXP717 PMIC "
     "battery charging and USB power supply; common in Allwinner-based SoCs",
     "base"),
    ("linux-smmv3-vcmdq", "driver", "Linux",
     "SMMUv3 Virtual Command Queue (Linux 6.12) — per-device virtual command queues "
     "for NVIDIA GPUs; reduces SMMU command submission contention in multi-GPU "
     "and GPU passthrough configurations",
     "base"),
    ("linux-poe-arm64", "framework", "Linux",
     "ARM Permission Overlay Extension (POE, Linux 6.12) — hardware-enforced memory "
     "permission overlays; efficient permission changes without TLB flush; "
     "used for sandboxing and JIT compilation security",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_PM_FAILURES = [
    ("FM-Runtime-EM-Stale",
     "EAS makes poor task placement decisions after frequency/voltage change; "
     "tasks land on wrong cluster",
     "Runtime Energy Model not updated after dynamic OPP table change; "
     "devfreq or cpufreq driver must call em_dev_update_perf_domain() "
     "after modifying OPP values; check /sys/kernel/debug/energy_model/",
     "power",
     "Linux Documentation/scheduler/sched-energy.rst / KernelNewbies 6.9",
     "base"),
    ("FM-Panthor-CSF-Timeout",
     "Panthor GPU job timeout; dmesg shows 'group scheduling error' or "
     "'CSF progress timeout'; GPU hangs and recovers",
     "CSF firmware scheduling stall; command stream blocked on memory fault, "
     "priority inversion, or tiler heap exhaustion; check dmesg for GPU page "
     "faults and heap growth events; increase tiler heap initial size if needed",
     "gpu",
     "Linux Documentation/gpu/panthor.rst / Collabora Panthor blog",
     "base"),
    ("FM-Panthor-Heap-OOM",
     "Panthor tiler heap out of memory; rendering fails with heap allocation error",
     "Dynamic tiler heap growth exceeded system memory limits; scene too complex "
     "for available memory; reduce render target resolution or geometry complexity; "
     "check /sys/kernel/debug/dri/*/heap for heap usage",
     "gpu",
     "Linux kernel drivers/gpu/drm/panthor/",
     "base"),
    ("FM-MTK-SVS-Voltage-Undershoot",
     "MT8192/MT8195 GPU crashes under load after SVS voltage optimization",
     "SVS eFuse calibration data may be inaccurate for specific die; "
     "per-OPP voltage reduced too aggressively; add voltage guard band "
     "or disable SVS for affected OPP levels; fixed in Linux 6.11",
     "power",
     "Collabora kernel 6.11 blog / MediaTek SVS driver",
     "base"),
    ("FM-PREEMPT-RT-IRQ-Latency",
     "RT task misses deadline on ARM64; high IRQ-to-task latency despite PREEMPT_RT",
     "BSP driver using raw spinlocks or disabling preemption in non-RT-safe paths; "
     "audit drivers for spin_lock_irqsave → rt_spin_lock migration; "
     "use cyclictest to measure worst-case latency; check for missing IRQ threading",
     "power",
     "Linux Documentation/locking/rt-mutex.rst",
     "base"),
    ("FM-Color-Pipeline-Mismatch",
     "HDR content displays with wrong colors; compositor applies software fallback "
     "despite hardware color pipeline support",
     "DRM color pipeline API properties not set correctly by compositor; "
     "hardware color ops chain mismatch with content color space; "
     "verify KMS plane properties and color operation ordering",
     "display",
     "Linux Documentation/gpu/drm-kms.rst / DRM color pipeline patches",
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
        _EM_COMPONENTS + _PANTHOR_COMPONENTS + _MTK_COMPONENTS +
        _RT_COMPONENTS + _COLOR_PIPELINE_COMPONENTS + _MISC_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _PM_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Runtime EM → EAS scheduler
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-em-runtime-mod", dst_name="sched-util-arm")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-em-runtime-mod", dst_name="linux-em-perf-domain")

    # Panthor → DRM/KMS
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panthor-drm-driver", dst_name="DRM-KMS-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panthor-drm-driver", dst_name="panthor-CSF")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panthor-CSF", dst_name="panthor-heap")

    # MTK DVFS Resource Collector → devfreq
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mtk-dvfs-resource-collector", dst_name="devfreq-core")

    # MTK PMIC ADC → thermal framework
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mtk-pmic-auxadc", dst_name="thermal-core")

    # MT8188 power domains → genpd
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mtk-mt8188-power-domains", dst_name="genpd-core")

    # Color pipeline → DRM
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="drm-color-pipeline-api", dst_name="DRM-KMS-core")

    # SMMUv3 vCMDQ → SMMU
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-smmv3-vcmdq", dst_name="SMMUv3-TCU")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-Runtime-EM-Stale", "linux-em-runtime-mod"),
        ("FM-Panthor-CSF-Timeout", "panthor-CSF"),
        ("FM-Panthor-Heap-OOM", "panthor-heap"),
        ("FM-MTK-SVS-Voltage-Undershoot", "mtk-svs-voltage-opt"),
        ("FM-PREEMPT-RT-IRQ-Latency", "linux-preempt-rt-arm64"),
        ("FM-Color-Pipeline-Mismatch", "drm-color-pipeline-api"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-kernel-pm-updates] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
