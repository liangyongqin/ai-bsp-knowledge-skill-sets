#!/usr/bin/env python3
"""
fix-orphan-connectivity.py — Remediate orphan nodes by adding missing relationships.

Addresses 209+ orphan Component nodes, 49 disconnected FailureModes, 8 unlinked
PowerDomains, and 35 unlinked ClockSources that were created by prior seed scripts
without corresponding relationship edges.

This script is idempotent — safe to re-run.

Sources:
  - ARM GIC-600 TRM (ITS data structures, §5.4–5.6)
  - Linux kernel Documentation/scheduler/sched-energy.rst (EAS)
  - Linux kernel Documentation/cpu-freq/governors.rst
  - Linux kernel Documentation/power/states.rst (C-states, PSCI)
  - Linux kernel Documentation/driver-api/clk.rst (clock framework)
  - Linux kernel Documentation/userspace-api/media/ (V4L2 subsystem)
  - ARM DynamIQ Shared Unit TRM (DSU, OPP tables)
  - AMBA AXI4 Protocol Specification (channels, bridges, QoS)
  - ARM GICv3/v4 Architecture Specification
  - ARM Cortex-A55/A76/A78 TRMs (OPP, power domain mapping)
  - GPU rendering pipeline: Vulkan spec §8 (render pass), OpenGL ES 3.x spec
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _ingest_helpers import create_rel  # noqa: E402


def run(db_path: str | None = None) -> dict:
    """Add missing relationships to orphan nodes. Returns stats dict."""
    import kuzu

    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    if not os.path.exists(db_path):
        logger.error("Database not found at %s", db_path)
        sys.exit(1)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    created = 0
    failed = 0

    def link(rel_type, src_label, dst_label, src_name, dst_name, props=None):
        nonlocal created, failed
        if create_rel(conn, rel_type, src_label, dst_label, src_name, dst_name, props):
            created += 1
        else:
            failed += 1

    # =========================================================================
    # 1. OPP nodes → ROUTES_TO → parent CPU cluster / GPU
    #    Source: ARM Cortex-A55/A76/A78 TRMs, Linux OPP framework
    #    Note: DEPENDS_ON_CLOCK is Component→ClockSource per schema;
    #    OPPs are Components, so use ROUTES_TO (Component→Component)
    # =========================================================================
    logger.info("Linking OPP nodes to parent clusters...")

    a55_opps = [f"OPP-A55-{f}MHz" for f in [400, 600, 800, 1000, 1200, 1400, 1600, 1800]]
    for opp in a55_opps:
        link("ROUTES_TO", "Component", "Component", opp, "Cortex-A55-Cluster")

    a76_opps = [f"OPP-A76-{f}MHz" for f in [800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600]]
    for opp in a76_opps:
        link("ROUTES_TO", "Component", "Component", opp, "Cortex-A76-Cluster")

    a78_opps = [f"OPP-A78-{f}MHz" for f in [1000, 1400, 1800, 2200, 2600, 3000, 3200]]
    for opp in a78_opps:
        link("ROUTES_TO", "Component", "Component", opp, "Cortex-A78-Cluster")

    gpu_opps = [f"OPP-GPU-{f}MHz" for f in [200, 400, 600, 750, 900]]
    for opp in gpu_opps:
        link("ROUTES_TO", "Component", "Component", opp, "GPU-Controller")

    # =========================================================================
    # 2. CPU C-state nodes → ROUTES_TO → CPU cores/clusters
    #    Source: Linux Documentation/power/states.rst, ACPI spec §8
    # =========================================================================
    logger.info("Linking C-state nodes...")

    cstates = ["ACPI-C0", "ACPI-C1", "ACPI-C1E", "ACPI-C2", "ACPI-C3", "ACPI-C6"]
    for cs in cstates:
        link("ROUTES_TO", "Component", "Component", cs, "Cortex-A55-Cluster")
        link("ROUTES_TO", "Component", "Component", cs, "Cortex-A76-Cluster")

    # C-state → idle state mapping
    link("ROUTES_TO", "Component", "Component", "ACPI-C1", "ARM-WFI")
    link("ROUTES_TO", "Component", "Component", "ACPI-C1E", "ARM-WFE")
    link("ROUTES_TO", "Component", "Component", "ACPI-C6", "ARM-PSCI-CPU_SUSPEND")

    # =========================================================================
    # 3. cpufreq governors → ROUTES_TO → cpufreq-core subsystem
    #    Source: Linux Documentation/cpu-freq/governors.rst
    # =========================================================================
    logger.info("Linking cpufreq governors...")

    governors = ["cpufreq-conservative", "cpufreq-ondemand", "cpufreq-performance",
                 "cpufreq-powersave", "cpufreq-userspace"]
    for gov in governors:
        link("ROUTES_TO", "Component", "Component", gov, "cpufreq-core")

    # =========================================================================
    # 4. EAS components → inter-component relationships
    #    Source: Linux Documentation/scheduler/sched-energy.rst
    # =========================================================================
    logger.info("Linking EAS components...")

    link("ROUTES_TO", "Component", "Component", "EAS-Task-Placement", "EAS-PELT")
    link("ROUTES_TO", "Component", "Component", "EAS-Task-Placement", "EAS-Energy-Model")
    link("ROUTES_TO", "Component", "Component", "EAS-Util-Est", "EAS-PELT")
    link("ROUTES_TO", "Component", "Component", "EAS-Capacity-Aware-Wakeup", "EAS-Energy-Model")
    # EAS → schedutil governor
    link("ROUTES_TO", "Component", "Component", "EAS-Energy-Model", "cpufreq-schedutil")
    # EAS components → CPU clusters
    for eas in ["EAS-Energy-Model", "EAS-Task-Placement", "EAS-PELT",
                "EAS-Capacity-Aware-Wakeup", "EAS-Util-Est"]:
        link("ROUTES_TO", "Component", "Component", eas, "Cortex-A55-Cluster")
        link("ROUTES_TO", "Component", "Component", eas, "Cortex-A76-Cluster")

    # =========================================================================
    # 5. GIC data structures → parent GIC-600/ITS
    #    Source: ARM GIC-600 TRM §5.4–5.6, GICv3/v4 Architecture Spec
    # =========================================================================
    logger.info("Linking GIC data structures...")

    # ITS tables belong to GIC-600-ITS
    its_tables = ["ITS-Device-Table", "ITS-Interrupt-Translation-Table",
                  "ITS-Collection-Table", "ITS-Command-Queue"]
    for table in its_tables:
        link("ROUTES_TO", "Component", "Component", table, "GIC-600-ITS")

    # GIC-600 vPE/LPI tables belong to GIC-600-Redistributor
    gic_tables = ["GIC-600-vPE-Table", "GIC-600-LPI-Config-Table", "GIC-600-LPI-Pending-Table"]
    for table in gic_tables:
        link("ROUTES_TO", "Component", "Component", table, "GIC-600-Redistributor")

    # Architecture specs → GIC-600
    link("ROUTES_TO", "Component", "Component", "GICv3-Architecture", "GIC-600")
    link("ROUTES_TO", "Component", "Component", "GICv4-Architecture", "GIC-600")
    link("ROUTES_TO", "Component", "Component", "GIC-600-Hypervisor-IF", "GIC-600")
    link("ROUTES_TO", "Component", "Component", "GIC-600-Power-Controller", "GIC-600")

    # =========================================================================
    # 6. ISA extensions → parent CPU architectures
    #    Source: ARM Architecture Reference Manual for A-profile, ARMv9.5–9.7
    # =========================================================================
    logger.info("Linking ISA extensions...")

    # ARMv9.5 extensions → Cortex-X4 and newer
    v95_exts = ["ARMv9.5-CPA", "ARMv9.5-FAMINMAX", "ARMv9.5-LUT"]
    for ext in v95_exts:
        link("ROUTES_TO", "Component", "Component", ext, "Cortex-X4-Cluster")
        link("ROUTES_TO", "Component", "Component", ext, "Cortex-A725-Cluster")

    # ARMv9.6 extensions → Cortex-X925 and newer
    v96_exts = ["ARMv9.6-CMPBR", "ARMv9.6-LSUI", "ARMv9.6-PoPS"]
    for ext in v96_exts:
        link("ROUTES_TO", "Component", "Component", ext, "Cortex-X925-Cluster")

    # ARMv9.7 extensions → future cores (link to X925 as latest available)
    v97_exts = ["ARMv9.7-Domain-TLB-Inv", "ARMv9.7-LOR-Realms", "ARMv9.7-Split-PAC",
                "ARMv9.7-Video-Codec"]
    for ext in v97_exts:
        link("ROUTES_TO", "Component", "Component", ext, "Cortex-X925-Cluster")

    # ARMv9-BRBE → performance monitoring
    link("ROUTES_TO", "Component", "Component", "ARMv9-BRBE", "Cortex-X4-Cluster")

    # =========================================================================
    # 7. Render stages → GPU blocks
    #    Source: Vulkan spec §8 (render pass), OpenGL ES 3.x spec
    # =========================================================================
    logger.info("Linking render stages...")

    render_stages = {
        "render-depth-prepass": "GPU-rasterizer",
        "render-gbuffer": "GPU-shader-core",
        "render-shadow-map": "GPU-rasterizer",
        "render-color-pass": "GPU-shader-core",
        "render-post-process": "GPU-shader-core",
        "render-ui-pass": "GPU-shader-core",
    }
    for stage, target in render_stages.items():
        link("ROUTES_TO", "Component", "Component", stage, target)

    # =========================================================================
    # 8. V4L2/Media framework nodes → camera pipeline
    #    Source: Linux Documentation/userspace-api/media/
    # =========================================================================
    logger.info("Linking V4L2/media framework nodes...")

    # media-controller and media-entity are core kernel subsystem framework
    link("ROUTES_TO", "Component", "Component", "media-entity", "ISP-pipeline")
    link("ROUTES_TO", "Component", "Component", "media-controller", "ISP-pipeline")
    link("ROUTES_TO", "Component", "Component", "media-controller", "MIPI-CSI2-RX")

    # V4L2 framework components → ISP pipeline
    link("ROUTES_TO", "Component", "Component", "v4l2-subdev", "ISP-pipeline")
    link("ROUTES_TO", "Component", "Component", "v4l2-subdev", "camera-sensor-drv")
    link("ROUTES_TO", "Component", "Component", "v4l2-async", "v4l2-subdev")
    link("ROUTES_TO", "Component", "Component", "v4l2-fwnode", "v4l2-async")
    link("ROUTES_TO", "Component", "Component", "v4l2-ctrl-framework", "v4l2-subdev")
    link("ROUTES_TO", "Component", "Component", "v4l2-m2m", "ISP-pipeline")
    link("ROUTES_TO", "Component", "Component", "videobuf2", "dma-buf-core")
    link("ROUTES_TO", "Component", "Component", "v4l2-video-dev", "v4l2-subdev")

    # Camera HAL/API
    link("ROUTES_TO", "Component", "Component", "camera2-api", "camera-hal3")
    link("ROUTES_TO", "Component", "Component", "camera-hal3", "camera-hal3-adapter")
    link("ROUTES_TO", "Component", "Component", "camera-hal3-adapter", "v4l2-video-dev")
    link("ROUTES_TO", "Component", "Component", "camera-flash-drv", "camera-sensor-drv")
    link("ROUTES_TO", "Component", "Component", "camera-lens-drv", "camera-sensor-drv")

    # =========================================================================
    # 9. DRM framework nodes → GPU subsystem
    #    Source: Linux kernel DRM subsystem documentation
    # =========================================================================
    logger.info("Linking DRM framework nodes...")

    link("ROUTES_TO", "Component", "Component", "drm-core", "GPU-Controller")
    link("ROUTES_TO", "Component", "Component", "drm-gem", "drm-core")
    link("ROUTES_TO", "Component", "Component", "drm-scheduler", "GPU-job-manager")
    link("ROUTES_TO", "Component", "Component", "drm-syncobj", "drm-core")
    link("ROUTES_TO", "Component", "Component", "drm-bridge", "drm-core")
    link("ROUTES_TO", "Component", "Component", "panfrost-driver", "GPU-Controller")
    link("ROUTES_TO", "Component", "Component", "panfrost-driver", "drm-core")

    # GPU APIs
    link("ROUTES_TO", "Component", "Component", "vulkan-pipeline", "GPU-shader-core")
    link("ROUTES_TO", "Component", "Component", "vulkan-render-pass", "GPU-frontend")
    link("ROUTES_TO", "Component", "Component", "opengl-es-context", "GPU-frontend")
    link("ROUTES_TO", "Component", "Component", "egl-display", "drm-core")

    # =========================================================================
    # 10. Bus protocol/component/channel nodes → SoC interconnect
    #     Source: AMBA AXI4 Protocol Specification
    # =========================================================================
    logger.info("Linking bus protocol/component nodes...")

    # AXI channels → AXI4-Interconnect
    axi_channels = ["AXI4-AW-Channel", "AXI4-W-Channel", "AXI4-B-Channel",
                    "AXI4-AR-Channel", "AXI4-R-Channel"]
    for ch in axi_channels:
        link("ROUTES_TO", "Component", "Component", ch, "AXI4-Interconnect")

    # AXI ports → AXI4-Interconnect
    link("ROUTES_TO", "Component", "Component", "AXI4-Master-Port", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI4-Slave-Port", "AXI4-Interconnect")

    # AXI protocol variants → SoC-NoC
    link("ROUTES_TO", "Component", "Component", "AXI4-Interconnect", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "AXI4-Lite", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI4-Stream", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI-ACE", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI-ACE-Lite", "AXI4-Interconnect")

    # Bus bridges
    link("ROUTES_TO", "Component", "Component", "APB-to-AXI4-Bridge", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI4-to-AHB-Bridge", "AHB-Bus")

    # Bus components (QoS, arbiters, etc.)
    link("ROUTES_TO", "Component", "Component", "AXI-Arbiter", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI-Clock-Bridge", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI-Width-Converter", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI4-AxPROT", "AXI4-Interconnect")
    link("ROUTES_TO", "Component", "Component", "AXI4-Barrier", "AXI4-Interconnect")

    # QoS components → interconnect
    link("ROUTES_TO", "Component", "Component", "AXI-Bandwidth-Limiter", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "AXI-QoS-Controller", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "pm-qos-dev", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "pm-qos-interconnect", "SoC-NoC")

    # MIPI-I3C
    link("ROUTES_TO", "Component", "Component", "MIPI-I3C", "SoC-NoC")

    # =========================================================================
    # 11. Linux kernel framework/subsystem nodes
    #     Source: Linux kernel Documentation/
    # =========================================================================
    logger.info("Linking Linux kernel framework nodes...")

    # Clock framework
    link("ROUTES_TO", "Component", "Component", "linux-clk-core", "linux-clk-pll")
    link("ROUTES_TO", "Component", "Component", "linux-clkdev", "linux-clk-core")
    link("ROUTES_TO", "Component", "Component", "linux-clk-composite", "linux-clk-core")
    link("ROUTES_TO", "Component", "Component", "linux-clk-mux", "linux-clk-core")
    link("ROUTES_TO", "Component", "Component", "linux-clk-rpchk", "linux-clk-core")
    link("ROUTES_TO", "Component", "Component", "linux-clk-scmi", "linux-scmi-core")
    link("ROUTES_TO", "Component", "Component", "linux-clk-summary", "linux-clk-core")

    # Power management framework
    link("ROUTES_TO", "Component", "Component", "linux-pm-runtime", "linux-pm-qos-core")
    link("ROUTES_TO", "Component", "Component", "linux-platform-suspend-ops", "linux-pm-runtime")
    link("ROUTES_TO", "Component", "Component", "linux-power-supply", "linux-pm-runtime")

    # Regulator/subsystem frameworks
    link("ROUTES_TO", "Component", "Component", "regulator-framework", "PMIC-BUCK1")
    link("ROUTES_TO", "Component", "Component", "thermal-framework", "pmic-thermal")
    link("ROUTES_TO", "Component", "Component", "opp-core", "cpufreq-core")
    link("ROUTES_TO", "Component", "Component", "cpufreq-core", "opp-core")

    # OPP config nodes
    link("ROUTES_TO", "Component", "Component", "opp-table-cpu", "opp-core")
    link("ROUTES_TO", "Component", "Component", "opp-table-gpu", "opp-core")
    link("ROUTES_TO", "Component", "Component", "opp-table-ddr", "opp-core")

    # DMA/memory allocators
    link("ROUTES_TO", "Component", "Component", "dma-heap", "dma-buf-core")
    link("ROUTES_TO", "Component", "Component", "cma-heap", "dma-heap")
    link("ROUTES_TO", "Component", "Component", "ion-allocator", "dma-buf-core")
    link("ROUTES_TO", "Component", "Component", "DMA-BUF-Heap", "dma-buf-core")
    link("ROUTES_TO", "Component", "Component", "ION-Allocator", "dma-buf-core")

    # Bus/driver frameworks
    link("ROUTES_TO", "Component", "Component", "linux-i2c-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-spi-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-gpio-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-phy-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-serdev", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-iio", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-input-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-led-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-pwm-core", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-watchdog", "SoC-NoC")

    # Debug/trace frameworks
    link("ROUTES_TO", "Component", "Component", "linux-debugfs", "linux-ftrace")
    link("ROUTES_TO", "Component", "Component", "linux-dynamic-debug", "linux-debugfs")
    link("ROUTES_TO", "Component", "Component", "linux-kprobes", "linux-ftrace")
    link("ROUTES_TO", "Component", "Component", "linux-ftrace", "CoreSight-SoC600")
    link("ROUTES_TO", "Component", "Component", "linux-devcoredump", "linux-debugfs")
    link("ROUTES_TO", "Component", "Component", "perf-event-core", "linux-ftrace")

    # DMA engine
    link("ROUTES_TO", "Component", "Component", "linux-dma-engine", "DMA-PL330")
    link("ROUTES_TO", "Component", "Component", "DMA-Controller", "DMA-PL330")

    # Regmap, SCMI
    link("ROUTES_TO", "Component", "Component", "linux-regmap", "linux-i2c-core")
    link("ROUTES_TO", "Component", "Component", "linux-scmi-core", "SoC-NoC")

    # Other kernel subsystems
    link("ROUTES_TO", "Component", "Component", "linux-dm-verity", "linux-debugfs")
    link("ROUTES_TO", "Component", "Component", "linux-kexec-secure", "linux-debugfs")
    link("ROUTES_TO", "Component", "Component", "linux-poe-arm64", "linux-phy-core")
    link("ROUTES_TO", "Component", "Component", "linux-axp717-power", "linux-power-supply")

    # =========================================================================
    # 12. Storage/bus controllers
    #     Source: Linux kernel storage subsystem docs
    # =========================================================================
    logger.info("Linking storage/controller nodes...")

    link("ROUTES_TO", "Component", "Component", "USB3-Controller", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "SDIO-Controller", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "SPI-NOR-Controller", "linux-spi-core")

    # =========================================================================
    # 13. Security/firmware nodes
    #     Source: ARM TrustZone TRM, ARM SAU Architecture Reference
    # =========================================================================
    logger.info("Linking security/firmware nodes...")

    link("ROUTES_TO", "Component", "Component", "ARM-SAU", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "TrustZone-TZPC", "ARM-SAU")
    link("ROUTES_TO", "Component", "Component", "Secure-World-Monitor", "ARM-SAU")
    link("ROUTES_TO", "Component", "Component", "ARM-SCP", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "linux-efi-stub", "SoC-NoC")

    # =========================================================================
    # 14. Misc orphans — PLLs, clocks, timers, etc.
    # =========================================================================
    logger.info("Linking misc orphan nodes...")

    # PLLs (Component type) → CPU/GPU/DDR via ROUTES_TO
    link("ROUTES_TO", "Component", "Component", "PLL-CPU-BIG", "Cortex-A76-Cluster")
    link("ROUTES_TO", "Component", "Component", "PLL-DDR", "LPDDR5-DRAM")
    link("ROUTES_TO", "Component", "Component", "PLL-GPU", "GPU-Controller")

    # DSU-L3 cache → CPU clusters
    link("ROUTES_TO", "Component", "Component", "DSU-L3", "Cortex-A55-Cluster")
    link("ROUTES_TO", "Component", "Component", "DSU-L3", "Cortex-A76-Cluster")

    # Timer, PMU
    link("ROUTES_TO", "Component", "Component", "ARM-Generic-Timer", "Cortex-A55-Cluster")
    link("ROUTES_TO", "Component", "Component", "ARM-PMU-IRQ-Overflow", "GIC-600")

    # PMIC-LDO1, PMIC-BUCK4 → voltage regulators to SoC components
    link("ROUTES_TO", "Component", "Component", "PMIC-LDO1", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "PMIC-BUCK4", "LPDDR5-DRAM")

    # SMMUv3-VMID → GIC (IOMMU + virtualization)
    link("ROUTES_TO", "Component", "Component", "SMMUv3-VMID", "GIC-600")

    # PSCI firmware interface
    link("ROUTES_TO", "Component", "Component", "PSCI-CPU_SUSPEND", "ARM-PSCI-CPU_SUSPEND")
    link("ROUTES_TO", "Component", "Component", "ARM-PSCI-SYSTEM_SUSPEND", "ARM-PSCI-CPU_SUSPEND")

    # GPU thermal
    link("ROUTES_TO", "Component", "Component", "GPU-thermal-zone", "GPU-Controller")

    # GICv5 nodes
    link("ROUTES_TO", "Component", "Component", "GICv5-Power-Mgmt", "GIC-600")
    link("ROUTES_TO", "Component", "Component", "GICv5-Realm-Support", "GIC-600")

    # vGIC/KVM
    link("ROUTES_TO", "Component", "Component", "vGIC-KVM", "GIC-600")

    # MTK power domains
    link("ROUTES_TO", "Component", "Component", "mtk-mt8188-power-domains", "SoC-NoC")
    link("ROUTES_TO", "Component", "Component", "mtk-pmic-auxadc", "pmic-thermal")

    # MIPI CSI2 TX
    link("ROUTES_TO", "Component", "Component", "MIPI-CSI2-TX", "MIPI-CSI2-RX")

    # IPC/Mailbox
    link("ROUTES_TO", "Component", "Component", "IPI-Mailbox", "ARM-SCP")
    link("ROUTES_TO", "Component", "Component", "ARM-MHU", "ARM-SCP")

    # Crystal oscillator
    link("ROUTES_TO", "Component", "Component", "XTAL-26MHz", "SoC-NoC")

    # CoreSight TMC
    link("ROUTES_TO", "Component", "Component", "CoreSight-TMC", "CoreSight-SoC600")

    # ISP-AF block
    link("ROUTES_TO", "Component", "Component", "ISP-AF", "ISP-pipeline")

    # UFS features
    link("ROUTES_TO", "Component", "Component", "UFS-HPB", "UFS-host-controller")
    link("ROUTES_TO", "Component", "Component", "UFS-inline-crypto", "UFS-host-controller")

    # Mali-GPU orphan → GPU-Controller
    link("ROUTES_TO", "Component", "Component", "Mali-GPU", "GPU-Controller")

    # ARM-CMN watchpoint
    link("ROUTES_TO", "Component", "Component", "ARM-CMN-Watchpoint", "CMN-650")

    # =========================================================================
    # 15. PowerDomain → POWERS → Components
    #     Source: ARM DynamIQ TRM, Linux genpd framework
    # =========================================================================
    logger.info("Linking unlinked PowerDomains...")

    pd_powers = {
        "PD-NPU": ["SoC-NoC"],  # NPU powered by its domain
        "PD-DISPLAY": ["display-controller"],
        "PD-ISP": ["ISP-Controller"],
        "PD-DDR": ["LPDDR5-DRAM"],
        "PD-ALWAYS-ON": ["SoC-NoC"],
        "PD-SYSTEM-STD": ["SoC-NoC"],
        "PD-DRAM-IO": ["LPDDR5-DRAM"],
        "PD-DISP": ["display-controller"],
    }
    for pd, targets in pd_powers.items():
        for target in targets:
            link("POWERS", "PowerDomain", "Component", pd, target)

    # =========================================================================
    # 16. ClockSource → CLOCKS → Components
    #     Source: Linux Documentation/driver-api/clk.rst, MT6989 clock tree
    # =========================================================================
    logger.info("Linking unlinked ClockSources...")

    # CPU cluster clocks
    for i in range(1, 4):
        link("CLOCKS", "ClockSource", "Component", f"clk-a55-{i}", "Cortex-A55-Cluster")
    for i in range(1, 3):
        link("CLOCKS", "ClockSource", "Component", f"clk-a76-{i}", "Cortex-A76-Cluster")
    link("CLOCKS", "ClockSource", "Component", "clk-ddr", "LPDDR5-DRAM")
    link("CLOCKS", "ClockSource", "Component", "clk-ref-26mhz", "SoC-NoC")

    # Oscillators → PLL roots
    link("CLOCKS", "ClockSource", "Component", "OSC-26M", "SoC-NoC")
    link("CLOCKS", "ClockSource", "Component", "OSC-32K", "SoC-NoC")
    link("CLOCKS", "ClockSource", "Component", "TCXO-26M", "SoC-NoC")

    # PLLs → subsystems
    pll_targets = {
        "PLL-MAINPLL": "SoC-NoC",
        "PLL-UNIVPLL": "SoC-NoC",
        "PLL-MMPLL": "ISP-Controller",
        "PLL-GPUPLL": "GPU-Controller",
        "PLL-EMIPLL": "LPDDR5-DRAM",
        "PLL-TVDPLL": "display-controller",
        "PLL-NNAPLL": "SoC-NoC",  # NPU
        "PLL-AUDPLL": "SoC-NoC",
        "PLL-MSDCPLL": "eMMC-host-controller",
    }
    for pll, target in pll_targets.items():
        link("CLOCKS", "ClockSource", "Component", pll, target)

    # Clock dividers → subsystems
    for div in ["CLK-SYSPLL-D2", "CLK-SYSPLL-D4", "CLK-SYSPLL-D8"]:
        link("CLOCKS", "ClockSource", "Component", div, "SoC-NoC")
    for div in ["CLK-UNIVPLL-D2", "CLK-UNIVPLL-D4", "CLK-UNIVPLL-D8"]:
        link("CLOCKS", "ClockSource", "Component", div, "SoC-NoC")
    for div in ["CLK-MMPLL-D2", "CLK-MMPLL-D4"]:
        link("CLOCKS", "ClockSource", "Component", div, "ISP-Controller")
    link("CLOCKS", "ClockSource", "Component", "CLK-GPUPLL-D2", "GPU-Controller")

    # Peripheral clocks
    link("CLOCKS", "ClockSource", "Component", "CLK-UART-26M", "SoC-NoC")
    link("CLOCKS", "ClockSource", "Component", "CLK-I2C-HS", "SoC-NoC")
    link("CLOCKS", "ClockSource", "Component", "CLK-SPI-52M", "SoC-NoC")
    link("CLOCKS", "ClockSource", "Component", "CLK-ISP-MAIN", "ISP-Controller")
    link("CLOCKS", "ClockSource", "Component", "CLK-VENC", "SoC-NoC")
    link("CLOCKS", "ClockSource", "Component", "CLK-DISP", "display-controller")
    link("CLOCKS", "ClockSource", "Component", "CLK-AUD-INTBUS", "SoC-NoC")

    # =========================================================================
    # 17. FailureMode → CAUSED_BY → Component (root-cause component)
    #     Schema: CAUSED_BY goes FROM FailureMode TO Component
    #     Source: Open-source kernel bug trackers, ARM erratas, Linux PM docs
    # =========================================================================
    logger.info("Linking disconnected FailureModes...")

    # Each FailureMode is linked to the Component most likely to be its root cause
    fm_component_links = [
        # DVFS failures → power/clock components
        ("FM-DVFS-OPP-Not-Supported", "opp-core"),
        ("FM-DVFS-Voltage-Notifier-Timeout", "PMIC-BUCK1"),
        ("FM-DVFS-Clock-Set-Fail", "linux-clk-core"),
        ("FM-DVFS-OPP-Voltage-Drop", "PMIC-BUCK1"),
        ("FM-DVFS-Thermal-Throttle-Loop", "thermal-framework"),
        ("FM-DVFS-EAS-Misplacement", "EAS-Task-Placement"),
        ("FM-Devfreq-QoS-Conflict", "SoC-NoC"),

        # Power failures → PMIC/power domain components
        ("FM-PMIC-Supply-Sequence-Violation", "PMIC-BUCK1"),
        ("FM-Power-Domain-Off-Under-Use", "linux-pm-runtime"),
        ("FM-Retention-State-Data-Loss", "LPDDR5-DRAM"),
        ("FM-C-State-Stuck", "Cortex-A55-Cluster"),
        ("FM-LDO-Dropout-Brown-Out", "PMIC-LDO1"),
        ("FM-PSCI-CPU-Suspend-Hang", "ARM-PSCI-CPU_SUSPEND"),
        ("FM-Genpd-Power-Off-With-Active-Child", "linux-pm-runtime"),

        # Boot failures → boot chain components
        ("FM-DRAM-Init-Fail", "LPDDR5-DRAM"),
        ("FM-DTB-Mismatch", "SoC-NoC"),
        ("FM-PLL-Lock-Timeout", "PLL-CPU-BIG"),
        ("FM-PSCI-Version-Mismatch", "ARM-PSCI-CPU_SUSPEND"),
        ("FM-Secure-Boot-Chain-Break", "Secure-World-Monitor"),
        ("FM-UART-Baud-Rate-Wrong", "SoC-NoC"),
        ("FM-TFA-BL2-Load-Fail", "Secure-World-Monitor"),

        # Multimedia failures → ISP/camera/storage components
        ("FM-DMA-Buffer-Starvation", "dma-buf-core"),
        ("FM-ISP-Timeout-Frame-Freeze", "ISP-pipeline"),
        ("FM-MIPI-CSI2-Lane-Desync", "MIPI-CSI2-RX"),
        ("FM-CSI2-ECC-Uncorrectable", "MIPI-CSI2-RX"),
        ("FM-V4L2-Buffer-Overflow", "videobuf2"),
        ("FM-F2FS-Checkpoint-Latency", "eMMC-host-controller"),

        # Interrupt failures → GIC components
        ("FM-IRQ-Storm", "GIC-600"),
        ("FM-Spurious-IRQ", "GIC-600-Redistributor"),
        ("FM-ITS-MSI-Map-Failure", "GIC-600-ITS"),
        ("FM-GIC-Redistributor-Off", "GIC-600-Redistributor"),

        # GPU failures → GPU components
        ("FM-GPU-Thermal-Runaway", "GPU-Controller"),
        ("FM-GPU-Command-Timeout", "GPU-job-manager"),
        ("FM-GPU-Page-Fault", "GPU-MMU"),

        # Display failures → display components
        ("FM-Display-FIFO-Underflow", "display-controller"),
        ("FM-DSI-Command-Timeout", "MIPI-DSI2-Host"),
        ("FM-MIPI-DSI-Timeout-Underflow", "display-controller"),

        # Interconnect/memory failures
        ("FM-NoC-Timeout", "SoC-NoC"),
        ("FM-CHI-Snoop-Filter-Overflow", "CMN-650"),
        ("FM-CMA-Allocation-Fail", "cma-heap"),
        ("FM-DDR-Frequency-Stuck", "LPDDR5-DRAM"),
        ("FM-IOMMU-Fault-DMA", "GPU-MMU"),
        ("FM-Interconnect-Bandwidth-Starve", "SoC-NoC"),

        # Storage failures
        ("FM-eMMC-HS400-Tuning-Fail", "eMMC-host-controller"),
        ("FM-UFS-Hibern8-Stuck", "UFS-host-controller"),

        # Thermal/PCIe/USB/Watchdog
        ("FM-Thermal-Zone-Missing", "pmic-thermal"),
        ("FM-PCIe-ATS-Fault", "PCIe-Controller"),
        ("FM-USB-Enumeration-Fail", "USB3-Controller"),
        ("FM-Watchdog-Bark-Reset", "SoC-NoC"),
    ]
    for fm, component in fm_component_links:
        link("CAUSED_BY", "FailureMode", "Component", fm, component)

    # =========================================================================
    # Summary
    # =========================================================================
    stats = {"created": created, "failed": failed}
    logger.info("Orphan remediation complete: %d relationships created, %d failed", created, failed)
    return stats


def ingest(db_path: str | None = None) -> int:
    """Entry point for build_base_graph.py orchestrator. Returns 0 (no new nodes)."""
    stats = run(db_path)
    logger.info(
        "[fix-orphan-connectivity] %d relationships created, %d failed",
        stats["created"], stats["failed"],
    )
    return 0  # no new nodes created, only relationships


if __name__ == "__main__":
    stats = run()
    print(f"\nRelationships created: {stats['created']}")
    print(f"Relationships failed:  {stats['failed']}")
