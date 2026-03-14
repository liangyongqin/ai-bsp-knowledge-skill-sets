"""
ARM GIC-600 Interrupt Controller — seed knowledge ingestion.

Ingests open-source documented knowledge about the ARM GIC-600 interrupt
controller (ARM GIC-600 TRM, publicly available) into the BSP knowledge graph.

Covers:
  - GIC-600 component node and sub-components (Distributor, Redistributor, ITS)
  - GICv3 / GICv4 architecture nodes
  - Interrupt type nodes: SPI, PPI, SGI, LPI (with ID ranges per ARM spec)
  - ITS table entries and MSI frame nodes
  - Key ROUTES_TO and TRANSLATES relationships

Reference: ARM GIC-600 TRM (ARM IHI0069), ARM GICv3/v4 Architecture Spec
"""

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

_COMPONENTS = [
    ("GIC-600", "interrupt_controller", "ARM GIC-600 CoreLink interrupt controller, supports GICv3/v4", "base", "ARM", "r0p0"),
    ("GIC-600-Distributor", "gic_sub_component", "GIC-600 Distributor (GICD): global interrupt routing and prioritization", "base", "ARM", "r0p0"),
    ("GIC-600-Redistributor", "gic_sub_component", "GIC-600 Redistributor (GICR): per-CPU interrupt management and LPI support", "base", "ARM", "r0p0"),
    ("GIC-600-ITS", "interrupt_translation_service", "GIC-600 Interrupt Translation Service for MSI/MSI-X LPI delivery", "base", "ARM", "r0p0"),
    ("GICv3-Architecture", "architecture_spec", "ARM GICv3 architecture: affinity routing, SGI via ICC, LPI support", "base", "ARM", "GICv3"),
    ("GICv4-Architecture", "architecture_spec", "ARM GICv4 architecture: adds direct injection of virtual LPIs into VMs", "base", "ARM", "GICv4"),
    ("GICv3-CPU-Interface", "gic_sub_component", "GICv3 CPU interface registers: ICC_SRE_EL1, ICC_IAR1_EL1, ICC_EOIR1_EL1", "base", "ARM", "GICv3"),
    ("GIC-600-vPE-Table", "gic_data_structure", "GIC-600 vPE configuration table for GICv4 direct vLPI injection", "base", "ARM", "r0p0"),
    ("GIC-600-LPI-Config-Table", "gic_data_structure", "GIC-600 LPI configuration table in memory (GICR_PROPBASER)", "base", "ARM", "r0p0"),
    ("GIC-600-LPI-Pending-Table", "gic_data_structure", "GIC-600 LPI pending table per Redistributor (GICR_PENDBASER)", "base", "ARM", "r0p0"),
    ("ITS-Device-Table", "gic_data_structure", "ITS Device Table: maps DeviceID to ITT base address", "base", "ARM", "r0p0"),
    ("ITS-Interrupt-Translation-Table", "gic_data_structure", "ITS Interrupt Translation Table (ITT): maps EventID to INTID + collection", "base", "ARM", "r0p0"),
    ("ITS-Collection-Table", "gic_data_structure", "ITS Collection Table: maps CollectionID to target Redistributor", "base", "ARM", "r0p0"),
    ("ITS-Command-Queue", "gic_data_structure", "ITS command queue in memory for MAPD/MAPC/MAPTI/INT/INV commands", "base", "ARM", "r0p0"),
    ("ARM-Cortex-A55", "cpu_core", "ARM Cortex-A55 efficiency CPU core, supports GICv3 system register interface", "base", "ARM", "r0p1"),
    ("ARM-Cortex-A76", "cpu_core", "ARM Cortex-A76 performance CPU core, GICv3/4 system register interface", "base", "ARM", "r1p0"),
    ("ARM-Cortex-A78", "cpu_core", "ARM Cortex-A78 performance CPU core, GICv4 direct vLPI support", "base", "ARM", "r0p0"),
    ("PCIe-Controller", "bus_controller", "PCIe root complex, issues MSI/MSI-X via ITS LPI mechanism", "base", "generic", ""),
    ("USB3-Controller", "bus_controller", "USB 3.x host controller, uses SPI interrupts for transfer completion", "base", "generic", ""),
    ("PMIC-Interrupt-Pin", "power_management_ic", "PMIC interrupt output pin connected to SoC SPI interrupt line", "base", "generic", ""),
    ("Thermal-Sensor-Controller", "thermal", "On-die thermal sensor interrupt source (TSENS), SPI-based", "base", "generic", ""),
    ("WDT-Watchdog-Timer", "timer", "Watchdog timer interrupt source, connected via SPI", "base", "generic", ""),
    ("ARM-Generic-Timer", "timer", "ARM Generic Timer (CNTPCT_EL0), PPI-based per-CPU timer interrupt", "base", "ARM", ""),
    ("vGIC-KVM", "virtualization", "KVM ARM virtual GIC (vGIC) emulation layer for guest VMs", "base", "KVM", ""),
    ("GIC-600-Hypervisor-IF", "gic_sub_component", "GIC-600 hypervisor interface registers (GICH_*) for list register management", "base", "ARM", "r0p0"),
    ("SDIO-Controller", "bus_controller", "SDIO/eMMC controller, SPI interrupt for card detect and transfer complete", "base", "generic", ""),
    ("SPI-NOR-Controller", "bus_controller", "SPI NOR flash controller with completion SPI interrupt", "base", "generic", ""),
    ("DMA-Controller", "dma", "System DMA controller generating SPI completion interrupts", "base", "generic", ""),
    ("GPU-Controller", "gpu", "GPU core generating SPI interrupts for command queue completions", "base", "generic", ""),
    ("ISP-Controller", "multimedia", "Image Signal Processor generating SPI interrupts per frame", "base", "generic", ""),
    ("MIPI-CSI2-RX", "multimedia", "MIPI CSI-2 receiver, generates SPI interrupt on frame-end", "base", "generic", ""),
    ("IPI-Mailbox", "ipc", "Inter-Processor Interrupt mailbox using SGI 0-7 for core-to-core IPC", "base", "generic", ""),
    ("Secure-World-Monitor", "security", "ARM TrustZone secure monitor, uses Group0 SGIs for secure notifications", "base", "ARM", ""),
    ("SMMU-v3", "iommu", "ARM SMMUv3 stream-based translation, issues SPI for fault events", "base", "ARM", "r0p0"),
    ("GIC-600-Power-Controller", "power_management", "GIC-600 power controller for Redistributor power gating per cluster", "base", "ARM", "r0p0"),
]

_INTERRUPTS = [
    ("SGI-0", "SGI", 0, "Software Generated Interrupt 0 — typically used for IPI reschedule", "base", "edge"),
    ("SGI-1", "SGI", 1, "Software Generated Interrupt 1 — IPI call function", "base", "edge"),
    ("SGI-2", "SGI", 2, "Software Generated Interrupt 2 — IPI call function single", "base", "edge"),
    ("SGI-3", "SGI", 3, "Software Generated Interrupt 3 — IPI CPU stop", "base", "edge"),
    ("SGI-4", "SGI", 4, "Software Generated Interrupt 4 — IPI timer broadcast", "base", "edge"),
    ("SGI-5", "SGI", 5, "Software Generated Interrupt 5 — IPI IRQ work", "base", "edge"),
    ("SGI-6", "SGI", 6, "Software Generated Interrupt 6 — IPI completion", "base", "edge"),
    ("SGI-7", "SGI", 7, "Software Generated Interrupt 7 — secure monitor SGI", "base", "edge"),
    ("PPI-16", "PPI", 16, "PPI 16 — virtual maintenance interrupt (EL2 hypervisor)", "base", "level"),
    ("PPI-17", "PPI", 17, "PPI 17 — hypervisor timer (EL2) CNTHP_EL2", "base", "level"),
    ("PPI-18", "PPI", 18, "PPI 18 — virtual timer CNTV_EL0", "base", "level"),
    ("PPI-19", "PPI", 19, "PPI 19 — fast IRQ (legacy FIQ)", "base", "level"),
    ("PPI-26", "PPI", 26, "PPI 26 — non-secure EL1 physical timer CNTP_EL0", "base", "level"),
    ("PPI-27", "PPI", 27, "PPI 27 — secure EL1 physical timer CNTS_EL0", "base", "level"),
    ("SPI-32", "SPI", 32, "SPI 32 — first Shared Peripheral Interrupt slot", "base", "level"),
    ("SPI-PMIC", "SPI", 64, "SPI 64 — PMIC interrupt (typical assignment)", "base", "level"),
    ("SPI-USB3", "SPI", 96, "SPI 96 — USB3 host controller interrupt", "base", "level"),
    ("SPI-PCIe", "SPI", 128, "SPI 128 — PCIe root complex interrupt", "base", "level"),
    ("SPI-DMA", "SPI", 160, "SPI 160 — DMA controller completion interrupt", "base", "level"),
    ("SPI-GPU", "SPI", 192, "SPI 192 — GPU command queue completion interrupt", "base", "level"),
    ("SPI-ISP", "SPI", 224, "SPI 224 — ISP frame-done interrupt", "base", "level"),
    ("SPI-Thermal", "SPI", 256, "SPI 256 — thermal sensor threshold interrupt", "base", "level"),
    ("SPI-WDT", "SPI", 288, "SPI 288 — watchdog timer bark interrupt", "base", "level"),
    ("SPI-SMMU", "SPI", 320, "SPI 320 — SMMUv3 fault event interrupt", "base", "level"),
    ("LPI-8192", "LPI", 8192, "LPI 8192 — first LPI slot, MSI delivered via ITS", "base", "edge"),
    ("LPI-PCIe-MSI", "LPI", 8193, "LPI 8193 — PCIe MSI interrupt via ITS translation", "base", "edge"),
    ("LPI-PCIe-MSIX-0", "LPI", 8200, "LPI 8200 — PCIe MSI-X vector 0 via ITS", "base", "edge"),
]


def ingest(db_path: str = None) -> int:
    """Ingest GIC-600 knowledge into the Kuzu database."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = os.path.abspath(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    inserted = 0

    for name, ctype, desc, ns, vendor, version in _COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "description": desc,
            "namespace": ns, "vendor": vendor, "version": version,
        }):
            inserted += 1

    for name, irq_type, irq_id, desc, ns, trigger in _INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "description": desc, "namespace": ns, "trigger": trigger,
        }):
            inserted += 1

    # ROUTES_TO relationships
    for src, dst, desc in [
        ("SPI-PMIC", "GIC-600", "PMIC SPI interrupt routed into GIC-600 Distributor"),
        ("SPI-USB3", "GIC-600", "USB3 SPI interrupt routed into GIC-600 Distributor"),
        ("SPI-PCIe", "GIC-600", "PCIe SPI interrupt routed into GIC-600 Distributor"),
        ("SPI-DMA", "GIC-600", "DMA completion SPI routed into GIC-600 Distributor"),
        ("SPI-GPU", "GIC-600", "GPU completion SPI routed into GIC-600 Distributor"),
        ("SPI-ISP", "GIC-600", "ISP frame-done SPI routed into GIC-600 Distributor"),
        ("SPI-Thermal", "GIC-600", "Thermal SPI routed into GIC-600 Distributor"),
        ("SPI-WDT", "GIC-600", "Watchdog SPI routed into GIC-600 Distributor"),
        ("SPI-SMMU", "GIC-600", "SMMUv3 fault SPI routed into GIC-600 Distributor"),
        ("GIC-600", "ARM-Cortex-A55", "GIC-600 delivers interrupts to Cortex-A55 CPU interface"),
        ("GIC-600", "ARM-Cortex-A76", "GIC-600 delivers interrupts to Cortex-A76 CPU interface"),
        ("GIC-600", "ARM-Cortex-A78", "GIC-600 delivers interrupts to Cortex-A78 CPU interface"),
        ("GIC-600-Distributor", "GIC-600-Redistributor", "Distributor forwards SPIs to per-CPU Redistributors"),
        ("GIC-600-Redistributor", "GICv3-CPU-Interface", "Redistributor delivers Group1 NS interrupts to CPU interface"),
        ("GIC-600-ITS", "GIC-600-Redistributor", "ITS translates LPI EventIDs and routes to target Redistributor"),
        ("PCIe-Controller", "GIC-600-ITS", "PCIe MSI/MSI-X writes to ITS GITS_TRANSLATER register"),
    ]:
        create_rel(conn, "ROUTES_TO", "Component", "Component", src, dst, {"description": desc})

    # TRANSLATES: ITS → LPI interrupts
    for irq_name in ("LPI-PCIe-MSI", "LPI-PCIe-MSIX-0", "LPI-8192"):
        try:
            conn.execute(
                "MATCH (a:Component {name: 'GIC-600-ITS'}), (i:Interrupt {name: $irq}) "
                "CREATE (a)-[:TRANSLATES {description: 'ITS translates MSI write to LPI INTID'}]->(i)",
                {"irq": irq_name},
            )
        except Exception as e:
            pass  # may already exist

    # TRIGGERS: interrupts trigger handlers on components
    for irq_name, comp_name in [
        ("SPI-PMIC", "PMIC-Interrupt-Pin"),
        ("SPI-Thermal", "Thermal-Sensor-Controller"),
        ("SPI-WDT", "WDT-Watchdog-Timer"),
        ("SPI-GPU", "GPU-Controller"),
        ("SPI-ISP", "ISP-Controller"),
        ("SPI-SMMU", "SMMU-v3"),
    ]:
        try:
            conn.execute(
                "MATCH (i:Interrupt {name: $irq}), (c:Component {name: $comp}) "
                "CREATE (i)-[:TRIGGERS {description: 'Interrupt triggers handler in component'}]->(c)",
                {"irq": irq_name, "comp": comp_name},
            )
        except Exception as e:
            pass

    print(f"[arm-gic-600] Inserted {inserted} nodes ({len(_COMPONENTS)} components + {len(_INTERRUPTS)} interrupts).")
    return inserted


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Ingest ARM GIC-600 knowledge into BSP graph.")
    p.add_argument("--db-path", default=None)
    args = p.parse_args()
    ingest(args.db_path)
