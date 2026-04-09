"""
Linux virtual cpufreq, Exynos ACPM, and SoC thermal fixes seed.

Adds Linux kernel 6.13–6.15 developments not covered by other seed scripts:
  - Virtual cpufreq driver (6.13): guest VM performance scaling via MMIO
  - Exynos ACPM protocol driver (6.15): Google GS101 Tensor SoC power management
  - Qualcomm dual-lane PHY (6.15): PCIe/USB dual-lane support
  - Snapdragon X1 GPU thermal fix (6.15.1): critical GPU overheating failure mode
  - RME v1.2 updates: Realm Management Extension granule protection improvements

Sources:
  - KernelNewbies: Linux 6.13, 6.15
  - Phoronix: Virtual CPUFreq driver (2024-11), Linux 6.15.1 Snapdragon X1 fix
  - Linux kernel drivers/cpufreq/virtual-cpufreq.c
  - Linux kernel Documentation/devicetree/bindings/cpufreq/virtual,cpufreq.yaml
  - CNX Software: Linux 6.15 ARM64 SoC changes
  - ARM RME v1.2 Guide — documentation-service.arm.com

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
# Components — Virtual cpufreq driver (Linux 6.13)
# ---------------------------------------------------------------------------

_VIRT_CPUFREQ_COMPONENTS = [
    ("linux-virt-cpufreq", "driver", "Linux",
     "Virtual cpufreq driver (Linux 6.13, CONFIG_CPUFREQ_VIRT) — guest VM kernel "
     "reads/writes MMIO region to communicate performance requests to host hypervisor; "
     "host uses requests as hints for vCPU scheduling and CPU frequency selection; "
     "depends on OF (device tree) and PM_OPP framework; "
     "source: drivers/cpufreq/virtual-cpufreq.c",
     "base"),
    ("linux-virt-cpufreq-fie", "framework", "Linux",
     "Virtual FIE (Frequency Invariance Engine) — when guest lacks hardware AMU "
     "counters, virtual cpufreq polls host CPU frequency to update frequency "
     "scaling factor; enables accurate Per-Entity Load Tracking (PELT) in guest; "
     "critical for EAS task placement accuracy inside VMs",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Exynos ACPM protocol (Linux 6.15)
# ---------------------------------------------------------------------------

_EXYNOS_ACPM_COMPONENTS = [
    ("exynos-acpm-protocol", "driver", "Samsung",
     "Exynos Alive Clock and Power Manager (ACPM) protocol driver (Linux 6.15) — "
     "communication interface between AP power management software and ACPM "
     "firmware running on embedded processor; used on Google GS101 (Tensor) SoC; "
     "handles clock rate requests, power domain transitions, thermal notifications",
     "base"),
    ("exynos-acpm-mailbox", "bus", "Samsung",
     "Exynos ACPM Mailbox — shared memory + interrupt mailbox for AP-to-ACPM "
     "communication; messages carry clock/power/thermal commands; "
     "firmware processes asynchronously on dedicated M-series core",
     "base"),
    ("google-gs101-soc", "soc", "Google",
     "Google GS101 (Tensor G1) SoC — first Google-designed mobile SoC; "
     "Samsung Exynos-based with custom CPU cluster (2x X1 + 2x A78 + 4x A55); "
     "ACPM firmware manages power domains; upstream support in Linux 6.15+; "
     "Pixel 6 Pro (Raven) board support added",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Qualcomm platform updates (Linux 6.15)
# ---------------------------------------------------------------------------

_QCOM_COMPONENTS = [
    ("qcom-dual-lane-phy", "driver", "Qualcomm",
     "Qualcomm dual-lane PHY support (Linux 6.15) — enables PCIe and USB "
     "dual-lane configurations on QCS8300 and newer Qualcomm SoCs; "
     "doubles link bandwidth for storage and peripheral connectivity",
     "base"),
    ("qcom-qcs8300-soc", "soc", "Qualcomm",
     "Qualcomm QCS8300 SoC — automotive/IoT platform with dual-lane PHY; "
     "initial upstream support added in Linux 6.15; "
     "power domain and interconnect drivers for multimedia and compute",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — RME v1.2 updates
# ---------------------------------------------------------------------------

_RME_V12_COMPONENTS = [
    ("arm-rme-v1.2", "security", "ARM",
     "ARM Realm Management Extension v1.2 — updated RME specification with "
     "enhanced granule protection check (GPC) for SMMU integration; "
     "SMMU_ROOT_IDR0.ROOT_IMPL and SMMU_ROOT_CR0.GPCEN control realm enforcement; "
     "supports Device Assignment (DA) for direct device access from Realm VMs; "
     "part of ARM CCA (Confidential Compute Architecture)",
     "base"),
    ("arm-rme-granule-protection", "security", "ARM",
     "RME Granule Protection Table (GPT) — per-page physical address space "
     "classification into Normal, Secure, Realm, Root worlds; "
     "checked on every memory access by PE and SMMU; "
     "v1.2 adds finer-grained DA controls for device passthrough to Realms",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_FAILURE_MODES = [
    ("FM-Snapdragon-X1-GPU-Overheat",
     "Snapdragon X1 GPU reaches critical temperature; system thermal shutdown "
     "or severe throttling under moderate GPU load",
     "GPU thermal zone missing consistent critical shutdown temperature and "
     "cooling device binding in DT; fixed in Linux 6.15.1 by applying "
     "consistent critical thermal limit and ensuring GPU cooling registration; "
     "check thermal zone trip points and cooling-device bindings in DT",
     "thermal",
     "Phoronix: Linux 6.15.1 Snapdragon X1 GPU thermal fix",
     "base"),
    ("FM-Virt-Cpufreq-MMIO-Timeout",
     "Guest VM cpufreq driver fails to set frequency; dmesg shows MMIO timeout "
     "or performance requests not acknowledged by host",
     "Host hypervisor does not implement virtual cpufreq MMIO interface; "
     "DT node for virtual-cpufreq present but host handler missing; "
     "verify host KVM virtual cpufreq support and MMIO region mapping",
     "power",
     "Linux kernel drivers/cpufreq/virtual-cpufreq.c",
     "base"),
    ("FM-Virt-Cpufreq-PELT-Inaccuracy",
     "Guest VM tasks scheduled on wrong CPU cluster; poor performance despite "
     "available compute capacity",
     "Virtual FIE polling frequency too low or AMU counter emulation absent; "
     "PELT frequency scaling factor stale in guest; EAS makes suboptimal "
     "placement decisions; increase FIE polling interval or enable AMU trapping",
     "power",
     "Linux Documentation/scheduler/sched-energy.rst",
     "base"),
    ("FM-ACPM-Mailbox-Timeout",
     "Exynos/GS101 power domain transition hangs; dmesg shows ACPM mailbox "
     "timeout or firmware response timeout",
     "ACPM firmware on embedded processor not responding; possible firmware crash, "
     "mailbox IRQ misconfiguration, or shared memory corruption; "
     "check ACPM firmware version and mailbox interrupt binding in DT",
     "power",
     "Linux kernel drivers/firmware/samsung/exynos-acpm.c",
     "base"),
    ("FM-RME-GPC-Violation",
     "Device access from Realm VM fails with GPC fault; dmesg shows SMMUv3 "
     "SMMU_EVENTQ_ABT_GPC_FAULT event",
     "Granule Protection Table (GPT) not updated to mark device MMIO pages as "
     "Realm-accessible; SMMU_ROOT_CR0.GPCEN enabled but GPT entries still "
     "classify device memory as Non-Realm; update GPT via RMM before "
     "assigning device to Realm VM",
     "security",
     "ARM RME System Architecture / ARM CCA spec DEN0096",
     "base"),
    ("FM-Dual-Lane-PHY-Training-Fail",
     "Qualcomm QCS8300 PCIe link trains at single lane instead of dual lane; "
     "reduced bandwidth causes storage or peripheral performance degradation",
     "Dual-lane PHY DT configuration incorrect; lane count or PHY refclk "
     "mismatch between SoC and endpoint; check DT phys property for correct "
     "lane count and phy-names for dual-lane binding",
     "boot",
     "Linux kernel drivers/phy/qualcomm/",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    # Insert components
    all_components = (
        _VIRT_CPUFREQ_COMPONENTS + _EXYNOS_ACPM_COMPONENTS +
        _QCOM_COMPONENTS + _RME_V12_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # Insert failure modes
    for name, symptom, root_cause, affected_domain, source, ns in _FAILURE_MODES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Virtual cpufreq → cpufreq subsystem and EAS
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-virt-cpufreq", dst_name="cpufreq-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-virt-cpufreq-fie", dst_name="linux-virt-cpufreq")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-virt-cpufreq-fie", dst_name="sched-util-arm")

    # Exynos ACPM → power management
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="exynos-acpm-protocol", dst_name="exynos-acpm-mailbox")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="exynos-acpm-protocol", dst_name="genpd-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="google-gs101-soc", dst_name="exynos-acpm-protocol")

    # Qualcomm dual-lane PHY → PCIe
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="qcom-dual-lane-phy", dst_name="qcom-qcs8300-soc")

    # RME v1.2 → TrustZone/CCA chain
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="arm-rme-v1.2", dst_name="arm-rme-granule-protection")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="arm-rme-v1.2", dst_name="SMMUv3-TCU")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="arm-rme-granule-protection", dst_name="TF-A-BL31")

    # Failure mode → root component
    for fm_name, comp_name in [
        ("FM-Snapdragon-X1-GPU-Overheat", "thermal-core"),
        ("FM-Virt-Cpufreq-MMIO-Timeout", "linux-virt-cpufreq"),
        ("FM-Virt-Cpufreq-PELT-Inaccuracy", "linux-virt-cpufreq-fie"),
        ("FM-ACPM-Mailbox-Timeout", "exynos-acpm-protocol"),
        ("FM-RME-GPC-Violation", "arm-rme-granule-protection"),
        ("FM-Dual-Lane-PHY-Training-Fail", "qcom-dual-lane-phy"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-virt-cpufreq-acpm] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
