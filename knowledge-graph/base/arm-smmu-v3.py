"""
ARM SMMUv3 (System Memory Management Unit) seed — open-source knowledge ingestion.

Adds IOMMU/SMMU components critical for DMA protection, device isolation,
and virtualization pass-through on modern ARM SoCs.

Sources:
  - ARM SMMU Architecture Specification IHI0070 (SMMUv3.0–v3.3)
  - Linux kernel Documentation/devicetree/bindings/iommu/arm,smmu-v3.yaml
  - Linux kernel drivers/iommu/arm/arm-smmu-v3/
  - LWN.net: KVM Arm SMMUv3 driver for pKVM
  - Antmicro Renode SMMU blog (2025-11)

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
# Components — SMMUv3 hardware blocks
# ---------------------------------------------------------------------------

_SMMU_HW_COMPONENTS = [
    ("SMMUv3-TBU",          "iommu",       "ARM",
     "SMMUv3 Translation Buffer Unit (TBU) — per-port TLB cache, walks page tables "
     "for DMA masters; multiple TBUs connect to a single TCU",
     "base"),
    ("SMMUv3-TCU",          "iommu",       "ARM",
     "SMMUv3 Translation Control Unit (TCU) — central page table walker, "
     "manages stream table lookups, context descriptor fetches, and PTW for all TBUs",
     "base"),
    ("SMMUv3-Stream-Table", "iommu-config", "ARM",
     "SMMUv3 Stream Table — in-memory structure indexed by StreamID, "
     "maps device transactions to Stage-1/Stage-2 translation contexts; "
     "supports linear (small) and 2-level (large) formats",
     "base"),
    ("SMMUv3-Context-Desc",  "iommu-config", "ARM",
     "SMMUv3 Context Descriptor — per-stream or per-PASID configuration, "
     "points to TTBR (translation table base), configures stage-1 translation",
     "base"),
    ("SMMUv3-Command-Queue", "iommu",      "ARM",
     "SMMUv3 Command Queue (CMDQ) — circular buffer in memory, "
     "software writes TLB invalidation, config sync, and prefetch commands; "
     "hardware consumes asynchronously",
     "base"),
    ("SMMUv3-Event-Queue",   "iommu",      "ARM",
     "SMMUv3 Event Queue (EVTQ) — circular buffer in memory, "
     "hardware writes translation fault events, permission faults, "
     "config errors; software consumes for fault handling",
     "base"),
    ("SMMUv3-PRI-Queue",     "iommu",      "ARM",
     "SMMUv3 PRI Queue (PRIQ) — Page Request Interface queue, "
     "handles PCIe ATS/PRI page requests for on-demand IOMMU mapping; "
     "enables device-initiated page faults (SVA/SVM)",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — SMMUv3 Linux driver stack
# ---------------------------------------------------------------------------

_SMMU_LINUX_COMPONENTS = [
    ("linux-arm-smmu-v3",    "driver",      "linux",
     "Linux arm-smmu-v3 driver (drivers/iommu/arm/arm-smmu-v3/) — "
     "manages SMMUv3 hardware: stream table setup, TLB invalidation, "
     "fault handling via EVTQ, PCIe ATS/PRI support",
     "base"),
    ("linux-iommu-core",     "framework",   "linux",
     "Linux IOMMU core framework (drivers/iommu/iommu.c) — "
     "DMA domain management, IOMMU group/device binding, "
     "iommu_ops abstraction for arm-smmu-v3 and other backends",
     "base"),
    ("linux-iommu-dma",      "framework",   "linux",
     "Linux IOMMU DMA mapping layer (drivers/iommu/dma-iommu.c) — "
     "translates DMA API calls (dma_map_*, dma_alloc_*) into IOMMU page table operations; "
     "handles scatter-gather, CMA fallback, and SWIOTLB bounce buffers",
     "base"),
    ("linux-iommu-sva",      "framework",   "linux",
     "Linux Shared Virtual Addressing (SVA) — binds process page tables to device PASID, "
     "enables GPU/accelerator to share CPU virtual address space; "
     "requires SMMUv3 with PASID and PRI support",
     "base"),
    ("linux-vfio-iommu",     "framework",   "linux",
     "Linux VFIO IOMMU backend — provides userspace device access with IOMMU isolation, "
     "used for KVM device pass-through; integrates with SMMUv3 stage-2 translation",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — SMMUv3 virtualization
# ---------------------------------------------------------------------------

_SMMU_VIRT_COMPONENTS = [
    ("SMMUv3-Stage1",       "iommu-stage", "ARM",
     "SMMUv3 Stage-1 translation — guest OS managed, VA→IPA translation, "
     "configured via context descriptors; used for guest DMA isolation",
     "base"),
    ("SMMUv3-Stage2",       "iommu-stage", "ARM",
     "SMMUv3 Stage-2 translation — hypervisor managed, IPA→PA translation, "
     "configured via stream table S2 pointers; enforces inter-VM isolation",
     "base"),
    ("SMMUv3-VMID",         "iommu-config", "ARM",
     "SMMUv3 VMID (Virtual Machine ID) — tags TLB entries per-VM, "
     "enables efficient TLB invalidation per-VM without flushing other VMs",
     "base"),
    ("pkvm-smmu-driver",    "driver",      "linux",
     "pKVM SMMUv3 driver — protected KVM hypervisor manages SMMUv3 stage-2 "
     "to prevent host kernel from bypassing IOMMU protection; "
     "isolates device DMA from host and other VMs even if host is compromised",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_SMMU_INTERRUPTS = [
    ("IRQ-SMMU-Global-Fault", "SPI", 200, "level-high", "base"),
    ("IRQ-SMMU-EVTQ",        "SPI", 201, "level-high", "base"),
    ("IRQ-SMMU-PRIQ",        "SPI", 202, "level-high", "base"),
    ("IRQ-SMMU-CMD-Sync",    "SPI", 203, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_SMMU_FAILURES = [
    ("FM-SMMU-Translation-Fault",
     "SMMU event: translation fault for StreamID X; DMA transfer blocked; peripheral stalls",
     "Device DMA address not mapped in IOMMU page table; driver did not call dma_map_* "
     "or IOMMU domain not attached to device; check iommu_group and domain binding",
     "iommu",
     "ARM SMMU Architecture Spec IHI0070 §6 (Fault Handling)",
     "base"),
    ("FM-SMMU-Permission-Fault",
     "SMMU event: permission fault; device tried write to read-only mapped region",
     "IOMMU page table entry has wrong access flags; verify dma_map direction "
     "(DMA_TO_DEVICE vs DMA_FROM_DEVICE vs DMA_BIDIRECTIONAL)",
     "iommu",
     "Linux Documentation/core-api/dma-api.rst",
     "base"),
    ("FM-SMMU-StreamID-Mismatch",
     "SMMU: unknown StreamID; global fault; device cannot perform DMA",
     "Device StreamID not configured in SMMUv3 stream table; check DT iommu-map "
     "property or ACPI IORT table for correct StreamID→SMMU mapping",
     "iommu",
     "Linux Documentation/devicetree/bindings/iommu/arm,smmu-v3.yaml",
     "base"),
    ("FM-SMMU-Nested-Fault-VM",
     "Guest VM device pass-through fails; VFIO reports IOMMU fault; guest DMA broken",
     "Stage-2 translation not configured for device StreamID in hypervisor; "
     "or guest stage-1 maps PA that host stage-2 does not allow",
     "virtualization",
     "LWN.net: KVM Arm SMMUv3 for pKVM",
     "base"),
    ("FM-SMMU-CMDQ-Full",
     "SMMU command queue full; TLB invalidation stalled; DMA latency spikes",
     "Too many concurrent IOMMU operations overflowing command queue; "
     "increase CMDQ size in DT or reduce invalidation frequency (batch invalidations)",
     "iommu",
     "ARM SMMU Architecture Spec IHI0070 §4.5 (Command Queue)",
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
        _SMMU_HW_COMPONENTS + _SMMU_LINUX_COMPONENTS +
        _SMMU_VIRT_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _SMMU_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _SMMU_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # TBU → TCU (translation path)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMUv3-TBU", dst_name="SMMUv3-TCU")

    # TCU → Stream Table → Context Descriptor
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMUv3-TCU", dst_name="SMMUv3-Stream-Table")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMUv3-Stream-Table", dst_name="SMMUv3-Context-Desc")

    # Stage 1/2 from stream table
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMUv3-Context-Desc", dst_name="SMMUv3-Stage1")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMUv3-Stream-Table", dst_name="SMMUv3-Stage2")

    # Command/Event/PRI queues
    for q in ("SMMUv3-Command-Queue", "SMMUv3-Event-Queue", "SMMUv3-PRI-Queue"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="SMMUv3-TCU", dst_name=q)

    # Linux driver stack
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-arm-smmu-v3", dst_name="SMMUv3-TCU")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-iommu-core", dst_name="linux-arm-smmu-v3")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-iommu-dma", dst_name="linux-iommu-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-iommu-sva", dst_name="linux-arm-smmu-v3")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-vfio-iommu", dst_name="linux-iommu-core")

    # pKVM driver → stage-2
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pkvm-smmu-driver", dst_name="SMMUv3-Stage2")

    # Existing SMMU-v3 node (from arm-amba-axi) → new detailed nodes
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMU-v3", dst_name="SMMUv3-TCU")

    # GPU AXI master → TBU (DMA path through SMMU)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GPU-AXI-Master", dst_name="SMMUv3-TBU")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-SMMU-Translation-Fault", "SMMUv3-TCU"),
        ("FM-SMMU-Permission-Fault",  "SMMUv3-Stage1"),
        ("FM-SMMU-StreamID-Mismatch", "SMMUv3-Stream-Table"),
        ("FM-SMMU-Nested-Fault-VM",   "SMMUv3-Stage2"),
        ("FM-SMMU-CMDQ-Full",         "SMMUv3-Command-Queue"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-smmu-v3] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
