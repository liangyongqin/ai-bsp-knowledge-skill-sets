"""
Linux Panthor DRM Driver / Mali CSF GPU — seed knowledge ingestion.

Sources:
  - Collabora blog: "PanCSF: A new DRM driver for Mali CSF-based GPUs" (2023)
  - Collabora blog: "Release the panthor!" (2024)
  - Collabora blog: "Taming the Panthor: OpenGL ES 3.1 conformance on Mali-G610"
  - Linux kernel docs: Documentation/gpu/panthor.html (kernel 6.10+)
  - Linux kernel docs: Documentation/gpu/panfrost.html
  - LWN.net: "drm: Add a driver for CSF-based Mali GPUs"
  - Phoronix: "Linux 6.14 DRM Feature Pull" (Panfrost MT8188 support)

Covers:
  - Panthor kernel driver architecture (Command Stream Frontend, firmware scheduling)
  - CSF vs JM (Job Manager) scheduling model
  - drm_sched integration for dependency tracking
  - Mali-G310/G510/G610/G710 10th-gen GPU support
  - Panfrost improvements: MT8188 Mali-G57 MC3 (kernel 6.14)
  - Related failure modes for BSP GPU engineers

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
# Components — Panthor / Mali CSF driver
# ---------------------------------------------------------------------------

_COMPONENTS = [
    ("panthor-drm-driver", "driver", "linux",
     "Linux Panthor DRM driver — kernel driver for Mali CSF-based 10th-gen GPUs "
     "(G310, G510, G610, G710); uses Command Stream Frontend (CSF) for "
     "firmware-assisted GPU job scheduling; separate from Panfrost (JM-based); "
     "merged in Linux 6.10; Vulkan-friendly uAPI design",
     "base"),
    ("mali-csf-firmware", "firmware", "ARM",
     "Mali CSF (Command Stream Frontend) firmware — runs on GPU MCU; handles "
     "job scheduling, preemption, and queue management offloaded from CPU; "
     "firmware-assisted scheduling reduces CPU overhead; supports priority-based "
     "queue groups and fine-grained preemption",
     "base"),
    ("mali-csf-queue-group", "gpu-block", "ARM",
     "Mali CSF Queue Group — logical grouping of GPU command queues managed by "
     "CSF firmware; each group has priority level; firmware handles inter-queue "
     "scheduling and preemption; replaces JM slot-based model",
     "base"),
    ("drm-sched-framework", "framework", "linux",
     "DRM GPU scheduler (drm_sched) — kernel framework for GPU job scheduling; "
     "provides hardware queue abstraction (drm_gpu_scheduler), job dependency "
     "tracking, and scheduling entities (drm_sched_entity); used by Panthor, "
     "Panfrost, AMD, and other DRM drivers; Intel working on firmware-assisted "
     "scheduling support in drm_sched",
     "base"),
    ("panfrost-mt8188", "driver", "linux",
     "Panfrost DRM driver MT8188 support — added in Linux 6.14; enables "
     "MediaTek MT8188 Mali-G57 MC3 GPU; Panfrost covers JM-based Mali GPUs "
     "(Midgard, Bifrost); uses drm_sched for job scheduling",
     "base"),
    ("mali-g710", "gpu", "ARM",
     "ARM Mali-G710 — 10th-gen Valhall GPU; 16 shader cores; CSF command "
     "stream frontend; hardware ray tracing; variable rate shading; "
     "supported by Panthor driver in mainline Linux",
     "base"),
    ("mali-g610", "gpu", "ARM",
     "ARM Mali-G610 — 10th-gen Valhall GPU; 6 shader cores; CSF-based; "
     "OpenGL ES 3.1 conformant via Panthor + Mesa; found in RK3588 SoC; "
     "first Mali GPU with mainline open-source Vulkan path",
     "base"),
    ("gpu-devcoredump", "debug", "linux",
     "GPU devcoredump — kernel mechanism for capturing GPU crash state; "
     "Panthor/Panfrost dump GPU registers, MMU fault info, and firmware state "
     "to /sys/class/devcoredump/; critical for BSP GPU debug; parsed by "
     "apitrace and gpu-trace tools",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — Panthor/CSF GPU specific
# ---------------------------------------------------------------------------

_FAILURES = [
    ("panthor-csf-fw-timeout",
     "GPU jobs stall; dmesg: 'panthor: CSF firmware timeout, group N'; "
     "GPU hang recovery triggered; applications see EGL_CONTEXT_LOST",
     "CSF firmware unresponsive due to MCU clock gating issue or firmware "
     "version incompatibility; verify GPU firmware version matches kernel "
     "driver expectations; check GPU MCU clock is not gated during active "
     "queue processing; inspect devcoredump for firmware state",
     "gpu",
     "Collabora: 'PanCSF: A new DRM driver for Mali CSF-based GPUs'",
     "base"),
    ("panthor-queue-priority-inversion",
     "Low-priority GPU workload blocks high-priority rendering; frame drops "
     "during compositing; Perfetto shows GPU queue scheduling delay",
     "CSF queue group priorities not configured correctly; high-priority "
     "compositing queue and low-priority compute queue in same group; "
     "separate into distinct queue groups with appropriate priority levels; "
     "verify drm_sched entity priorities match application expectations",
     "gpu",
     "Linux kernel docs: Documentation/gpu/panthor.html",
     "base"),
    ("panfrost-mt8188-opp-mismatch",
     "Mali-G57 MC3 on MT8188 fails to reach peak frequency; dmesg: "
     "'panfrost: Failed to set OPP'; GPU benchmark scores lower than expected",
     "GPU OPP table in device tree does not match actual MT8188 GPU frequency "
     "table; verify DT gpu-opp-table entries against MT8188 datasheet; "
     "check regulator supply voltage for highest OPP corner",
     "gpu",
     "Phoronix: 'Linux 6.14 DRM Feature Pull'",
     "base"),
    ("drm-sched-deadlock-fence",
     "GPU job submission hangs; dmesg: 'drm_sched: job timeout on ring N'; "
     "system becomes unresponsive if GPU is display controller",
     "Circular fence dependency between drm_sched entities; compute job "
     "waiting on render job fence while render job waits on compute output; "
     "review job submission order and fence signaling graph; ensure no "
     "implicit sync dependencies create cycles across sched entities",
     "gpu",
     "Linux kernel drm_sched framework (drivers/gpu/drm/scheduler/)",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    for name, ctype, vendor, desc, ns in _COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # -- Relationships --

    # Panthor driver → CSF firmware
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="panthor-drm-driver", dst_name="mali-csf-firmware")
    # Panthor → drm_sched
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panthor-drm-driver", dst_name="drm-sched-framework")

    # CSF firmware → queue groups
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mali-csf-firmware", dst_name="mali-csf-queue-group")

    # GPU hardware → Panthor driver
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mali-g710", dst_name="panthor-drm-driver")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mali-g610", dst_name="panthor-drm-driver")

    # Panfrost MT8188 → drm_sched
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panfrost-mt8188", dst_name="drm-sched-framework")

    # GPU devcoredump → Panthor
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="gpu-devcoredump", dst_name="panthor-drm-driver")

    # Panthor → existing GPU subsystem components
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panthor-drm-driver", dst_name="GPU-job-manager")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="panthor-drm-driver", dst_name="GPU-MMU")

    # Mali G710/G610 → existing GPU shader core / L2
    for gpu in ["mali-g710", "mali-g610"]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=gpu, dst_name="GPU-shader-core")
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=gpu, dst_name="GPU-L2")

    # Failure → root component
    _fm_causes = [
        ("panthor-csf-fw-timeout", "panthor-drm-driver"),
        ("panthor-queue-priority-inversion", "mali-csf-queue-group"),
        ("panfrost-mt8188-opp-mismatch", "panfrost-mt8188"),
        ("drm-sched-deadlock-fence", "drm-sched-framework"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-panthor-drm-csf] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
