"""
MIPI CSI-2 v4.2 Event-Based Vision & Linux thermal netlink seed.

Adds:
  - MIPI CSI-2 v4.2 features: event-based vision sensor (EVS) protocol support,
    D-PHY Error Correction Mode (ECM), Multi-Pixel Compression (MPC)
  - Linux 6.13 thermal user thresholds via netlink (detailed subsystem view)
  - MIPI C-PHY v3.1, M-PHY v6.0, RFFE v3.2 (December 2025 releases)

Sources:
  - MIPI Alliance: CSI-2 v4.2 adopted 2025-12-15
  - MIPI Alliance: C-PHY v3.1, M-PHY v6.0, RFFE v3.2 (2025-12)
  - KernelNewbies: Linux 6.13 thermal features
  - Linux kernel Documentation/driver-api/thermal/
  - Linux kernel drivers/thermal/thermal_netlink.c

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
# Components — MIPI CSI-2 v4.2 features
# ---------------------------------------------------------------------------

_CSI2_V42_COMPONENTS = [
    ("MIPI-CSI2-v4.2",        "protocol",   "MIPI",
     "MIPI CSI-2 v4.2 (adopted 2025-12-15) — adds event-based vision sensor (EVS) "
     "protocol support, D-PHY Error Correction Mode (ECM) for improved signal integrity, "
     "and Multi-Pixel Compression (MPC) pseudo-code clarifications",
     "base"),
    ("MIPI-CSI2-EVS",         "protocol",   "MIPI",
     "MIPI CSI-2 Event-Based Vision Sensor (EVS) support — standardized protocol "
     "for event-driven image sensors (neuromorphic/dynamic vision sensors); "
     "each pixel reports only brightness changes asynchronously; "
     "ultra-low latency (<1ms), low bandwidth, high dynamic range (>120dB); "
     "applications: robotics, ADAS, industrial inspection, AR/VR eye tracking",
     "base"),
    ("MIPI-CSI2-ECM",         "protocol",   "MIPI",
     "MIPI CSI-2 D-PHY Error Correction Mode (ECM) — enhanced error correction "
     "for CSI-2 packet headers on D-PHY; detects and corrects multi-bit errors; "
     "improves reliability on long flex cables and in high-EMI environments; "
     "mandatory for automotive camera links per CSI-2 v4.2",
     "base"),
    ("MIPI-CSI2-MPC",         "protocol",   "MIPI",
     "MIPI CSI-2 Multi-Pixel Compression (MPC) — lossless/near-lossless compression "
     "of pixel data on CSI-2 link; reduces bandwidth by 40-60% for RAW Bayer data; "
     "CSI-2 v4.2 includes pseudo-code clarifications for decoder implementation",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — MIPI PHY updates (December 2025)
# ---------------------------------------------------------------------------

_MIPI_PHY_UPDATES = [
    ("MIPI-CPHY-v3.1",        "phy",        "MIPI",
     "MIPI C-PHY v3.1 (2025-12) — 3-wire differential PHY for camera/display; "
     "higher data rates per lane than D-PHY; uses trio signaling encoding; "
     "combined with D-PHY in CSI-2 for flexible lane configurations",
     "base"),
    ("MIPI-MPHY-v6.0",        "phy",        "MIPI",
     "MIPI M-PHY v6.0 (2025-12) — high-speed serializer/deserializer PHY; "
     "used by UFS storage (HS-Gear4+), UniPro, and SSIC; "
     "HS line rates up to 11.6 Gbps; PWM-G1 for low-power; "
     "improved power state transitions for faster UFS wake-up",
     "base"),
    ("MIPI-RFFE-v3.2",        "protocol",   "MIPI",
     "MIPI RFFE v3.2 (2025-12) — RF Front-End control interface; "
     "controls PA, LNA, antenna tuner, and switch modules in mobile RF chain; "
     "half-duplex serial bus with trigger support for timing-critical RF switching",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Linux 6.13 thermal netlink user thresholds (expanded)
# ---------------------------------------------------------------------------

_THERMAL_NETLINK_COMPONENTS = [
    ("thermal-netlink",        "framework",  "linux",
     "Linux thermal netlink interface — genetlink family for thermal zone discovery, "
     "temperature events, trip point notifications, and cooling device state changes; "
     "replaces polling of sysfs for userspace thermal management daemons",
     "base"),
    ("thermal-netlink-threshold", "framework", "linux",
     "Linux thermal netlink user thresholds (6.13) — userspace can add/remove "
     "temperature threshold notifications via netlink; thermal framework sends "
     "NL event when threshold is crossed; enables adaptive thermal policies "
     "without modifying DT trip points or kernel config",
     "base"),
    ("thermal-netlink-sampling", "framework", "linux",
     "Linux thermal netlink sampling events — periodic temperature readings "
     "delivered to userspace via netlink; enables thermal logging and trend "
     "analysis without sysfs polling; configurable sample rate per zone",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_FAILURE_MODES = [
    ("FM-EVS-Timestamp-Drift",
     "Event-based vision sensor data shows timestamp drift; object tracking loses accuracy",
     "EVS pixel events have monotonic timestamps from sensor clock; if sensor clock drifts "
     "from SoC system clock, event timestamps become inaccurate; synchronize via CSI-2 "
     "embedded timestamp or PTP clock; check sensor clock source and crystal accuracy",
     "multimedia", "MIPI CSI-2 v4.2 specification — EVS protocol", "medium"),
    ("FM-CSI2-ECM-Overhead",
     "Camera frame rate drops after enabling D-PHY ECM; bandwidth insufficient",
     "ECM adds error correction overhead to CSI-2 packet headers, reducing effective "
     "data bandwidth by ~3-5%; either increase D-PHY lane speed or reduce frame resolution; "
     "check if CSI-2 receiver supports ECM mode in hardware",
     "multimedia", "MIPI CSI-2 v4.2 specification — ECM", "low"),
    ("FM-Thermal-Netlink-Threshold-Missed",
     "Userspace thermal daemon misses temperature threshold crossing; throttling delayed",
     "Netlink socket buffer overflow under heavy system load; thermal threshold event "
     "dropped by kernel; increase netlink socket receive buffer size (SO_RCVBUF) "
     "or use dedicated high-priority netlink group for thermal events",
     "thermal", "Linux kernel 6.13 thermal netlink documentation", "medium"),
    ("FM-MPHY-Gear-Negotiate-Fail",
     "UFS link negotiation fails at HS-Gear4; falls back to HS-Gear3 with reduced bandwidth",
     "M-PHY v6.0 HS-Gear4 requires tighter PLL jitter spec; if PHY PLL exceeds jitter "
     "budget, gear negotiation fails; check UniPro PA_TxHsG4RateSeriesA parameter "
     "and PHY reference clock quality; may need board-level SI improvements",
     "storage", "MIPI M-PHY v6.0 specification / UFS JEDEC spec", "medium"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _CSI2_V42_COMPONENTS + _MIPI_PHY_UPDATES +
        _THERMAL_NETLINK_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
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

    # CSI-2 v4.2 features → CSI-2 receiver
    for src, dst in [
        ("MIPI-CSI2-v4.2",   "MIPI-CSI2-RX"),
        ("MIPI-CSI2-EVS",    "MIPI-CSI2-v4.2"),
        ("MIPI-CSI2-ECM",    "MIPI-CSI2-v4.2"),
        ("MIPI-CSI2-MPC",    "MIPI-CSI2-v4.2"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=src, dst_name=dst)

    # EVS → ISP pipeline (event stream processing)
    create_rel(conn, "STREAMS_TO", "Component", "Component",
               src_name="MIPI-CSI2-EVS", dst_name="ISP-Controller")

    # PHY updates → existing components
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="MIPI-CPHY-v3.1", dst_name="MIPI-CSI2-RX")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="MIPI-MPHY-v6.0", dst_name="UFS-M-PHY")

    # Thermal netlink → thermal core
    for src in ["thermal-netlink", "thermal-netlink-threshold", "thermal-netlink-sampling"]:
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
                   src_name=src, dst_name="linux-thermal-core")

    # Threshold → user threshold (existing node)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="thermal-netlink-threshold", dst_name="thermal-user-threshold")

    # Failure modes → components
    for fm, comp in [
        ("FM-EVS-Timestamp-Drift",            "MIPI-CSI2-EVS"),
        ("FM-CSI2-ECM-Overhead",              "MIPI-CSI2-ECM"),
        ("FM-Thermal-Netlink-Threshold-Missed", "thermal-netlink-threshold"),
        ("FM-MPHY-Gear-Negotiate-Fail",       "MIPI-MPHY-v6.0"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm, dst_name=comp)

    print(f"[mipi-evs-thermal-netlink] Inserted {inserted} nodes.")
    return inserted


if __name__ == "__main__":
    ingest()
