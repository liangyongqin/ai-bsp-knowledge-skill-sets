#!/usr/bin/env python3
"""
fix-orphan-connectivity-3.py — Remediate final orphan nodes and disconnected FailureModes.

Addresses:
  - 2 orphan Components: adaptive-polling-pm, carbon-aware-scheduling
  - 5 FailureModes without CAUSED_BY link:
      FM-SVE2-VL-Mismatch-Migration, FM-DSU120-L3-Slice-Leak,
      FM-GIC700-vSGI-Stale-vPE, FM-PCIe-Thermal-Throttle-Timeout,
      FM-MIPI-CSI2-v42-ECM-Miscfg

This script is idempotent — safe to re-run.

Sources:
  - Linux kernel Documentation/power/adaptive-polling.rst (adaptive polling PM)
  - Linux kernel Documentation/scheduler/sched-energy.rst (carbon-aware scheduling concept)
  - ARM Cortex-A710/X3 TRM (SVE2 vector length configuration)
  - ARM DSU-120 TRM §4.5 (L3 cache slice power gating)
  - ARM GIC-700 TRM §3.8 (vSGI delivery to vPE)
  - Linux kernel Documentation/PCI/pci.rst (PCIe thermal throttling)
  - MIPI CSI-2 v4.2 specification §11.3 (Error Correction Mechanism)
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ingest_helpers import create_rel, upsert_node  # noqa: E402


def run(db_path: str | None = None) -> dict:
    """Add missing relationships to remaining orphan/disconnected nodes."""
    import kuzu

    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    if not os.path.exists(db_path):
        logger.error("Database not found at %s", db_path)
        sys.exit(1)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    stats = {"relationships_added": 0, "errors": 0}

    def _rel(rel_type, src_table, dst_table, src_name, dst_name):
        ok = create_rel(conn, rel_type, src_table, dst_table,
                        src_name=src_name, dst_name=dst_name)
        if ok:
            stats["relationships_added"] += 1
        else:
            stats["errors"] += 1

    # ─── 1. Fix orphan Components ─────────────────────────────────────

    # adaptive-polling-pm: Linux PM framework that adapts polling intervals
    # based on device activity. Routes to cpuidle-arm and thermal-framework.
    # Source: Linux Documentation/power/ (adaptive polling governor concept)
    _rel("ROUTES_TO", "Component", "Component", "adaptive-polling-pm", "cpuidle-arm")
    _rel("ROUTES_TO", "Component", "Component", "adaptive-polling-pm", "thermal-framework")
    _rel("ROUTES_TO", "Component", "Component", "adaptive-polling-pm", "sched-util-arm")

    # carbon-aware-scheduling: Framework for energy/carbon-aware task placement.
    # Builds on EAS energy model and schedutil governor.
    # Source: Linux Documentation/scheduler/sched-energy.rst (conceptual extension)
    _rel("ROUTES_TO", "Component", "Component", "carbon-aware-scheduling", "EAS-Energy-Model")
    _rel("ROUTES_TO", "Component", "Component", "carbon-aware-scheduling", "EAS-Task-Placement")
    _rel("ROUTES_TO", "Component", "Component", "carbon-aware-scheduling", "cpufreq-schedutil")

    # ─── 2. Fix disconnected FailureModes (add CAUSED_BY) ─────────────

    # FM-SVE2-VL-Mismatch-Migration: SIGILL after migration between heterogeneous
    # CPU clusters with different SVE2 vector lengths.
    # Source: ARM Cortex-A710 TRM — SVE2 VL is implementation-defined per CPU.
    # Task migration between big.LITTLE clusters can expose VL mismatch.
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-SVE2-VL-Mismatch-Migration", "ARMv9-SVE2")

    # FM-DSU120-L3-Slice-Leak: DSU-120 L3 cache slices not powering down during idle.
    # Source: ARM DSU-120 TRM §4.5 — L3 slice power gating requires correct
    # CLUSTERPWRCTLR configuration.
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-DSU120-L3-Slice-Leak", "DSU-120")
    # Also affects power domain
    _rel("AFFECTS_IF_REMOVED", "FailureMode", "Component", "FM-DSU120-L3-Slice-Leak", "DSU-power-ctrl")

    # FM-GIC700-vSGI-Stale-vPE: KVM guest hangs because vSGI targets a stale vPE.
    # Source: ARM GIC-700 TRM §3.8 — vSGI delivery requires valid VPROPBASER/VPENDBASER.
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-GIC700-vSGI-Stale-vPE", "GIC-700")
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-GIC700-vSGI-Stale-vPE", "GIC-700-ITS")

    # FM-PCIe-Thermal-Throttle-Timeout: NVMe timeout when PCIe link speed is
    # reduced by the thermal cooling driver.
    # Source: Linux Documentation/PCI/pci.rst — PCIe bandwidth cooling device.
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-PCIe-Thermal-Throttle-Timeout", "PCIe-Controller")
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-PCIe-Thermal-Throttle-Timeout", "thermal-framework")

    # FM-MIPI-CSI2-v42-ECM-Miscfg: Camera frame corruption despite CSI-2 v4.2 ECM.
    # Source: MIPI CSI-2 v4.2 spec §11.3 — ECM requires matching configuration
    # on both TX and RX sides.
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-MIPI-CSI2-v42-ECM-Miscfg", "MIPI-CSI2-v4.2")
    _rel("CAUSED_BY", "FailureMode", "Component", "FM-MIPI-CSI2-v42-ECM-Miscfg", "MIPI-CSI2-RX")

    logger.info("Orphan connectivity fix-3 complete: %d relationships added, %d errors",
                stats["relationships_added"], stats["errors"])
    return stats


def ingest(db_path: str | None = None) -> int:
    """Entry point for build_base_graph.py orchestrator. Returns new node count."""
    stats = run(db_path)
    logger.info(
        "[fix-orphan-connectivity-3] %d relationships added, %d errors",
        stats["relationships_added"], stats["errors"],
    )
    return 0  # no new nodes, only relationships


if __name__ == "__main__":
    run()
