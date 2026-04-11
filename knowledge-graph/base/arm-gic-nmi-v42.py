"""
ARM GICv3.3 NMI + GICv4.2 Virtual NMI — seed knowledge ingestion.

Sources:
  - ARM GIC Architecture Specification IHI 0069 (versions 3.3 and 4.2)
  - ARM Developer Blog: "A closer look at Arm A-profile support for non-maskable
    interrupts" (developer.arm.com/community)
  - OSDev Wiki: "Generic Interrupt Controller versions 3 and 4"
  - ARM Learn the Architecture: GICv3/v4 Overview (documentation-service.arm.com)
  - QEMU patchset: "[PATCH v12 21/23] hw/intc/arm_gicv3: Report the VINMI interrupt"

Covers:
  - GICv3.3 FEAT_GICv3_NMI: non-maskable interrupt support for physical interrupts
  - GICv4.2 FEAT_GICv4_vNMI: direct injection of non-maskable virtual interrupts
  - NMI priority superpriority mechanism
  - Pseudo-NMI vs architectural NMI distinction in Linux
  - GICD_INMIR / GICR_INMIR register interface for NMI marking
  - Related failure modes for BSP interrupt engineers

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
# Components — GICv3.3 NMI / GICv4.2 vNMI
# ---------------------------------------------------------------------------

_COMPONENTS = [
    ("GICv3.3-NMI", "interrupt-controller", "ARM",
     "GICv3.3 FEAT_GICv3_NMI — architectural non-maskable interrupt support; "
     "interrupts marked non-maskable via GICD_INMIR/GICR_INMIR registers bypass "
     "CPU priority masking (ICC_PMR_EL1); only Secure Group 1 and Non-secure "
     "Group 1 interrupts can be non-maskable; requires PE support for "
     "FEAT_NMI (ALLINT MSR bit); replaces Linux pseudo-NMI workaround",
     "base"),
    ("GICv4.2-vNMI", "interrupt-controller", "ARM",
     "GICv4.2 FEAT_GICv4_vNMI — extends GICv4.1 direct injection to support "
     "virtual non-maskable interrupts (vNMI); enables hypervisor to deliver "
     "non-maskable virtual interrupts to VMs without trap-and-emulate; "
     "VINMI signaling via ITS VMOVP/VMAPP commands; critical for real-time "
     "VM workloads (automotive, industrial control)",
     "base"),
    ("GICD-INMIR", "register", "ARM",
     "GICD_INMIRn — GIC Distributor Non-Maskable Interrupt Register; one bit per "
     "SPI; when set, the corresponding SPI is treated as non-maskable and "
     "bypasses ICC_PMR_EL1 priority masking on the target PE; GICv3.3+",
     "base"),
    ("GICR-INMIR", "register", "ARM",
     "GICR_INMIRn — GIC Redistributor Non-Maskable Interrupt Register; one bit "
     "per PPI/SGI; marks the interrupt as non-maskable at the redistributor "
     "level; PPI NMI is per-PE; SGI NMI is per-PE per-interrupt; GICv3.3+",
     "base"),
    ("linux-pseudo-nmi", "framework", "linux",
     "Linux pseudo-NMI (arm64) — kernel workaround for pre-GICv3.3 systems; "
     "uses ICC_PMR_EL1 priority masking to create a 'superpriority' interrupt "
     "class that is not masked by local_irq_disable(); used for perf PMU "
     "overflow, watchdog; replaced by architectural NMI on GICv3.3+ systems",
     "base"),
    ("GICv3.2-AArch64-R", "interrupt-controller", "ARM",
     "GICv3.2 — adds support for Armv8-R AArch64 real-time profile; "
     "extends GIC to Cortex-R82 and similar real-time processors; "
     "enables deterministic interrupt delivery for safety-critical workloads",
     "base"),
    ("NMI-superpriority", "interrupt-controller", "ARM",
     "NMI Superpriority mechanism — GICv3.3 NMI bypasses the PE ICC_PMR_EL1 "
     "priority mask register; the ALLINT bit in PSTATE controls whether NMIs "
     "are delivered; MSR ALLINT clears the mask; designed for watchdog, "
     "performance monitoring, and crash dump triggers",
     "base"),
]

# ---------------------------------------------------------------------------
# Registers — INMIR interface
# ---------------------------------------------------------------------------

_REGISTERS = [
    ("GICD_INMIR0", "0x0F80", "RW", "0x00000000", "GIC-Distributor",
     "GIC Distributor Non-Maskable Interrupt Register 0 — NMI bits for SPI 32-63; "
     "bit N=1 marks SPI (32+N) as non-maskable; GICv3.3 extension",
     "base"),
    ("GICR_INMIR0", "0x0F80", "RW", "0x00000000", "GIC-Redistributor",
     "GIC Redistributor Non-Maskable Interrupt Register 0 — NMI bits for SGI 0-15 "
     "and PPI 16-31; bit N=1 marks interrupt N as non-maskable; per-PE; GICv3.3",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — NMI / vNMI specific
# ---------------------------------------------------------------------------

_FAILURES = [
    ("GICv3.3-NMI-Masked-Unexpectedly",
     "NMI-marked interrupt not delivered during critical section; watchdog "
     "timeout despite NMI configuration; system hangs without crash dump",
     "PE does not implement FEAT_NMI (ALLINT bit not functional); or PSTATE.ALLINT "
     "set by exception handler masking NMIs; verify PE supports FEAT_NMI via "
     "ID_AA64PFR1_EL1.NMI field; check that kernel NMI handler does not "
     "inadvertently set ALLINT during entry",
     "interrupt",
     "ARM GIC Specification IHI 0069 GICv3.3; ARM Developer Blog: A-profile NMI",
     "base"),
    ("GICv4.2-vNMI-Not-Injected",
     "VM real-time task misses deadline; virtual watchdog timeout inside guest; "
     "guest dmesg shows no NMI received",
     "Hypervisor vGIC emulation does not support GICv4.2 vNMI; or ITS VMAPP "
     "command did not set the vNMI delivery bit for the vPE; verify KVM GICv4.2 "
     "support is enabled (CONFIG_KVM_ARM_VGIC_V4); check ITS command queue for "
     "VMAPP vNMI bit; ensure host GIC hardware implements GICv4.2",
     "interrupt",
     "ARM GIC Specification IHI 0069 GICv4.2; QEMU GICv3 vNMI patchset",
     "base"),
    ("pseudo-NMI-PMR-race",
     "perf record shows missing PMU overflow samples on arm64; NMI handler "
     "invoked with wrong priority; spurious 'unexpected NMI' warnings in dmesg",
     "Race between ICC_PMR_EL1 restore in interrupt exit path and pseudo-NMI "
     "delivery; kernel versions before 6.x had window where PMR restore could "
     "mask a pending pseudo-NMI; upgrade to kernel with architectural NMI support "
     "on GICv3.3+ hardware or apply PMR serialization barrier patch",
     "interrupt",
     "Linux arm64 pseudo-NMI: arch/arm64/kernel/entry-common.c",
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

    for addr_name, address, access_type, reset_value, component, desc, ns in _REGISTERS:
        if upsert_node(conn, "Register", {
            "name": addr_name, "address": address, "access_type": access_type,
            "reset_value": reset_value, "component": component,
            "namespace": ns, "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # -- Relationships --

    # GICv3.3 NMI → GIC-600 / GIC-700 (extends)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv3.3-NMI", dst_name="GIC-600")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv3.3-NMI", dst_name="GIC-700-Distributor")

    # GICv4.2 vNMI → GICv3.3 NMI (extends NMI to virtual domain)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv4.2-vNMI", dst_name="GICv3.3-NMI")

    # GICv4.2 vNMI → ITS (vNMI delivery via ITS commands)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv4.2-vNMI", dst_name="GIC-ITS")

    # NMI superpriority → GICv3.3 NMI
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="NMI-superpriority", dst_name="GICv3.3-NMI")

    # Linux pseudo-NMI → GIC-600 (workaround for pre-3.3)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-pseudo-nmi", dst_name="GIC-600")

    # GICv3.2 → Cortex-R82 (if it exists in graph)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv3.2-AArch64-R", dst_name="GIC-600")

    # GICD_INMIR register components
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICD-INMIR", dst_name="GICv3.3-NMI")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICR-INMIR", dst_name="GICv3.3-NMI")

    # Failure → root component
    _fm_causes = [
        ("GICv3.3-NMI-Masked-Unexpectedly", "GICv3.3-NMI"),
        ("GICv4.2-vNMI-Not-Injected", "GICv4.2-vNMI"),
        ("pseudo-NMI-PMR-race", "linux-pseudo-nmi"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-gic-nmi-v42] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
