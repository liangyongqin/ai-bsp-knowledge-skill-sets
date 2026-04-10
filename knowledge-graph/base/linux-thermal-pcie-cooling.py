"""
Linux Kernel 6.12-6.13 Thermal and PM Updates — seed knowledge ingestion.

Sources:
  - Linux kernel 6.12 release notes (kernelnewbies.org/Linux_6.12)
  - Linux kernel 6.13 release notes (kernelnewbies.org/Linux_6.13)
  - Linux Documentation/power/powercap/dtpm.html (Dynamic Thermal Power Management)
  - Linux kernel commit: "thermal: Add PCIe bandwidth controller and cooling driver"
  - Linux kernel commit: "thermal: Add user thresholds support"
  - Linux Documentation/thermal/sysfs-api.txt
  - Patchwork: "[v9,8/9] thermal: Add PCIe cooling driver"

Covers:
  - Thermal user thresholds (kernel 6.13): userspace temperature notifications
  - PCIe bandwidth cooling driver (kernel 6.13): thermal-based PCIe link speed limiting
  - DTPM (Dynamic Thermal Power Management) framework enhancements
  - Thermal debugfs testing module (kernel 6.12)
  - Related failure modes for BSP engineers

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
# Components — Linux 6.12-6.13 thermal/PM additions
# ---------------------------------------------------------------------------

_COMPONENTS = [
    ("thermal-user-thresholds", "framework", "linux",
     "Linux kernel 6.13 thermal user thresholds — userspace API to register "
     "temperature threshold notifications; no hysteresis, just temperature + "
     "direction; delivered via netlink; replaces polling from userspace",
     "base"),
    ("pcie-cooling-driver", "driver", "linux",
     "Linux kernel 6.13 PCIe bandwidth cooling driver (CONFIG_PCIE_THERMAL) — "
     "limits PCIe link speed due to thermal reasons; state 0 = no throttling "
     "(max speed); integrates with thermal zone as a cooling device",
     "base"),
    ("pcie-bandwidth-controller", "driver", "linux",
     "PCIe bandwidth controller — companion to PCIe cooling driver; monitors "
     "PCIe link speed and applies bandwidth limits based on thermal governor "
     "decisions; supports PCIe Gen3/Gen4/Gen5 link speed stepping",
     "base"),
    ("dtpm-framework", "framework", "linux",
     "Dynamic Thermal Power Management (DTPM) framework — hierarchical power "
     "capping for SoC subsystems; aggregates CPU, GPU, and device power budgets; "
     "interface via powercap sysfs; Linux Documentation/power/powercap/dtpm.html",
     "base"),
    ("thermal-debugfs", "debug", "linux",
     "Linux kernel 6.12 thermal debugfs module — enables testing thermal core "
     "functionality via debugfs interface; allows simulation of thermal events "
     "for driver development without physical hardware",
     "base"),
    ("thermal-netlink-v2", "framework", "linux",
     "Linux thermal netlink interface v2 — delivers thermal events to userspace "
     "via generic netlink; supports user threshold notifications (kernel 6.13), "
     "trip point crossing, cooling device state changes",
     "base"),
    ("adaptive-polling-pm", "framework", "linux",
     "Linux kernel 6.13 adaptive network polling — reduces energy consumption "
     "by adjusting poll intervals based on traffic patterns; up to 30% energy "
     "reduction in heavy network traffic; relevant for SoC network accelerators",
     "base"),
    ("carbon-aware-scheduling", "framework", "linux",
     "Linux experimental carbon-aware CPU scheduling — 'Green IT' metrics for "
     "power-proportional computing; adjusts scheduling decisions based on energy "
     "source and grid carbon intensity; experimental patches moving toward mainline",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — thermal/PM specific
# ---------------------------------------------------------------------------

_FAILURES = [
    ("pcie-thermal-throttle-nvme-timeout",
     "NVMe I/O timeout after PCIe link speed reduced by thermal cooling; "
     "dmesg shows 'nvme nvme0: I/O tag timeout' after pcie_cooling state change",
     "PCIe cooling driver reduced link speed but NVMe driver ASPM/L1 substates "
     "not reconfigured for lower speed; check thermal zone trip points and ensure "
     "NVMe driver handles link speed change notification via PCIe bandwidth event",
     "thermal",
     "Linux kernel commit: 'thermal: Add PCIe cooling driver', kernel 6.13",
     "base"),
    ("thermal-user-threshold-missed",
     "Userspace thermal monitor fails to receive temperature notification; "
     "thermal threshold crossed but no netlink event delivered",
     "User threshold registration via thermal sysfs succeeded but netlink socket "
     "not subscribed to THERMAL_GENL_FAMILY; or threshold direction (rising/falling) "
     "not matching actual temperature transition; verify with 'thermal_zone_get_trips'",
     "thermal",
     "Linux kernel 6.13: thermal user thresholds, Documentation/thermal/",
     "base"),
    ("dtpm-power-budget-exceeded",
     "SoC total power exceeds thermal design power (TDP); thermal shutdown triggered "
     "despite per-subsystem power limits configured",
     "DTPM hierarchy does not account for all power consumers; check powercap sysfs "
     "tree for missing subsystems; common with SoC-specific accelerators (NPU, ISP) "
     "not registered as DTPM power zones",
     "power",
     "Linux Documentation/power/powercap/dtpm.html",
     "base"),
    ("thermal-debugfs-false-trip",
     "Thermal zone reports bogus trip point crossing during development; "
     "cooling device activated without real temperature change",
     "thermal debugfs test module still loaded in production kernel; "
     "verify CONFIG_THERMAL_DEBUGFS=n in production .config; "
     "check /sys/kernel/debug/thermal/ for active test injectors",
     "thermal",
     "Linux kernel 6.12 thermal debugfs module",
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

    # PCIe cooling → bandwidth controller
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pcie-cooling-driver", dst_name="pcie-bandwidth-controller")

    # Thermal user thresholds → netlink
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="thermal-user-thresholds", dst_name="thermal-netlink-v2")

    # DTPM → existing thermal framework components
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="dtpm-framework", dst_name="thermal-user-thresholds")

    # PCIe cooling → thermal zone (integrates as cooling device)
    # Link to existing thermal governor if present
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pcie-cooling-driver", dst_name="dtpm-framework")

    # PCIe bandwidth controller → PCIe controller
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pcie-bandwidth-controller", dst_name="PCIe-Controller")

    # Debugfs → thermal framework
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="thermal-debugfs", dst_name="thermal-user-thresholds")

    # Failure → root component
    _fm_causes = [
        ("pcie-thermal-throttle-nvme-timeout", "pcie-cooling-driver"),
        ("thermal-user-threshold-missed", "thermal-user-thresholds"),
        ("dtpm-power-budget-exceeded", "dtpm-framework"),
        ("thermal-debugfs-false-trip", "thermal-debugfs"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-thermal-pcie-cooling] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
