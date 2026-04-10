"""
ARM GIC-700 Interrupt Controller — seed knowledge ingestion.

Sources:
  - ARM CoreLink GIC-700 TRM (ARM 101516, r4p0, publicly available)
  - ARM GICv4.1 Architecture Specification (ARM IHI 0069)
  - ARM developer.arm.com: "Comparison of GIC-700 and GIC-600"
  - Linux kernel: drivers/irqchip/irq-gic-v3.c, irq-gic-v3-its.c
  - OSDev Wiki: "Generic Interrupt Controller versions 3 and 4"

Covers:
  - GIC-700 component hierarchy (Distributor, Redistributor, ITS, PMU)
  - GICv4.1 enhancements: virtual SGI (vSGI), GICR_INVLPIR, vPE scheduling
  - Multi-die/chiplet support via GIC-700 multi-chip
  - Real-time SPI support (up to 960 RT-SPIs)
  - Scaling: up to 1984 SPIs, 56000 LPIs, 32 ITS blocks
  - Failure modes specific to GIC-700 / GICv4.1

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
# Components — GIC-700
# ---------------------------------------------------------------------------

_COMPONENTS = [
    ("GIC-700", "interrupt_controller", "ARM",
     "ARM CoreLink GIC-700 — GICv4.1 compliant; supports up to 1984 SPIs, "
     "56000 LPIs, 32 ITS blocks; multi-die/chiplet support; core renumbering; "
     "replaces GIC-600 for v9-based SoCs",
     "base"),
    ("GIC-700-Distributor", "gic_sub_component", "ARM",
     "GIC-700 Distributor (GICD) — global SPI routing and prioritization; "
     "up to 1984 SPIs in groups of 32; up to 960 real-time SPIs with "
     "deterministic latency; extended SPI range (SPI 4096-5119)",
     "base"),
    ("GIC-700-Redistributor", "gic_sub_component", "ARM",
     "GIC-700 Redistributor (GICR) — per-CPU interrupt management; "
     "GICv4.1 vPE scheduling via GICR_VPENDBASER; "
     "GICR_INVLPIR for direct LPI invalidation; per-cluster power gating",
     "base"),
    ("GIC-700-ITS", "interrupt_translation_service", "ARM",
     "GIC-700 ITS — up to 32 ITS blocks per chip; MSI/MSI-X LPI translation; "
     "GICv4.1 GITS_SGIR for virtual SGI injection; VMOVP for vPE migration",
     "base"),
    ("GIC-700-PMU", "pmu", "ARM",
     "GIC-700 Performance Monitoring Unit — hardware counters with snapshot "
     "functionality; tracks interrupt latency, LPI processing time, "
     "Distributor/Redistributor utilization",
     "base"),
    ("GICv4.1-Architecture", "architecture_spec", "ARM",
     "ARM GICv4.1 architecture — extends GICv4 with: virtual SGI (vSGI) "
     "direct injection via GITS_SGIR, GICR_INVLPIR for Redistributor-level "
     "LPI invalidation, improved vPE scheduling, reduced hypervisor traps",
     "base"),
    ("GIC-700-Multi-Chip", "gic_sub_component", "ARM",
     "GIC-700 multi-chip controller — enables GIC distribution across "
     "multiple dies in chiplet/socket configurations; coherent interrupt "
     "delivery across chip boundaries",
     "base"),
    ("GIC-700-vSGI-Controller", "gic_sub_component", "ARM",
     "GICv4.1 virtual SGI controller — generates vSGIs by writing to "
     "GITS_SGIR register in ITS; removes hypervisor trap for SGI injection; "
     "critical for KVM vGIC performance",
     "base"),
    ("GIC-700-RT-SPI", "gic_sub_component", "ARM",
     "GIC-700 real-time SPI support — up to 960 RT-SPIs with deterministic "
     "interrupt latency response; prioritized over standard SPIs in Distributor",
     "base"),
]

# ---------------------------------------------------------------------------
# Registers — GIC-700 specific
# ---------------------------------------------------------------------------

_REGISTERS = [
    ("GITS_SGIR", "0x00020", "WO", "0x00000000",
     "GIC-700-ITS",
     "ITS SGI Register — GICv4.1 vSGI generation; write DeviceID+EventID "
     "to inject virtual SGI into target vPE without hypervisor trap",
     "base"),
    ("GICR_INVLPIR", "0x00A0", "WO", "0x00000000",
     "GIC-700-Redistributor",
     "Redistributor LPI Invalidation Register — GICv4.1; invalidate "
     "a single LPI at the Redistributor without ITS INV command",
     "base"),
    ("GICR_VPENDBASER", "0x0078", "RW", "0x00000000",
     "GIC-700-Redistributor",
     "vPE Pending Table Base Register — specifies the vPE currently "
     "scheduled on this Redistributor; controls GICv4.1 direct vLPI delivery",
     "base"),
    ("GICD_SETSPI_NSR", "0x0040", "WO", "0x00000000",
     "GIC-700-Distributor",
     "Distributor Set SPI Register — wire-format SPI assertion via MMIO; "
     "alternative to wired interrupt lines",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts — GIC-700 internal
# ---------------------------------------------------------------------------

_INTERRUPTS = [
    ("SPI-GIC700-Error", "SPI", 350, "level-high", "base"),
    ("SPI-GIC700-PMU-Overflow", "SPI", 351, "level-high", "base"),
    ("SPI-GIC700-Multi-Chip-Sync", "SPI", 352, "edge-rising", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — GIC-700 specific
# ---------------------------------------------------------------------------

_FAILURES = [
    ("gic700-vsgi-delivery-fail",
     "Virtual SGI not delivered to guest VM; KVM vGIC logs 'vSGI pending but not injected'",
     "GICv4.1 vSGI requires GITS_SGIR write with correct vPEID; check ITS "
     "VMAPP command mapped the vPE correctly and GICR_VPENDBASER points to "
     "scheduled vPE; common after vCPU migration between physical CPUs",
     "interrupt",
     "ARM GICv4.1 Architecture Spec §5.4 (Virtual SGIs)",
     "base"),
    ("gic700-lpi-invalidation-stale",
     "Stale LPI delivered after device reset; interrupt fires for unmapped device",
     "LPI not invalidated after device hotplug/reset; use GICR_INVLPIR (GICv4.1) "
     "or ITS INV command to flush; check GICR_CTLR.EnableLPIs state",
     "interrupt",
     "ARM GIC-700 TRM §3.6 (LPI caching and invalidation)",
     "base"),
    ("gic700-multi-chip-routing-fail",
     "Interrupt lost in multi-die SoC; target CPU on remote die never receives SPI",
     "GIC-700 multi-chip routing table misconfigured; check GICD_CHIPR register "
     "and verify inter-die link is operational; often seen during SoC bring-up "
     "when secondary die init sequence is incomplete",
     "interrupt",
     "ARM GIC-700 TRM §6 (Multi-chip support)",
     "base"),
    ("gic700-rt-spi-priority-inversion",
     "Real-time SPI not serviced within deadline; RT task misses latency target",
     "RT-SPI priority lower than active running priority group; check GICD "
     "priority configuration and ensure RT-SPIs use Group0 with highest priority "
     "range; preemption must be enabled in GICD_CTLR",
     "interrupt",
     "ARM GIC-700 TRM §3.3 (Real-time SPIs)",
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

    for name, address, access_type, reset_value, component, desc, ns in _REGISTERS:
        if upsert_node(conn, "Register", {
            "name": name, "address": address, "access_type": access_type,
            "reset_value": reset_value, "component": component,
            "description": desc, "namespace": ns,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # -- Relationships --

    # GIC-700 internal hierarchy
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-Distributor", dst_name="GIC-700-Redistributor")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-Redistributor", dst_name="GICv3-CPU-Interface")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-ITS", dst_name="GIC-700-Redistributor")

    # vSGI controller → ITS
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-vSGI-Controller", dst_name="GIC-700-ITS")

    # Multi-chip → Distributor
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-Multi-Chip", dst_name="GIC-700-Distributor")

    # RT-SPI → Distributor
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-RT-SPI", dst_name="GIC-700-Distributor")

    # GIC-700 → CPU cores (delivery)
    for cpu in ("Cortex-X925-PE", "Cortex-A725-PE", "Cortex-A520-PE"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="GIC-700", dst_name=cpu)

    # PCIe → ITS (MSI via GIC-700)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="PCIe-Controller", dst_name="GIC-700-ITS")

    # GIC-700 PMU → perf
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GIC-700-PMU", dst_name="linux-perf-arm")

    # KVM vGIC → GICv4.1 (virtualization path)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="vGIC-KVM", dst_name="GICv4.1-Architecture")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv4.1-Architecture", dst_name="GIC-700-vSGI-Controller")

    # Failure → root component
    _fm_causes = [
        ("gic700-vsgi-delivery-fail", "GIC-700-vSGI-Controller"),
        ("gic700-lpi-invalidation-stale", "GIC-700-Redistributor"),
        ("gic700-multi-chip-routing-fail", "GIC-700-Multi-Chip"),
        ("gic700-rt-spi-priority-inversion", "GIC-700-RT-SPI"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-gic-700] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
