"""
GPU Subsystem seed — open-source knowledge ingestion.

Sources:
  - ARM Mali GPU Architecture white papers (public)
  - Qualcomm Adreno GPU architecture overview (public)
  - OpenGL ES 3.2 specification (Khronos, public)
  - Vulkan 1.3 specification (Khronos, public)
  - Linux Documentation/gpu/ (DRM/KMS)
  - Android GPU Inspector documentation (open-source docs)
  - Perfetto GPU data source documentation

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
# Components — GPU hardware blocks (architecture-agnostic open-source view)
# ---------------------------------------------------------------------------

_GPU_HW_COMPONENTS = [
    ("GPU-frontend",         "gpu-block",   "open",  "GPU command processor / frontend — fetches draw calls from ring buffer, dispatch to shader cores",        "base"),
    ("GPU-shader-core",      "gpu-block",   "open",  "Shader core — SIMD vector ALU, texture unit, L1 cache; executes vertex/fragment/compute workloads",       "base"),
    ("GPU-tiler",            "gpu-block",   "open",  "GPU geometry tiler — tile-based deferred rendering (TBDR) binning pass; outputs per-tile primitive lists","base"),
    ("GPU-rasterizer",       "gpu-block",   "open",  "Rasterizer — converts primitives to fragments; early-Z test, MSAA coverage; feeds fragment shaders",      "base"),
    ("GPU-L2",               "cache",       "open",  "GPU L2 cache — shared across shader cores; write-back; coherent with system cache on ARM GPU via ACE-Lite","base"),
    ("GPU-MMU",              "mmu",         "open",  "GPU MMU — per-process IOVA → PA translation; page fault handling; TLB shootdown on context switch",       "base"),
    ("GPU-job-manager",      "gpu-block",   "open",  "GPU job manager — slot-based command stream; preemption at job boundary; priority scheduling (8 levels)", "base"),
    ("GPU-memory-interface", "gpu-block",   "open",  "GPU memory interface — AXI/ACE-Lite master; read/write channels, QoS arbitration vs display/ISP",         "base"),
    ("GPU-perfcounters",     "pmu",         "open",  "GPU performance counters — fragment active, vertex active, L2 hit rate, external bandwidth; Perfetto GPU source", "base"),
    ("GPU-thermal-zone",     "thermal",     "open",  "GPU thermal zone — junction temperature sensor; trip points: passive (throttle OPP), critical (halt)",    "base"),
]

# ---------------------------------------------------------------------------
# Components — ARM Mali-specific (public architecture info only)
# ---------------------------------------------------------------------------

_MALI_COMPONENTS = [
    ("Mali-GPU",             "gpu",         "ARM",   "ARM Mali GPU — TBDR architecture; Valhall/CSF (Command Stream Frontend) on Mali-G710/G510; CSF replaces JM", "base"),
    ("Mali-CSF",             "gpu-block",   "ARM",   "Mali Command Stream Frontend (CSF) — firmware-based scheduling; replaces Job Manager on Valhall (G57+)",  "base"),
    ("Mali-JM",              "gpu-block",   "ARM",   "Mali Job Manager (JM) — slot-based HW scheduler; 3 slots (fragment/vertex/compute); used up to Mali-G76", "base"),
    ("Mali-shader-core",     "gpu-block",   "ARM",   "Mali shader core — Quad vectorisation, FMA, texture fetch; FP32/FP16/INT8; quad-vectorised architecture", "base"),
    ("Mali-tiler-hw",        "gpu-block",   "ARM",   "Mali HW tiler — on-chip geometry tiling, occlusion culling, hidden surface removal before fragment pass", "base"),
]

# ---------------------------------------------------------------------------
# Components — Render Pipeline (API-level, architecture-agnostic)
# ---------------------------------------------------------------------------

_RENDER_PIPELINE_COMPONENTS = [
    ("render-depth-prepass",  "render-stage","open", "Depth Pre-pass — renders only depth buffer first pass; enables early-Z rejection in main color pass",     "base"),
    ("render-gbuffer",        "render-stage","open", "G-buffer (deferred rendering) — stores albedo/normal/roughness to textures; resolved in lighting pass",   "base"),
    ("render-shadow-map",     "render-stage","open", "Shadow map rendering — depth-only draw call from light POV; PCF or PCSS soft shadow sampling",            "base"),
    ("render-color-pass",     "render-stage","open", "Color render pass — final shading; inputs: G-buffer + shadow maps + IBL; outputs: HDR framebuffer",       "base"),
    ("render-post-process",   "render-stage","open", "Post-process pass — TAA, bloom, tone mapping, FXAA; compute shaders on HDR framebuffer",                  "base"),
    ("render-ui-pass",        "render-stage","open", "UI overlay pass — transparent blending on top of 3D scene; 2D canvas, rounded corners, blur effects",    "base"),
    ("vulkan-render-pass",    "api",         "open", "Vulkan render pass — VkRenderPass defines attachments, subpasses, dependencies; maps to TBDR on-chip",   "base"),
    ("vulkan-pipeline",       "api",         "open", "Vulkan graphics pipeline — VkPipeline (VS+FS+state); pipeline cache reduces driver compile stall",        "base"),
    ("opengl-es-context",     "api",         "open", "OpenGL ES 3.2 context — EGLContext, framebuffer object, VAO, GLSL 3.20 ES; multi-context threading",     "base"),
    ("egl-display",           "api",         "open", "EGL 1.5 display — connects OpenGL ES/Vulkan to DRM/KMS surface; EGLSurface swap chain",                  "base"),
]

# ---------------------------------------------------------------------------
# Components — DRM/KMS (kernel GPU driver framework)
# ---------------------------------------------------------------------------

_DRM_COMPONENTS = [
    ("drm-core",             "framework",   "linux", "Linux DRM core — GEM object lifecycle, PRIME dma-buf export, modeset lock, vblank handling",             "base"),
    ("drm-gem",              "framework",   "linux", "DRM GEM (Graphics Execution Manager) — GPU BO alloc, mmap, fence; replaces TTM for discrete GPUs",       "base"),
    ("drm-kms",              "framework",   "linux", "DRM KMS (Kernel Mode Setting) — CRTC/plane/connector/encoder objects; atomic commit (drm_atomic_state)", "base"),
    ("drm-syncobj",          "framework",   "linux", "DRM sync objects — GPU timeline fence export; used by Vulkan VkFence/VkSemaphore for implicit sync",     "base"),
    ("drm-scheduler",        "framework",   "linux", "DRM GPU scheduler — job queue per ring, priority, timeout, entity (per-context priority); drm_sched_job","base"),
    ("panfrost-driver",      "driver",      "linux", "Mali Midgard/Bifrost/Valhall open-source DRM driver (panfrost); GEM, job manager, devfreq integration", "base"),
    ("drm-panel",            "driver",      "linux", "DRM panel driver — MIPI DSI/LVDS panel; power sequence via DT (panel-simple); connects to DRM encoder",  "base"),
    ("drm-bridge",           "driver",      "linux", "DRM bridge chain — DSI-to-eDP, HDMI encoder; drm_bridge_chain_pre_enable()/post_disable() sequence",    "base"),
]

# ---------------------------------------------------------------------------
# Components — GPU power management
# ---------------------------------------------------------------------------

_GPU_PM_COMPONENTS = [
    ("gpu-devfreq",          "driver",      "linux", "GPU devfreq — frequency/voltage scaling triggered by GPU load; simple_ondemand governor; OPP table",    "base"),
    ("gpu-runtime-pm",       "driver",      "linux", "GPU runtime PM — power domain gating when GPU idle; pm_runtime_autosuspend(delay=50ms) typical",        "base"),
    ("gpu-thermal-cooling",  "driver",      "linux", "GPU thermal cooling device — struct thermal_cooling_device; caps GPU OPP on trip crossing",              "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_GPU_INTERRUPTS = [
    ("IRQ-GPU-JOB",    "SPI", 220, "level-high", "base"),
    ("IRQ-GPU-MMU",    "SPI", 221, "level-high", "base"),
    ("IRQ-GPU-ERR",    "SPI", 222, "level-high", "base"),
    ("IRQ-DISP-VSYNC", "SPI", 223, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — GPU / Rendering
# ---------------------------------------------------------------------------

_GPU_FAILURES = [
    ("gpu-overdraw-throttle",
     "UI rendering FPS drops below 30 fps; GPU fragment time > 16ms; no CPU bottleneck",
     "Overdraw > 3x on screen area; alpha-blended UI layers accumulate fragment cost; measure with: adb shell setprop debug.hwui.overdraw show_overdraw",
     "gpu",
     "Android GPU Inspector overdraw documentation; Vulkan best practices guide",
     "base"),
    ("gpu-draw-call-cpu-stall",
     "GPU utilisation < 30%; CPU thread blocks on vkQueueSubmit / eglSwapBuffers; jank visible",
     "Too many draw calls (>2000/frame); CPU driver overhead per draw call = 5–30us; batch with indirect draw or instancing",
     "gpu",
     "Vulkan spec §5.3 (Command Buffer recording); OpenGL ES best practices",
     "base"),
    ("gpu-thermal-throttle-drop",
     "GPU frequency drops from 850 MHz to 400 MHz during sustained gaming; FPS unstable",
     "GPU junction temperature crossed passive trip point; cooling device caps OPP; improve thermal paste or reduce power budget via GPU OPP table",
     "gpu",
     "Linux thermal framework Documentation/driver-api/thermal/",
     "base"),
    ("gpu-page-fault",
     "Kernel: 'Mali GPU page fault'; GPU MMU bus error; rendering corruption or crash",
     "UAF (use-after-free) GPU buffer: GEM BO released while GPU still reads it; use fence wait before bo_unreference",
     "gpu",
     "Linux DRM syncobj documentation; DRM scheduler fence semantics",
     "base"),
    ("drm-atomic-commit-fail",
     "Display flicker; DRM: 'atomic commit failed'; adb logcat shows SurfaceFlinger timeout",
     "Plane configuration violates hardware constraint (e.g. scaling ratio > 4x, or format not supported by HW); use drm_plane_check_pixel_format()",
     "display",
     "Linux DRM atomic modesetting Documentation/gpu/drm-kms.rst",
     "base"),
    ("gpu-devfreq-stuck",
     "GPU runs at maximum frequency even when screen is idle; battery drain",
     "devfreq governor not receiving busy/idle notifications; check gpu_power_off callback triggers devfreq_monitor_stop()",
     "power",
     "Linux devfreq Documentation/driver-api/devfreq.rst",
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
        _GPU_HW_COMPONENTS + _MALI_COMPONENTS + _RENDER_PIPELINE_COMPONENTS +
        _DRM_COMPONENTS + _GPU_PM_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _GPU_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _GPU_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # GPU HW pipeline
    for src, dst in [
        ("GPU-frontend",      "GPU-job-manager"),
        ("GPU-job-manager",   "GPU-shader-core"),
        ("GPU-job-manager",   "GPU-tiler"),
        ("GPU-tiler",         "GPU-rasterizer"),
        ("GPU-rasterizer",    "GPU-shader-core"),
        ("GPU-shader-core",   "GPU-L2"),
        ("GPU-L2",            "GPU-memory-interface"),
        ("GPU-MMU",           "GPU-memory-interface"),
        ("GPU-perfcounters",  "GPU-shader-core"),
        ("Mali-CSF",          "Mali-shader-core"),
        ("Mali-JM",           "Mali-shader-core"),
        ("Mali-tiler-hw",     "Mali-shader-core"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # Render pipeline dependencies
    for src, dst in [
        ("render-depth-prepass", "GPU-rasterizer"),
        ("render-color-pass",    "GPU-shader-core"),
        ("render-post-process",  "GPU-shader-core"),
        ("vulkan-render-pass",   "GPU-tiler"),
        ("vulkan-pipeline",      "GPU-shader-core"),
        ("opengl-es-context",    "egl-display"),
        ("egl-display",          "drm-kms"),
    ]:
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
                   src_name=src, dst_name=dst)

    # DRM framework
    for src, dst in [
        ("drm-gem",        "drm-core"),
        ("drm-kms",        "drm-core"),
        ("drm-syncobj",    "drm-core"),
        ("drm-scheduler",  "drm-core"),
        ("panfrost-driver","drm-core"),
        ("panfrost-driver","gpu-devfreq"),
        ("drm-panel",      "drm-kms"),
        ("drm-bridge",     "drm-kms"),
    ]:
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
                   src_name=src, dst_name=dst)

    # GPU power management
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="gpu-devfreq", dst_name="gpu-runtime-pm")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="gpu-thermal-cooling", dst_name="gpu-devfreq")

    # GPU DMA to display
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="GPU-memory-interface", dst_name="drm-kms")
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="GPU-memory-interface", dst_name="dma-buf-core")

    # Failure modes
    _fm_causes = [
        ("gpu-overdraw-throttle",   "GPU-rasterizer"),
        ("gpu-draw-call-cpu-stall", "GPU-job-manager"),
        ("gpu-thermal-throttle-drop","gpu-thermal-cooling"),
        ("gpu-page-fault",          "GPU-MMU"),
        ("drm-atomic-commit-fail",  "drm-kms"),
        ("gpu-devfreq-stuck",       "gpu-devfreq"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[gpu-subsystem] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
