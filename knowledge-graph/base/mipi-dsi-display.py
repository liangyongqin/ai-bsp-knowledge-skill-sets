"""
MIPI DSI Display Pipeline seed — open-source knowledge ingestion.

Adds display subsystem components: MIPI DSI-2 interface, DRM/KMS display
pipeline, display controller, and panel management.

Sources:
  - MIPI DSI-2 v2.0/v2.2 specification (mipi.org)
  - Linux kernel Documentation/gpu/drm-kms.rst
  - Linux kernel drivers/gpu/drm/ source code
  - Linux kernel Documentation/devicetree/bindings/display/
  - VESA DSC specification (Display Stream Compression)

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
# Components — MIPI DSI-2 physical interface
# ---------------------------------------------------------------------------

_DSI_PHY = [
    ("MIPI-DSI2-Host",         "display",    "MIPI",
     "MIPI DSI-2 Host Controller — drives display panel via DSI protocol, "
     "supports video mode (continuous pixel clock) and command mode (frame buffer in panel SRAM); "
     "DSI-2 v2.0+ adds video-to-command mode switching and adaptive refresh",
     "base"),
    ("MIPI-DSI2-DPHY",         "phy",        "MIPI",
     "MIPI D-PHY for DSI-2 — differential signaling, 1–4 data lanes + 1 clock lane, "
     "up to 4.5 Gbps/lane (D-PHY v2.5); HS (High Speed) and LP (Low Power) modes",
     "base"),
    ("MIPI-DSI2-CPHY",         "phy",        "MIPI",
     "MIPI C-PHY for DSI-2 — 3-wire signaling, higher bits/symbol (2.28 bits/symbol), "
     "up to 6 Gsps/trio; no separate clock lane; better efficiency for high-resolution panels",
     "base"),
    ("MIPI-DSI2-Panel",        "display",    "generic",
     "MIPI DSI-2 display panel — AMOLED or LCD panel with DSI-2 interface, "
     "supports adaptive refresh rate (variable refresh panel), "
     "VESA DSC for compressed pixel transport",
     "base"),
    ("VESA-DSC",               "codec",      "VESA",
     "VESA Display Stream Compression (DSC) — visually lossless 3:1–6:1 compression, "
     "reduces DSI bandwidth for high-resolution (4K+) panels; "
     "DSC encoder in display controller, decoder in panel",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — DRM/KMS display framework
# ---------------------------------------------------------------------------

_DRM_KMS = [
    ("linux-drm-core",         "framework",  "linux",
     "Linux DRM core (drivers/gpu/drm/drm_*.c) — Direct Rendering Manager, "
     "provides GEM buffer management, DRM IOCTL interface, "
     "modesetting (KMS), and plane/CRTC/connector abstractions",
     "base"),
    ("drm-kms-crtc",           "display",    "linux",
     "DRM CRTC (CRT Controller) — represents the display pipeline: "
     "reads framebuffer, applies gamma/CTM, drives encoder timing; "
     "one CRTC per independent display output",
     "base"),
    ("drm-kms-encoder",        "display",    "linux",
     "DRM Encoder — converts CRTC pixel stream to panel-specific signaling "
     "(DSI, HDMI, DP, LVDS); bridges CRTC to connector",
     "base"),
    ("drm-kms-connector",      "display",    "linux",
     "DRM Connector — represents physical display output (DSI panel, HDMI port); "
     "reports EDID, supported modes, connection status",
     "base"),
    ("drm-kms-plane",          "display",    "linux",
     "DRM Plane — hardware overlay/composition layer; primary plane for main FB, "
     "cursor plane, overlay planes for video/UI composition; "
     "reduces GPU composition load via hardware blending",
     "base"),
    ("drm-kms-bridge",         "display",    "linux",
     "DRM Bridge — intermediate converter in display chain "
     "(e.g., DSI-to-HDMI, DSI-to-eDP); chain of bridges between encoder and panel; "
     "Linux drm_bridge framework manages bridge ordering",
     "base"),
    ("drm-panel",              "display",    "linux",
     "DRM Panel framework (drivers/gpu/drm/panel/) — "
     "abstracts panel init sequences, backlight control, "
     "power-on/off timing; generic panel-simple and vendor-specific drivers",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Display controller (SoC-level)
# ---------------------------------------------------------------------------

_DISPLAY_CONTROLLER = [
    ("display-controller",     "display",    "generic",
     "SoC Display Controller (DPU/MDSS/DISP) — hardware composition engine, "
     "reads framebuffers via AXI, blends planes, applies scaling/rotation, "
     "outputs pixel stream to DSI/HDMI encoder; "
     "Qualcomm: MDSS/DPU; MediaTek: DISP/OVL/RDMA/WDMA",
     "base"),
    ("display-ovl",            "display",    "generic",
     "Display Overlay Engine (OVL) — multi-layer hardware compositor, "
     "blends 4–8 input layers with alpha, color key, and z-order; "
     "output feeds to color processing and DSI encoder",
     "base"),
    ("display-color",          "display",    "generic",
     "Display Color Processing — gamma correction, color matrix transform (CTM), "
     "HDR tone mapping, dithering; hardware pipeline between OVL and encoder",
     "base"),
    ("display-rdma",           "display",    "generic",
     "Display RDMA (Read DMA) — fetches framebuffer pixels from DRAM via AXI; "
     "supports tiled, linear, and AFBC (ARM Frame Buffer Compression) formats; "
     "bandwidth-critical: 4K@120Hz requires ~12 GB/s",
     "base"),
    ("display-dsc-encoder",    "display",    "generic",
     "Display DSC Encoder — hardware VESA DSC compression in display pipeline, "
     "compresses pixel stream before DSI transmission; reduces PHY bandwidth requirement",
     "base"),
    ("display-backlight",      "display",    "linux",
     "Linux backlight framework (drivers/video/backlight/) — "
     "controls panel brightness via PWM or DSI DCS commands; "
     "sysfs at /sys/class/backlight/; integrates with power management",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_DISPLAY_INTERRUPTS = [
    ("IRQ-DSI-TE",             "SPI", 260, "edge-rising", "base"),
    ("IRQ-DSI-UNDERRUN",       "SPI", 261, "level-high",  "base"),
    ("IRQ-DISP-VSYNC",         "SPI", 262, "edge-rising", "base"),
    ("IRQ-DISP-RDMA-DONE",    "SPI", 263, "level-high",  "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_DISPLAY_FAILURES = [
    ("FM-DSI-Underrun",
     "Display shows horizontal tearing or blank bands; DSI underrun interrupt fires",
     "Display RDMA cannot fetch pixels fast enough; DDR bandwidth contention with "
     "camera/GPU; increase RDMA QoS priority or reduce display resolution/refresh rate",
     "display",
     "Linux DRM/KMS documentation, SoC vendor BSP guides",
     "base"),
    ("FM-DSI-Lane-Error",
     "Display shows corrupted image or pink/green stripes; DSI PHY error status set",
     "MIPI DSI D-PHY/C-PHY lane calibration failed; termination impedance mismatch "
     "or PHY PLL not locked; check DSI PHY clock configuration in DT",
     "display",
     "MIPI DSI-2 specification §6 (Error Handling)",
     "base"),
    ("FM-Panel-Init-Fail",
     "Display stays black after boot; panel init sequence returns error or times out",
     "Panel DCS (Display Command Set) init sequence wrong for panel revision; "
     "check panel vendor init table and reset GPIO timing in DT",
     "display",
     "Linux drivers/gpu/drm/panel/ source code",
     "base"),
    ("FM-HDMI-No-Signal",
     "HDMI output shows no signal; hotplug detect works but mode negotiation fails",
     "EDID read fails (I2C SCL/SDA pull-up too weak) or HDMI PHY PLL cannot lock "
     "to requested pixel clock; check I2C and PHY configuration",
     "display",
     "Linux DRM/KMS HDMI documentation",
     "base"),
    ("FM-Display-VRR-Flicker",
     "Display flickers or shows brightness pulsing with variable refresh rate enabled",
     "Panel adaptive refresh rate (VRR) range too narrow; refresh drops below panel minimum "
     "causing re-sync; set minimum VRR floor in DRM connector properties",
     "display",
     "MIPI DSI-2 v2.2 VRR specification",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = _DSI_PHY + _DRM_KMS + _DISPLAY_CONTROLLER
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _DISPLAY_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _DISPLAY_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Display pipeline: RDMA → OVL → Color → DSC Encoder → DSI Host → PHY → Panel
    pipeline = [
        ("display-rdma",        "display-ovl"),
        ("display-ovl",         "display-color"),
        ("display-color",       "display-dsc-encoder"),
        ("display-dsc-encoder", "MIPI-DSI2-Host"),
        ("MIPI-DSI2-Host",      "MIPI-DSI2-DPHY"),
        ("MIPI-DSI2-Host",      "MIPI-DSI2-CPHY"),
        ("MIPI-DSI2-DPHY",      "MIPI-DSI2-Panel"),
        ("MIPI-DSI2-CPHY",      "MIPI-DSI2-Panel"),
    ]
    for src, dst in pipeline:
        create_rel(conn, "STREAMS_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # DSC encoder uses VESA DSC codec
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="display-dsc-encoder", dst_name="VESA-DSC")

    # Display controller encompasses OVL, RDMA, color
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="display-controller", dst_name="display-ovl")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="display-controller", dst_name="display-rdma")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="display-controller", dst_name="display-color")

    # DRM/KMS: CRTC → encoder → connector → panel
    drm_chain = [
        ("drm-kms-crtc",       "drm-kms-encoder"),
        ("drm-kms-encoder",    "drm-kms-connector"),
        ("drm-kms-connector",  "drm-panel"),
        ("drm-kms-crtc",       "drm-kms-plane"),
    ]
    for src, dst in drm_chain:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # DRM bridge in encoder chain
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="drm-kms-encoder", dst_name="drm-kms-bridge")

    # DRM core manages all KMS objects
    for obj in ("drm-kms-crtc", "drm-kms-encoder", "drm-kms-connector",
                "drm-kms-plane", "drm-kms-bridge", "drm-panel"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="linux-drm-core", dst_name=obj)

    # Display controller → DRM CRTC (hardware → software mapping)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="display-controller", dst_name="drm-kms-crtc")

    # Backlight → panel
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="display-backlight", dst_name="drm-panel")

    # RDMA reads from DRAM via AXI
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="display-rdma", dst_name="DDR-Controller",
               rel_props={"channel": "display-rdma", "description": "Display RDMA reads framebuffer from DRAM"})

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-DSI-Underrun",        "display-rdma"),
        ("FM-DSI-Lane-Error",      "MIPI-DSI2-DPHY"),
        ("FM-Panel-Init-Fail",     "drm-panel"),
        ("FM-HDMI-No-Signal",      "drm-kms-connector"),
        ("FM-Display-VRR-Flicker", "MIPI-DSI2-Panel"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[mipi-dsi-display] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
