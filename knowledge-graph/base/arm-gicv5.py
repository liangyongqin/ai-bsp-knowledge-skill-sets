"""
ARM GICv5 Architecture seed — open-source knowledge ingestion.

Adds the next-generation ARM Generic Interrupt Controller architecture
announced in 2025, with direct injection, IRS, and GIC Stream protocol.

Sources:
  - ARM blog: Introducing GICv5 (developer.arm.com, 2025)
  - ARM A-Profile Architecture Developments 2025
  - LWN.net: Arm GICv5: Host driver implementation (2025-06)
  - ARM GIC Architecture Specification IHI0069 (GICv3/v4 for comparison)

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
# Components — GICv5 core architecture
# ---------------------------------------------------------------------------

_GICV5_CORE = [
    ("GICv5-IRS",              "interrupt-controller", "ARM",
     "GICv5 Interrupt Routing Service (IRS) — replaces Distributor+Redistributor model, "
     "scalable interrupt routing for thousands of interrupt sources; "
     "memory-mapped configuration via tables instead of per-register programming",
     "base"),
    ("GICv5-CPUIF-v5",        "interrupt-controller", "ARM",
     "GICv5 CPU Interface — system register based (ICC_*_ELn), "
     "direct injection of all interrupt types (no hypervisor traps for SPIs, LPIs, SGIs); "
     "compatible with GICv3/v4 CPU interface registers for backward compat",
     "base"),
    ("GICv5-ITS-v5",          "interrupt-controller", "ARM",
     "GICv5 Interrupt Translation Service — translates MSI writes from PCIe/platform devices "
     "to interrupt routing; enhanced scalability over GICv3 ITS; "
     "integrated with GIC Stream protocol for coherent interrupt delivery",
     "base"),
    ("GICv5-Stream-Protocol",  "protocol",   "ARM",
     "GIC Stream Protocol — new wire protocol in GICv5 for interrupt delivery between "
     "IRS and CPU interfaces; replaces legacy SPI/LPI wire routing; "
     "ensures interoperability and scalability across large SoCs",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — GICv5 virtualization
# ---------------------------------------------------------------------------

_GICV5_VIRT = [
    ("GICv5-Direct-Inject",    "interrupt-controller", "ARM",
     "GICv5 Direct Injection — all interrupt types (SPIs, LPIs, SGIs) directly injected to vCPU "
     "without hypervisor trap; eliminates virtualization overhead for interrupts; "
     "no more vGIC emulation needed for common operations",
     "base"),
    ("GICv5-vSGI-Direct",     "interrupt-controller", "ARM",
     "GICv5 virtual SGI direct injection — IPIs between vCPUs delivered directly by hardware; "
     "no EL2 trap for sending or receiving IPIs; critical for VM scheduling performance",
     "base"),
    ("GICv5-Config-NoTrap",   "interrupt-controller", "ARM",
     "GICv5 trap-free configuration — interrupt configuration (enable/disable/priority) "
     "can be read and updated by guest without trapping to EL2; "
     "enables simpler hypervisors with smaller TCB",
     "base"),
    ("GICv5-Realm-Support",   "interrupt-controller", "ARM",
     "GICv5 Realm interrupt delivery — direct interrupt delivery to ARM CCA Realms "
     "without EL2 involvement; GICv5 emulation in RMM with small TCB impact; "
     "enables confidential VM interrupt handling",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — GICv5 power management
# ---------------------------------------------------------------------------

_GICV5_PM = [
    ("GICv5-Power-Mgmt",      "interrupt-controller", "ARM",
     "GICv5 improved power management — fine-grained power domain support, "
     "interrupt wake-up without powering full IRS; "
     "supports per-core and per-cluster power gating with efficient wake-up path",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Linux GICv5 driver
# ---------------------------------------------------------------------------

_GICV5_LINUX = [
    ("linux-irqchip-gicv5",   "driver",     "linux",
     "Linux GICv5 host driver (drivers/irqchip/irq-gic-v5*) — "
     "implements irqchip for GICv5 IRS; supports MSI via GICv5 ITS; "
     "initial patches posted to LKML (v6, June 2025); "
     "31-patch series covering host, MSI, timer interrupt delivery",
     "base"),
    ("linux-kvm-gicv5",       "driver",     "linux",
     "Linux KVM GICv5 support — leverages direct injection for vSGI/vSPI/vLPI; "
     "simplified vGIC emulation; no trap overhead for common interrupt operations; "
     "enables system partitioning with GICv5",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — GICv4.1 enhancements (fill gaps from existing gic-600.py)
# ---------------------------------------------------------------------------

_GICV41_ENHANCEMENTS = [
    ("GICv4.1-vSGI-Inject",   "interrupt-controller", "ARM",
     "GICv4.1 virtual SGI direct injection — extends GICv4 direct LPI injection "
     "to also handle vSGIs; one architectural doorbell per vCPU (vs per-VLPI); "
     "doorbell entirely managed by hardware",
     "base"),
    ("GICv4.1-VPE-Table",     "interrupt-controller", "ARM",
     "GICv4.1 Virtual PE (VPE) table — maps vPEID to physical redistributor; "
     "ITS commands: VMAPP, VMOVI, VMOVP for VPE management; "
     "enables direct vLPI injection to correct physical CPU",
     "base"),
    ("GICv4.1-Doorbell",      "interrupt-controller", "ARM",
     "GICv4.1 per-vCPU doorbell — single doorbell interrupt per VPE; "
     "wakes hypervisor only when vCPU has pending interrupts and is not scheduled; "
     "replaces per-VLPI doorbell from GICv4.0 (less interrupt overhead)",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_GIC_FAILURES = [
    ("FM-GICv5-IRS-Init-Fail",
     "GICv5 IRS initialization fails at boot; no interrupts delivered; system hangs",
     "GICv5 IRS firmware table not configured or IRS power domain not enabled; "
     "check DT gicv5 node and ensure IRS memory region is accessible",
     "interrupt",
     "ARM GICv5 blog / LWN.net GICv5 driver patches",
     "base"),
    ("FM-GICv4-VLPI-Not-Delivered",
     "KVM guest not receiving device interrupts via pass-through; vLPI stuck pending",
     "GICv4.1 VPE not mapped to correct physical redistributor; "
     "VMAPP ITS command failed or VPE table misconfigured; "
     "check /sys/kernel/debug/kvm/ vgic state",
     "interrupt",
     "ARM GIC Architecture Spec / Linux irqchip/gic-v4 code",
     "base"),
    ("FM-GICv4-Doorbell-Storm",
     "Hypervisor CPU at 100% handling doorbell interrupts; VM scheduling overhead high",
     "vCPU descheduled with many pending vLPIs; each pending vLPI triggers doorbell; "
     "GICv4.1 per-vCPU doorbell should coalesce, but if using GICv4.0 doorbell is per-VLPI; "
     "upgrade to GICv4.1 hardware or reduce vLPI count",
     "interrupt",
     "ARM GICv4.1 documentation / LWN.net irqchip/gic-v4",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Additional ARM interrupt architecture
# ---------------------------------------------------------------------------

_ARM_IRQ_EXTRA = [
    ("ARM-FIQ",               "interrupt",   "ARM",
     "ARM Fast Interrupt Request (FIQ) — highest priority interrupt, "
     "used for secure world interrupts (GIC Group 0); "
     "EL3 firmware handles FIQ; Linux sees FIQ as NMI on ARM64",
     "base"),
    ("ARM-NMI",               "interrupt",   "ARM",
     "ARM Non-Maskable Interrupt (NMI) — ARMv8.8 FEAT_NMI; "
     "superpriority interrupts that cannot be masked by PSTATE.I; "
     "used for watchdog, performance monitoring, and debugging; "
     "Linux pseudo-NMI via GIC priority masking",
     "base"),
    ("ARM-PMU-IRQ-Overflow",  "interrupt",   "ARM",
     "ARM PMU overflow interrupt — fires when PMU counter wraps; "
     "perf tool uses this to sample events; "
     "typically PPI 23 (GIC-assigned); must be correctly routed per-CPU",
     "base"),
    ("ARM-SDEI",              "firmware",    "ARM",
     "ARM Software Delegated Exception Interface (SDEI) — "
     "firmware-first error handling; EL3 firmware captures RAS errors, "
     "delegates to OS via SDEI callback; used for memory ECC errors and "
     "platform-specific hardware faults",
     "base"),
    ("ARM-RAS",               "framework",   "ARM",
     "ARM Reliability, Availability, Serviceability (RAS) — "
     "error detection/correction architecture; nodes report errors via "
     "ERR<n>STATUS registers; propagated via SDEI or interrupt; "
     "Linux EDAC and GHES drivers consume RAS events",
     "base"),
    ("linux-edac-arm",        "driver",      "linux",
     "Linux EDAC ARM driver — Error Detection and Correction reporting; "
     "monitors cache/DRAM ECC errors, CPU RAS events; "
     "exposes via /sys/devices/system/edac/; integrates with ARM RAS",
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
        _GICV5_CORE + _GICV5_VIRT + _GICV5_PM + _GICV5_LINUX +
        _GICV41_ENHANCEMENTS + _ARM_IRQ_EXTRA
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _GIC_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # GICv5 architecture: IRS → CPU IF via Stream Protocol
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-IRS", dst_name="GICv5-Stream-Protocol")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-Stream-Protocol", dst_name="GICv5-CPUIF-v5")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-IRS", dst_name="GICv5-ITS-v5")

    # Direct injection features
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-Direct-Inject", dst_name="GICv5-CPUIF-v5")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-vSGI-Direct", dst_name="GICv5-Direct-Inject")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-Config-NoTrap", dst_name="GICv5-CPUIF-v5")

    # Realm support → CCA
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv5-Realm-Support", dst_name="ARM-CCA")

    # Linux drivers
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-irqchip-gicv5", dst_name="GICv5-IRS")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-kvm-gicv5", dst_name="GICv5-Direct-Inject")

    # GICv4.1 enhancements → existing GIC-600-ITS
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv4.1-vSGI-Inject", dst_name="GIC-600-ITS")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv4.1-VPE-Table", dst_name="GIC-600-ITS")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="GICv4.1-Doorbell", dst_name="GIC-600-Redistributor")

    # ARM IRQ extras
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-FIQ", dst_name="GIC-600")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-NMI", dst_name="GIC-600")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-SDEI", dst_name="TFA-BL31")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-RAS", dst_name="ARM-SDEI")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-edac-arm", dst_name="ARM-RAS")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-GICv5-IRS-Init-Fail",       "GICv5-IRS"),
        ("FM-GICv4-VLPI-Not-Delivered",  "GICv4.1-VPE-Table"),
        ("FM-GICv4-Doorbell-Storm",      "GICv4.1-Doorbell"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-gicv5] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
