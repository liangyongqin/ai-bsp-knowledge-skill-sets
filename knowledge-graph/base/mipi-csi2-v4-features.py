"""
MIPI CSI-2 v4.0/v4.2 Features — seed knowledge ingestion.

Sources:
  - MIPI CSI-2 Specification Brief (mipi.org/specifications/csi-2)
  - MIPI Alliance: CSI-2 v4.0 feature overview (2023 Embedded Vision Summit)
  - MIPI CSI-2 v4.2 adoption notice (December 15, 2025)
  - MIPI Alliance press releases: Event Sensing and Processing (ESP)
  - Camera Serial Interface Wikipedia (Camera_Serial_Interface)

Covers:
  - Smart Region of Interest (SROI) Phase 1 & Phase 2 (v4.0)
  - Event-Based Vision Sensor support / Event Sensing and Processing (ESP) (v4.2)
  - Multi-Pixel Compression (MPC) for bandwidth reduction (v4.0)
  - Always-On Sentinel Conduit for low-power wake (v4.0)
  - Latency Reduction and Transport Efficiency (LRTE) (v4.0)
  - D-PHY ECM (Error Correction Mode) support (v4.2)
  - Related failure modes for BSP camera engineers

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
# Components — MIPI CSI-2 v4.0/v4.2 features
# ---------------------------------------------------------------------------

_COMPONENTS = [
    ("MIPI-CSI2-SROI", "controller", "MIPI-Alliance",
     "MIPI CSI-2 v4.0 Smart Region of Interest (SROI) — adaptive transfer of "
     "rectangular ROIs (e.g. face, license plate) to reduce data bandwidth; "
     "Phase 1: single/multi-ROI carving from full frame; Phase 2 (ISROI/ESROI): "
     "companion VDSP inferencing with internal and external SROI options",
     "base"),
    ("MIPI-CSI2-ESP", "controller", "MIPI-Alliance",
     "MIPI CSI-2 v4.2 Event Sensing and Processing (ESP) — standardized protocol "
     "support for event-based vision sensors (neuromorphic/dynamic vision sensors); "
     "asynchronous per-pixel change detection; enables always-on low-power "
     "machine vision with microsecond temporal resolution",
     "base"),
    ("MIPI-CSI2-MPC", "controller", "MIPI-Alliance",
     "MIPI CSI-2 v4.0 Multi-Pixel Compression (MPC) — visually lossless "
     "compression of pixel data in the CSI-2 transport layer; reduces bandwidth "
     "requirements between sensor and ISP by up to 50%; works alongside SROI "
     "for compound bandwidth savings",
     "base"),
    ("MIPI-CSI2-Sentinel", "controller", "MIPI-Alliance",
     "MIPI CSI-2 v4.0 Always-On Sentinel Conduit — low-power always-on pathway "
     "for sensor wake/alert signaling; enables camera-based wake triggers "
     "without full CSI-2 link activation; used for presence detection, "
     "automotive driver monitoring sentinel mode",
     "base"),
    ("MIPI-CSI2-LRTE", "controller", "MIPI-Alliance",
     "MIPI CSI-2 v4.0 Latency Reduction and Transport Efficiency (LRTE) — "
     "reduces end-to-end latency from sensor capture to ISP processing; "
     "optimized packet scheduling and interleaving for real-time computer "
     "vision pipelines; critical for ADAS and robotics",
     "base"),
    ("MIPI-DPHY-ECM", "phy", "MIPI-Alliance",
     "MIPI D-PHY Error Correction Mode (ECM) — enhanced error correction for "
     "CSI-2 D-PHY links (v4.2); improves link reliability in high-EMI "
     "environments; forward error correction on data lanes reduces "
     "retransmission overhead for automotive and industrial vision",
     "base"),
    ("EVS-sensor", "sensor", "open",
     "Event-Based Vision Sensor (EVS / Dynamic Vision Sensor) — neuromorphic "
     "sensor that outputs per-pixel brightness changes asynchronously; "
     "microsecond temporal resolution; low power (~10mW); standardized in "
     "MIPI CSI-2 v4.2 ESP; key vendors: Prophesee, Samsung, Sony IMX636",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — CSI-2 v4.0/v4.2 specific
# ---------------------------------------------------------------------------

_FAILURES = [
    ("MIPI-CSI2-SROI-Crop-Mismatch",
     "ISP receives partial frame or corrupted ROI data; V4L2 capture shows "
     "incorrect crop coordinates; dmesg: 'csi2: SROI frame geometry mismatch'",
     "SROI crop parameters configured in sensor do not match ISP input format "
     "expectations; verify SROI ROI coordinates are aligned to pixel group "
     "boundaries (typically 8-pixel aligned); check that ISP input crop is "
     "programmed to match sensor SROI output geometry",
     "multimedia",
     "MIPI CSI-2 v4.0 SROI specification (mipi.org/specifications/csi-2)",
     "base"),
    ("MIPI-CSI2-MPC-Decode-Fail",
     "ISP produces visible artifacts or color banding; raw capture shows "
     "decompression errors in MPC-compressed frames",
     "MPC compression ratio configured in sensor exceeds ISP decoder "
     "capability; or MPC mode (visually lossless vs reduced) not matching "
     "between sensor TX and ISP RX; verify MPC configuration registers on "
     "both ends of CSI-2 link match",
     "multimedia",
     "MIPI CSI-2 v4.0 MPC specification",
     "base"),
    ("MIPI-CSI2-ESP-Event-Drop",
     "Event-based vision sensor data stream has gaps; DVS event rate drops "
     "under high scene activity; ISP reports CSI-2 overflow",
     "ESP event bandwidth exceeds allocated CSI-2 lane capacity during "
     "high-contrast scene transitions; increase D-PHY data rate or reduce "
     "sensor contrast sensitivity threshold; check CSI-2 virtual channel "
     "allocation for ESP vs frame data multiplexing",
     "multimedia",
     "MIPI CSI-2 v4.2 ESP adoption notice (December 2025)",
     "base"),
    ("MIPI-DPHY-ECM-CRC-Storm",
     "CSI-2 link shows excessive CRC errors after enabling D-PHY ECM; "
     "dmesg: 'mipi-csi2: ECM ECC correction count exceeds threshold'",
     "D-PHY ECM enabled on sensor TX but receiver does not support ECM "
     "decoding (older SoC); or ECM FEC overhead not accounted for in link "
     "bandwidth calculation; verify SoC CSI-2 RX supports v4.2 ECM; "
     "disable ECM if RX is pre-v4.2",
     "multimedia",
     "MIPI CSI-2 v4.2 D-PHY ECM specification",
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

    # CSI-2 v4 features → existing MIPI CSI-2 RX
    for feat in ["MIPI-CSI2-SROI", "MIPI-CSI2-ESP", "MIPI-CSI2-MPC",
                 "MIPI-CSI2-Sentinel", "MIPI-CSI2-LRTE"]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=feat, dst_name="MIPI-CSI2-RX")

    # D-PHY ECM → existing D-PHY
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="MIPI-DPHY-ECM", dst_name="MIPI-D-PHY")

    # EVS sensor → ESP controller
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="EVS-sensor", dst_name="MIPI-CSI2-ESP")

    # EVS sensor → existing MIPI CSI-2 RX
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="EVS-sensor", dst_name="MIPI-CSI2-RX")

    # SROI → ISP (reduces data to ISP)
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-CSI2-SROI", dst_name="ISP-pipeline")

    # MPC → ISP
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-CSI2-MPC", dst_name="ISP-pipeline")

    # Sentinel → CSI-2 RX (wake path)
    create_rel(conn, "TRIGGERS", "Component", "Component",
               src_name="MIPI-CSI2-Sentinel", dst_name="MIPI-CSI2-RX")

    # Failure → root component
    _fm_causes = [
        ("MIPI-CSI2-SROI-Crop-Mismatch", "MIPI-CSI2-SROI"),
        ("MIPI-CSI2-MPC-Decode-Fail", "MIPI-CSI2-MPC"),
        ("MIPI-CSI2-ESP-Event-Drop", "MIPI-CSI2-ESP"),
        ("MIPI-DPHY-ECM-CRC-Storm", "MIPI-DPHY-ECM"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[mipi-csi2-v4-features] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
