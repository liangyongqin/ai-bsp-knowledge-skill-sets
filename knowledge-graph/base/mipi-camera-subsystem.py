"""
MIPI Camera Subsystem seed — open-source knowledge ingestion.

Sources:
  - MIPI CSI-2 Specification v3.0 (public summary)
  - Linux Documentation/userspace-api/media/v4l/
  - Linux Documentation/driver-api/media/
  - kernel/drivers/media/v4l2-core/ (V4L2 framework)
  - kernel/drivers/media/i2c/ (sensor drivers)
  - Linux Documentation/driver-api/dma-buf.rst

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
# Components — MIPI PHY / Link Layer
# ---------------------------------------------------------------------------

_MIPI_PHY_COMPONENTS = [
    # name, type, vendor, description, namespace
    ("MIPI-D-PHY",        "phy",          "MIPI-Alliance", "MIPI D-PHY v2.5 — differential lane pair, up to 4.5 Gbps/lane, 1–4 data lanes + 1 clock lane",         "base"),
    ("MIPI-C-PHY",        "phy",          "MIPI-Alliance", "MIPI C-PHY v2.0 — trio signaling, up to 5.7 Gsps/trio, 1–3 trios (higher bandwidth than D-PHY)",        "base"),
    ("MIPI-CSI2-RX",      "controller",   "open",          "MIPI CSI-2 receiver — deserialises D-PHY/C-PHY lanes into pixel stream; implements Long/Short packet framing", "base"),
    ("MIPI-CSI2-TX",      "controller",   "open",          "MIPI CSI-2 transmitter — serialises ISP output to display or companion SoC via D-PHY",                   "base"),
    ("MIPI-CSI2-DPHY-RX", "phy-wrapper",  "open",          "D-PHY + CSI-2 RX wrapper combining PHY calibration, clock recovery, and packet decoder",                 "base"),
    ("MIPI-I3C",          "bus",          "MIPI-Alliance", "MIPI I3C v1.1 — sensor control bus, replaces I2C for camera sensors, supports IBI (In-Band Interrupt)",   "base"),
]

# ---------------------------------------------------------------------------
# Components — Sensor Framework (V4L2 subdev)
# ---------------------------------------------------------------------------

_SENSOR_COMPONENTS = [
    ("v4l2-subdev",          "framework",    "linux", "V4L2 subdev framework — kernel abstraction layer for camera sensor, lens, flash, ISP subdevices", "base"),
    ("v4l2-async",           "framework",    "linux", "V4L2 async notifier — deferred sensor probe until all graph endpoints are available",              "base"),
    ("v4l2-fwnode",          "framework",    "linux", "V4L2 fwnode — parse DT/ACPI endpoint properties (bus-type, data-lanes, clock-lanes, link-freq)", "base"),
    ("media-controller",     "framework",    "linux", "Linux Media Controller — topology graph (entities + pads + links) for pipeline configuration",    "base"),
    ("media-entity",         "framework",    "linux", "Media entity — atomic unit in media controller topology; sources, sinks, and processing blocks",  "base"),
    ("camera-sensor-drv",    "driver",       "linux", "Generic camera sensor driver template (v4l2_subdev + media_entity); controls: gain, exposure, WB", "base"),
    ("camera-lens-drv",      "driver",       "linux", "VCM (Voice Coil Motor) lens autofocus driver; v4l2_ctrl V4L2_CID_FOCUS_ABSOLUTE",                 "base"),
    ("camera-flash-drv",     "driver",       "linux", "LED flash driver; V4L2_CID_FLASH_STROBE for sync with sensor exposure",                           "base"),
    ("cci-bus",              "bus",          "linux", "Camera Control Interface — I2C/I3C register access abstraction for V4L2 sensor drivers",           "base"),
    ("v4l2-ctrl-framework",  "framework",    "linux", "V4L2 control framework — v4l2_ctrl_handler, v4l2_ctrl_new_std; handles exposure/gain/ISO controls", "base"),
]

# ---------------------------------------------------------------------------
# Components — ISP Pipeline
# ---------------------------------------------------------------------------

_ISP_COMPONENTS = [
    ("ISP-frontend",        "isp-block",  "open", "ISP frontend — lens shading correction, black level subtraction, dead pixel correction",         "base"),
    ("ISP-demosaic",        "isp-block",  "open", "Bayer demosaic engine — converts RAW Bayer mosaic to RGB; supports bilinear and malvar algorithms","base"),
    ("ISP-AWB",             "isp-block",  "open", "Auto White Balance block — grey world, perfect reflector, and learned WB estimation",             "base"),
    ("ISP-AE",              "isp-block",  "open", "Auto Exposure block — histogram-based metering, EV calculation, shutter/gain split",              "base"),
    ("ISP-AF",              "isp-block",  "open", "Auto Focus block — contrast-detect (CDAF) statistics; drives VCM lens via CCI",                   "base"),
    ("ISP-3DNR",            "isp-block",  "open", "3D Noise Reduction — temporal+spatial NR; requires DMA reference frame buffer",                   "base"),
    ("ISP-gamma",           "isp-block",  "open", "Gamma / tone mapping block — 1D LUT, HDR tone map (BT.2020 to BT.709 conversion)",               "base"),
    ("ISP-scaler",          "isp-block",  "open", "Multi-stream image scaler — bilinear/lanczos resize; produces preview, video, capture streams",   "base"),
    ("ISP-stats",           "isp-block",  "open", "ISP statistics output — 3A (AWB/AE/AF) stat buffers delivered to 3A library via V4L2 meta",      "base"),
    ("ISP-pipeline",        "isp",        "open", "Complete ISP pipeline — frontend → demosaic → AWB → AE → NR → gamma → scaler",                   "base"),
]

# ---------------------------------------------------------------------------
# Components — DMA-BUF / Memory
# ---------------------------------------------------------------------------

_DMABUF_COMPONENTS = [
    ("dma-buf-core",        "framework",  "linux", "DMA-BUF framework — zero-copy buffer sharing between ISP, GPU, video encoder, display; fd-based",   "base"),
    ("dma-heap",            "allocator",  "linux", "DMA heap allocator — /dev/dma_heap/system and /dev/dma_heap/linux,cma; replaces ION",              "base"),
    ("ion-allocator",       "allocator",  "linux", "ION memory allocator (legacy) — contiguous/system heap for camera-to-GPU zero-copy",               "base"),
    ("v4l2-m2m",            "framework",  "linux", "V4L2 mem-to-mem framework — video codec (H.264/HEVC encoder) pipeline with DMA-BUF support",       "base"),
    ("videobuf2",           "framework",  "linux", "Videobuf2 (VB2) — V4L2 buffer management; MMAP, USERPTR, DMABUF memory models",                   "base"),
    ("cma-heap",            "allocator",  "linux", "Contiguous Memory Allocator heap — physically contiguous buffers for DMA-coherent ISP/video HW",   "base"),
]

# ---------------------------------------------------------------------------
# Components — V4L2 Capture / Encode Pipeline
# ---------------------------------------------------------------------------

_V4L2_PIPELINE_COMPONENTS = [
    ("v4l2-video-dev",      "driver",     "linux", "V4L2 video device (/dev/videoN) — capture, output, m2m node; main userspace interface",            "base"),
    ("v4l2-meta-dev",       "driver",     "linux", "V4L2 meta device — delivers ISP 3A statistics and embedded data in metadata buffer queue",          "base"),
    ("video-encoder-hw",    "encoder",    "open",  "Hardware video encoder — H.264/HEVC/VP9; integrates with V4L2 M2M and DMA-BUF zero-copy",         "base"),
    ("camera-hal3",         "hal",        "android","Android Camera HAL3 — camera3_device_t; request/result model, 3A callback, stream configuration", "base"),
    ("camera2-api",         "api",        "android","Android Camera2 API — CameraCaptureSession, CaptureRequest, ImageReader; HAL3 userspace interface","base"),
    ("camera-hal3-adapter", "hal",        "android","CameraProvider HAL3 adapter — bridges HIDL/AIDL camera HAL interface to kernel V4L2/Media",       "base"),
]

# ---------------------------------------------------------------------------
# Interrupts — MIPI CSI-2 + ISP
# ---------------------------------------------------------------------------

_CAMERA_INTERRUPTS = [
    # name, irq_type, irq_id, trigger, namespace
    ("IRQ-CSI2-ERR",     "SPI", 200, "level-high", "base"),
    ("IRQ-CSI2-FRAME",   "SPI", 201, "level-high", "base"),
    ("IRQ-ISP-EOF",      "SPI", 202, "level-high", "base"),
    ("IRQ-ISP-OVERFLOW", "SPI", 203, "level-high", "base"),
    ("IRQ-ISP-STATS",    "SPI", 204, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — Camera / ISP
# ---------------------------------------------------------------------------

_CAMERA_FAILURES = [
    # name, symptom, root_cause, affected_domain, source, namespace
    ("CSI2-ECC-error",
     "Pink/green pixel artifacts, V4L2 EIO",
     "MIPI D-PHY lane skew > 1 UI; check Teq (equalization termination) value",
     "camera",
     "MIPI CSI-2 v3.0 spec §9.8 (ECC and CRC error handling)",
     "base"),
    ("CSI2-LP-state-stuck",
     "Camera open fails, CSI receiver in LP-11 (no sync)",
     "Sensor not driving LP-01/LP-00 HS-prepare sequence; MCLK absent or wrong freq",
     "camera",
     "MIPI D-PHY v2.5 §5.6 (HS mode entry state machine)",
     "base"),
    ("ISP-overflow-loss",
     "ISP overflow interrupt, frame dropped, V4L2 VIDIOC_DQBUF returns -ENODATA",
     "ISP DMA write bandwidth insufficient; DRAM latency spike during GC or thermal throttle",
     "camera",
     "Linux Documentation/driver-api/dma-buf.rst (DMA-BUF zero-copy requirement)",
     "base"),
    ("3A-tuning-crash",
     "Camera HAL crash / ANR during 3A convergence",
     "ISP stats buffer delivered out of order; stats DMA base address not aligned to 64 bytes",
     "camera",
     "Linux V4L2 meta buffer documentation",
     "base"),
    ("sensor-i2c-nack",
     "Camera open fails: i2c_transfer returns -EREMOTEIO",
     "Sensor AVDD/DOVDD power sequence violated; MCLK not stable before I2C access",
     "camera",
     "Generic camera sensor driver best practices (kernel/drivers/media/i2c/)",
     "base"),
    ("dmabuf-cache-incoherency",
     "GPU render uses stale ISP data; corruption visible in preview",
     "DMA-BUF not flushed before CPU/GPU access; missing dma_buf_begin_cpu_access()",
     "camera",
     "Linux Documentation/driver-api/dma-buf.rst §Cache coherency",
     "base"),
]


def ingest(db_path: str = None) -> int:
    """Ingest MIPI camera subsystem knowledge into the base graph.

    Parameters
    ----------
    db_path:
        Path to the Kuzu database directory.

    Returns
    -------
    int
        Total number of nodes inserted (skips existing).
    """
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    # MIPI PHY / Link Layer
    for name, ctype, vendor, desc, ns in _MIPI_PHY_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # Sensor Framework
    for name, ctype, vendor, desc, ns in _SENSOR_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # ISP Pipeline blocks
    for name, ctype, vendor, desc, ns in _ISP_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # DMA-BUF / Memory
    for name, ctype, vendor, desc, ns in _DMABUF_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # V4L2 pipeline
    for name, ctype, vendor, desc, ns in _V4L2_PIPELINE_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # Interrupts
    for name, irq_type, irq_id, trigger, ns in _CAMERA_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    # Failure modes
    for name, symptom, root_cause, affected_domain, source, ns in _CAMERA_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # MIPI PHY → CSI-2 RX (STREAMS_TO: PHY delivers lanes to CSI-2 protocol layer)
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-D-PHY", dst_name="MIPI-CSI2-RX")
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-C-PHY", dst_name="MIPI-CSI2-RX")
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-CSI2-DPHY-RX", dst_name="MIPI-CSI2-RX")

    # CSI-2 RX → ISP (raw pixel stream)
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-CSI2-RX", dst_name="ISP-frontend")

    # ISP pipeline internal chain
    for src, dst in [
        ("ISP-frontend",  "ISP-demosaic"),
        ("ISP-demosaic",  "ISP-AWB"),
        ("ISP-AWB",       "ISP-AE"),
        ("ISP-AE",        "ISP-3DNR"),
        ("ISP-3DNR",      "ISP-gamma"),
        ("ISP-gamma",     "ISP-scaler"),
        ("ISP-scaler",    "ISP-stats"),
        ("ISP-frontend",  "ISP-pipeline"),
        ("ISP-pipeline",  "ISP-scaler"),
    ]:
        create_rel(conn, "STREAMS_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # ISP → DMA-BUF (output buffer path)
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="ISP-scaler", dst_name="dma-buf-core")
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="ISP-stats", dst_name="v4l2-meta-dev")

    # DMA-BUF → video encoder
    create_rel(conn, "DMA_TO", "Component", "Component",
               src_name="dma-buf-core", dst_name="video-encoder-hw")

    # V4L2 framework dependencies
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="v4l2-subdev", dst_name="media-controller")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="camera-sensor-drv", dst_name="v4l2-subdev")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="videobuf2", dst_name="dma-buf-core")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="camera-hal3", dst_name="v4l2-video-dev")

    # Sensor → CSI-2 (physical lane connection)
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="camera-sensor-drv", dst_name="MIPI-D-PHY")

    # Sensor → CCI (register access)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="camera-sensor-drv", dst_name="cci-bus")

    # Failure mode → root component (CAUSED_BY)
    _fm_causes = [
        ("CSI2-ECC-error",       "MIPI-D-PHY"),
        ("CSI2-LP-state-stuck",  "MIPI-CSI2-RX"),
        ("ISP-overflow-loss",    "ISP-pipeline"),
        ("3A-tuning-crash",      "ISP-stats"),
        ("sensor-i2c-nack",      "cci-bus"),
        ("dmabuf-cache-incoherency", "dma-buf-core"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[mipi-camera-subsystem] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
