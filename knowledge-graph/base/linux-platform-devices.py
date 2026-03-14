"""
Linux Platform Devices seed — open-source knowledge ingestion.

Sources:
  - Linux Documentation/driver-api/ufs.rst
  - Linux Documentation/block/
  - Linux Documentation/driver-api/dmaengine/
  - Linux Documentation/driver-api/pci/
  - Linux Documentation/networking/phy.rst
  - JEDEC JESD209-5 LPDDR5 standard (public spec summary)
  - JEDEC JESD223 UFS 3.1 standard (public spec summary)
  - PCIe 4.0 Base Specification (public summary)
  - Linux Documentation/driver-api/devfreq.rst
  - Linux Documentation/driver-api/pm/

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
# Components — LPDDR5 Memory Subsystem
# ---------------------------------------------------------------------------

_LPDDR5_COMPONENTS = [
    ("LPDDR5-DRAM",          "dram",           "JEDEC", "LPDDR5 SDRAM — JESD209-5; 8500 Mbps/pin, 16-bank, WCK:CK 4:1 ratio, 32/64-bit bus; supports Bank-Group mode", "base"),
    ("LPDDR5-PHY",           "phy",            "open",  "LPDDR5 PHY — DFI 4.0 interface; ZQ calibration, read/write leveling, duty cycle correction, eye margin",       "base"),
    ("DRAM-controller",      "controller",     "open",  "DRAM memory controller — LPDDR5 scheduler, page policy (open/close), QoS bandwidth arbitration",               "base"),
    ("DRAM-inline-ECC",      "ecc",            "open",  "Inline ECC engine — SEC-DED per 64-byte cacheline; error log via sysfs /sys/devices/system/edac/mc",            "base"),
    ("DRAM-BW-monitor",      "monitor",        "open",  "DRAM bandwidth monitor — per-master throughput counters; feeds devfreq governor for DRAM frequency scaling",     "base"),
    ("devfreq-dram",         "driver",         "linux", "Linux devfreq DRAM frequency scaling — Governor: passive/simple-ondemand; drives DRAM controller OPP",         "base"),
]

# ---------------------------------------------------------------------------
# Components — UFS (Universal Flash Storage)
# ---------------------------------------------------------------------------

_UFS_COMPONENTS = [
    ("UFS-device",           "storage",        "JEDEC", "UFS 3.1 NAND device — JESD223D; HS-G4 (2×5.8 Gbps lanes), 4KB page, 1/4/8MB erase block, multi-LU",          "base"),
    ("UFS-host-controller",  "controller",     "open",  "UFS host controller (UFSHC) — implements MIPI UniPro + UFS Transport Layer; DMA scatter-gather I/O",           "base"),
    ("UFS-M-PHY",            "phy",            "MIPI",  "MIPI M-PHY v4.0 — UFS lane PHY; HS-G4 line rate 5.8 Gbps; Gear4 BURST mode; PWM-G1 for low-power",           "base"),
    ("UFS-HPB",              "feature",        "JEDEC", "UFS HPB (Host Performance Booster) — caches L2P (LBA-to-PBA) map in host DRAM; reduces random read latency",   "base"),
    ("UFS-inline-crypto",    "crypto",         "open",  "UFS inline encryption engine — AES-256-XTS per LBA range; kernel keyslot manager; fscrypt integration",        "base"),
    ("scsi-ufs-driver",      "driver",         "linux", "Linux ufshcd SCSI driver — SCSI command queue, power management (UFS link hibernate), runtime PM",             "base"),
    ("f2fs-on-ufs",          "filesystem",     "linux", "F2FS on UFS — log-structured FS with GC, checkpoint; optimal for sequential write patterns of UFS NAND",       "base"),
]

# ---------------------------------------------------------------------------
# Components — eMMC
# ---------------------------------------------------------------------------

_EMMC_COMPONENTS = [
    ("eMMC-device",          "storage",        "JEDEC", "eMMC 5.1 NAND device — JESD84-B51; HS400 mode 400 MB/s, 8-bit DDR; Enhanced Strobe; 512B sector",             "base"),
    ("eMMC-host-controller", "controller",     "open",  "SDHCI eMMC host controller — HS400 tuning, CMD Queue (CMDQ) for parallel request processing",                  "base"),
    ("mmc-block-driver",     "driver",         "linux", "Linux mmc_block driver — partition management (boot/RPMB/user), runtime PM, blk-mq queue depth",               "base"),
    ("mmc-cmdq",             "feature",        "linux", "eMMC Command Queue — CMDQ engine, up to 32 queued commands, reduces latency for mixed R/W",                    "base"),
]

# ---------------------------------------------------------------------------
# Components — PCIe
# ---------------------------------------------------------------------------

_PCIE_COMPONENTS = [
    ("PCIe-RC",              "pcie",           "open",  "PCIe 4.0 Root Complex — Gen4 16 GT/s, x1/x2/x4 lanes; LTSSM state machine, ASPM L0s/L1/L1.1/L1.2",           "base"),
    ("PCIe-PHY",             "phy",            "open",  "PCIe Gen4 PHY — SerDes, CDR, equalization; Rx/Tx adaptive EQ for board-level channel loss compensation",        "base"),
    ("PCIe-EP",              "pcie",           "open",  "PCIe Endpoint function — BAR mapping, MSI/MSI-X, DMA engine (EDMA), power state L0/L1/D3hot/D3cold",          "base"),
    ("pcie-linux-driver",    "driver",         "linux", "Linux PCIe host driver — DW DesignWare or ARM Neoverse based; PCI bus scan, MSI domain, ASPM policy",          "base"),
    ("pcie-iommu-arm",       "iommu",          "ARM",   "ARM SMMUv3 IOMMU for PCIe — stream-id based translation, CD (Context Descriptor), ARM SMMU-600",               "base"),
]

# ---------------------------------------------------------------------------
# Components — USB
# ---------------------------------------------------------------------------

_USB_COMPONENTS = [
    ("USB3-controller",      "usb",            "open",  "USB 3.2 Gen2 host controller (xHCI) — 10 Gbps; up to 64 slots, 255 ports; stream protocol for BOT/UAS",       "base"),
    ("USB3-PHY",             "phy",            "open",  "USB3 SuperSpeed PHY — 8b/10b coding (USB 3.1), 128b/132b (USB 3.2 Gen2); LTSSM, LFPS for link training",      "base"),
    ("USB-typec-controller", "usb",            "open",  "USB Type-C port controller — CC1/CC2 role detection, PD 3.0 negotiation, DisplayPort alt-mode, DP tunnel",     "base"),
    ("xhci-driver",          "driver",         "linux", "Linux xHCI host driver — ring buffer management, TRB scheduling, USB power management (U1/U2/U3 LPM)",        "base"),
    ("usb-typec-driver",     "driver",         "linux", "Linux USB Type-C subsystem — TCPM (Type-C Port Manager), PD policy, alt-mode discovery and config",            "base"),
]

# ---------------------------------------------------------------------------
# Components — DMA Engine
# ---------------------------------------------------------------------------

_DMA_COMPONENTS = [
    ("dmaengine-core",       "framework",      "linux", "Linux DMAengine framework — dma_async_tx_descriptor, completion callback, scatter-gather list API",             "base"),
    ("DMA-controller-hw",    "dma",            "open",  "Hardware DMA controller — multi-channel, AXI master, scatter-gather, flow control (mem-to-dev, dev-to-mem)",   "base"),
    ("DMA-PL330",            "dma",            "ARM",   "ARM PL330 DMA controller — uCode-based channel sequencer; used in many ARM SoCs for UART/SPI/I2S DMA",        "base"),
    ("iommu-dma",            "iommu",          "linux", "Linux IOMMU DMA ops — iommu_map_sg(), IOVA allocation, swiotlb fallback for non-IOMMU-capable buffers",        "base"),
]

# ---------------------------------------------------------------------------
# Components — PM QoS / Devfreq
# ---------------------------------------------------------------------------

_PMQOS_COMPONENTS = [
    ("pm-qos-core",          "framework",      "linux", "Linux PM QoS framework — per-CPU/global latency+bandwidth constraints; pm_qos_request aggregation",            "base"),
    ("devfreq-core",         "framework",      "linux", "Linux devfreq — device-level frequency/voltage scaling; governors: simple_ondemand, passive, performance",     "base"),
    ("devfreq-passive",      "driver",         "linux", "devfreq passive governor — follows parent devfreq (e.g. DRAM tracks CPU load via passive notifier chain)",     "base"),
    ("interconnect-api",     "framework",      "linux", "Linux interconnect API — icc_path bandwidth requests; maps to NOC QoS registers (per-master bandwidth grant)", "base"),
    ("thermal-cpufreq-cool", "driver",         "linux", "cpufreq cooling device — thermal subsystem → CPUFreq OPP cap; implements struct thermal_cooling_device",       "base"),
]

# ---------------------------------------------------------------------------
# Components — System Bus / Interconnect
# ---------------------------------------------------------------------------

_INTERCONNECT_COMPONENTS = [
    ("NOC-main",             "interconnect",   "open",  "Network on Chip (NoC) — AXI crossbar interconnect; QoS: priority, bandwidth, urgency; urgency escalation",     "base"),
    ("SMMU-600",             "iommu",          "ARM",   "ARM SMMUv3 (SMMU-600) — stage-1/2 page table walk, CD table, IOVA isolation, SID/SUBSTREAMID tagging",        "base"),
    ("CCI-550",              "coherent-int",   "ARM",   "ARM CCI-550 Cache Coherent Interconnect — ACE-Lite/ACE ports, DVM messages, SnoopFilter (optional)",           "base"),
    ("CMN-650",              "mesh-noc",       "ARM",   "ARM CMN-650 Coherent Mesh Network — ring/mesh topology, CHI protocol, SNF, RNF, HNF nodes",                    "base"),
    ("linux-noc-driver",     "driver",         "linux", "Linux NoC QoS driver — icc_provider, per-master BW/latency programming via interconnect API",                  "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_PLATFORM_INTERRUPTS = [
    ("IRQ-UFS-HW",      "SPI", 210, "level-high", "base"),
    ("IRQ-eMMC-HW",     "SPI", 211, "level-high", "base"),
    ("IRQ-PCIe-MSI",    "LPI", 8300, "edge-rising", "base"),
    ("IRQ-USB3-HW",     "SPI", 215, "level-high", "base"),
    ("IRQ-DMA-PL330",   "SPI", 216, "level-high", "base"),
    ("IRQ-DRAM-ECC",    "SPI", 217, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_PLATFORM_FAILURES = [
    ("UFS-hs-gear-fail",
     "UFS init fails at HS-G4; falls back to HS-G1 or PWM; storage performance drops 10x",
     "M-PHY eye degraded due to board trace impedance mismatch or termination voltage OOT",
     "storage",
     "JEDEC JESD223D §6.3 (MIPI M-PHY Gear4 requirements)",
     "base"),
    ("pcie-link-down",
     "PCIe endpoint not detected; lspci shows empty bus; link stays at Detect.Quiet",
     "PERST# de-asserted before REFCLK stable; or endpoint VCCIO out of tolerance during link train",
     "pcie",
     "PCIe 4.0 Base Specification §4.2.6.3 (Fundamental Reset timing)",
     "base"),
    ("dma-iommu-fault",
     "DMA transaction fails with IOMMU fault; kernel: 'Unhandled context fault ... translation fault'",
     "DMA master uses physical address outside IOMMU mapping; missing iommu_map() for scatter-gather element",
     "dma",
     "Linux Documentation/driver-api/dma-buf.rst; ARM SMMUv3 spec §6.3.1",
     "base"),
    ("lpddr5-eye-closure",
     "DRAM training fails at boot; SoC hangs in BL1/BL2; ECC errors at high temperature",
     "LPDDR5 ZQ calibration interval too long; Vref (DQVREF) drift at high temp causes read margin collapse",
     "memory",
     "JEDEC JESD209-5 §4.14 (ZQ calibration timing)",
     "base"),
    ("emmc-hs400-tuning-fail",
     "eMMC HS400 mode fails; falls back to HS200; throughput halved",
     "Host controller CMD21 tuning loop not converging; check CLK duty cycle and board strobe routing",
     "storage",
     "JEDEC JESD84-B51 §7.4 (HS400 tuning procedure)",
     "base"),
    ("noc-latency-spike",
     "Periodic latency spikes on display/ISP DMA; visible frame tears or ISP overflow",
     "NoC QoS priority not configured for latency-sensitive masters; DRAM refresh collision with non-urgent traffic",
     "interconnect",
     "ARM CMN-650 TRM §3.2 (QoS configuration) / ARM NIC-450 TRM",
     "base"),
    ("usb-u3-resume-fail",
     "USB device not recovered after USB3 U3 suspend; device enumeration fails on resume",
     "USB link partner exits U3 before host issues LFPS; xHCI BESL value mismatch between host and device",
     "usb",
     "USB 3.2 spec §7.5.11 (U3 exit timing)",
     "base"),
]


# ---------------------------------------------------------------------------
# PowerDomain nodes — platform-level power islands
# ---------------------------------------------------------------------------

_PLATFORM_POWER_DOMAINS = [
    # name, voltage_mv, current_ma, namespace
    ("PD-UFS",        1800, 200,  "base"),   # UFS host controller + M-PHY island
    ("PD-PCIe",       1800, 300,  "base"),   # PCIe RC + PHY island
    ("PD-USB3",       3300, 250,  "base"),   # USB3 VBUS/VDDIO island
    ("PD-DRAM-IO",    1100, 5000, "base"),   # LPDDR5 IO power domain (VDDQ)
    ("PD-DRAM-CORE",  500,  8000, "base"),   # LPDDR5 core (VDD2H)
    ("PD-GPU",        800,  4000, "base"),   # GPU power island (DVFS domain)
    ("PD-ISP",        900,  1500, "base"),   # ISP + camera pipeline island
    ("PD-DISP",       1800, 800,  "base"),   # Display controller island
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _LPDDR5_COMPONENTS + _UFS_COMPONENTS + _EMMC_COMPONENTS +
        _PCIE_COMPONENTS + _USB_COMPONENTS + _DMA_COMPONENTS +
        _PMQOS_COMPONENTS + _INTERCONNECT_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # PowerDomain nodes
    for name, voltage_mv, current_ma, ns in _PLATFORM_POWER_DOMAINS:
        if upsert_node(conn, "PowerDomain", {
            "name": name, "voltage_mv": voltage_mv,
            "current_ma": current_ma, "namespace": ns,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _PLATFORM_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _PLATFORM_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # DRAM subsystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DRAM-controller", dst_name="LPDDR5-PHY")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="LPDDR5-PHY", dst_name="LPDDR5-DRAM")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DRAM-inline-ECC", dst_name="DRAM-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-dram", dst_name="DRAM-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="DRAM-BW-monitor", dst_name="devfreq-dram")

    # UFS subsystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-host-controller", dst_name="UFS-M-PHY")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="UFS-M-PHY", dst_name="UFS-device")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="scsi-ufs-driver", dst_name="UFS-host-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="f2fs-on-ufs", dst_name="scsi-ufs-driver")
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="UFS-inline-crypto", dst_name="UFS-host-controller")

    # eMMC subsystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="eMMC-host-controller", dst_name="eMMC-device")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mmc-block-driver", dst_name="eMMC-host-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="mmc-cmdq", dst_name="eMMC-host-controller")

    # PCIe subsystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="PCIe-RC", dst_name="PCIe-PHY")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="PCIe-RC", dst_name="PCIe-EP")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pcie-linux-driver", dst_name="PCIe-RC")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pcie-iommu-arm", dst_name="SMMU-600")

    # USB subsystem
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="USB3-controller", dst_name="USB3-PHY")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="xhci-driver", dst_name="USB3-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="usb-typec-driver", dst_name="USB-typec-controller")

    # DMA
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="dmaengine-core", dst_name="DMA-controller-hw")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="dmaengine-core", dst_name="DMA-PL330")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="iommu-dma", dst_name="SMMU-600")

    # Interconnect / NoC
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="NOC-main", dst_name="DRAM-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CCI-550", dst_name="NOC-main")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CMN-650", dst_name="DRAM-controller")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-noc-driver", dst_name="NOC-main")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="interconnect-api", dst_name="linux-noc-driver")

    # PM QoS
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-core", dst_name="devfreq-dram")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-passive", dst_name="devfreq-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="thermal-cpufreq-cool", dst_name="devfreq-core")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pm-qos-core", dst_name="interconnect-api")

    # Power domain → component (POWERS)
    _pd_powers = [
        ("PD-UFS",      "UFS-host-controller"),
        ("PD-PCIe",     "PCIe-RC"),
        ("PD-USB3",     "USB3-controller"),
        ("PD-DRAM-CORE","DRAM-controller"),
        ("PD-GPU",      "GPU-memory-interface"),
        ("PD-ISP",      "ISP-pipeline"),
    ]
    for pd_name, comp_name in _pd_powers:
        create_rel(conn, "POWERS", "PowerDomain", "Component",
                   src_name=pd_name, dst_name=comp_name)

    # Failure modes
    _fm_causes = [
        ("UFS-hs-gear-fail",      "UFS-M-PHY"),
        ("pcie-link-down",        "PCIe-RC"),
        ("dma-iommu-fault",       "SMMU-600"),
        ("lpddr5-eye-closure",    "LPDDR5-PHY"),
        ("emmc-hs400-tuning-fail","eMMC-host-controller"),
        ("noc-latency-spike",     "NOC-main"),
        ("usb-u3-resume-fail",    "USB3-controller"),
    ]
    for fm_name, comp_name in _fm_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-platform-devices] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
