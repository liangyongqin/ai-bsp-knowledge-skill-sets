"""
Common BSP Failure Modes — seed knowledge ingestion.

Ingests open-source documented BSP failure patterns from LKML, Bootlin,
Linaro mailing lists, and publicly documented SoC debug guides.

Reference: LKML archives, Bootlin blog, Linaro Connect presentations,
           Android Bug Reports, Linux kernel Documentation/fault-injection/
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

_FAILURE_MODES = [
    ("FM-DVFS-OPP-Not-Supported",
     "cpufreq: WARN OPP not found for frequency X",
     "DT opp-table missing entry for a valid CPU frequency step, schedutil cannot set OPP",
     "dvfs", "LKML/cpufreq mailing list", "medium"),
    ("FM-DVFS-Voltage-Notifier-Timeout",
     "regulator: timeout waiting for voltage change completion",
     "PMIC I2C/SPI bus congestion delays voltage notifier callback beyond schedutil window",
     "dvfs", "Linaro Connect LVC22", "high"),
    ("FM-DVFS-Clock-Set-Fail",
     "clk_set_rate() returns -EINVAL for PLL frequency",
     "PLL VCO range exceeded because parent reference clock rate changed without updating child OPP table",
     "dvfs", "LKML/clk mailing list", "high"),
    ("FM-DVFS-OPP-Voltage-Drop",
     "system hang or random crashes at high load",
     "OPP voltage corner too low for frequency: sign-off voltage not correctly characterised at final silicon",
     "dvfs", "Bootlin blog 2021", "critical"),
    ("FM-DVFS-Thermal-Throttle-Loop",
     "CPU frequency oscillates between max and throttled state repeatedly",
     "Thermal trip threshold set too close to sustained load temperature; hysteresis too small",
     "dvfs", "LKML/thermal mailing list", "medium"),
    ("FM-DVFS-EAS-Misplacement",
     "big core busy while LITTLE cores idle at high load; battery drains fast",
     "Energy model capacity values not calibrated to silicon; EAS places tasks on wrong cluster",
     "dvfs", "Linaro EAS summit 2022", "medium"),
    ("FM-PMIC-Supply-Sequence-Violation",
     "SoC fails to boot or resets randomly after power-on; PMIC fault register set",
     "Power rail bring-up order violates PMIC sequencer spec; VDD_IO raised before VDD_CORE",
     "power", "Bootlin BSP bring-up guide", "critical"),
    ("FM-Power-Domain-Off-Under-Use",
     "kernel oops or bus error when accessing peripheral registers",
     "Power domain disabled by runtime PM while peripheral is still actively being used",
     "power", "LKML/pm-runtime mailing list", "critical"),
    ("FM-Retention-State-Data-Loss",
     "kernel crash or register corruption after deep idle resume",
     "CPU cluster retention power not maintained during suspend; SRAM context lost",
     "power", "Linaro Connect YVR18", "high"),
    ("FM-LDO-Dropout-Brown-Out",
     "intermittent peripheral failures under thermal stress",
     "LDO headroom drops below dropout voltage at high temperature; output voltage collapses",
     "power", "JEDEC JEP106/JEP122 reference", "high"),
    ("FM-PSCI-CPU-Suspend-Hang",
     "CPU core never wakes from PSCI CPU_SUSPEND; system unresponsive",
     "Secure firmware PSCI handler does not restore GIC Redistributor before waking CPU",
     "power", "ARM PSCI erratum list", "critical"),
    ("FM-PLL-Lock-Timeout",
     "Kernel panics early boot: PLL failed to lock; clock init aborted",
     "PLL reference clock missing or noisy; VDD_PLL supply not stable before lock attempt",
     "boot", "Bootlin BSP debugging guide", "critical"),
    ("FM-UART-Baud-Rate-Wrong",
     "Serial console shows garbage characters; boot log unreadable",
     "UART clock source misconfigured in DT; baud rate divisor computed from wrong parent clock",
     "boot", "LKML/serial mailing list", "low"),
    ("FM-DTB-Mismatch",
     "Kernel hangs silently after decompression; no output on serial",
     "Wrong DTB loaded for hardware revision; CPU topology mismatch causes early init failure",
     "boot", "Bootlin blog 2020", "critical"),
    ("FM-PSCI-Version-Mismatch",
     "PSCI operations fail at boot: CPU_ON returns NOT_SUPPORTED",
     "ATF compiled with PSCI 1.0 but kernel expects PSCI 0.2 interface; ABI mismatch",
     "boot", "ARM TF-A documentation", "high"),
    ("FM-Secure-Boot-Chain-Break",
     "Boot stops at BL2 with authentication failure; device bricked if fuses blown",
     "SPL/BL2 hash in OTP does not match built image; key rotation not properly committed",
     "boot", "ARM TF-A security advisory", "critical"),
    ("FM-DRAM-Init-Fail",
     "Boot halts at DDR training; no output after DRAM message",
     "LPDDR5 training parameters MR8/MR18 not matched to DRAM vendor part; PHY training times out",
     "boot", "JEDEC JESD79-5 / LKML", "critical"),
    ("FM-V4L2-Buffer-Overflow",
     "V4L2: DQBUF returns -EIO; frame dropped counter increments",
     "Userspace queue depth insufficient for ISP throughput; producer-consumer rate mismatch",
     "multimedia", "Linux V4L2 Documentation", "medium"),
    ("FM-DMA-Buffer-Starvation",
     "DMA: no free buffer; frame pipeline stalls; ISP watchdog fires",
     "DMA-BUF heap exhausted; userspace not releasing buffers fast enough; ref count leak",
     "multimedia", "Android Camera HAL bug reports", "high"),
    ("FM-MIPI-CSI2-Lane-Desync",
     "Camera image shows corrupted lines or green screen; CSI2 error register set",
     "MIPI CSI-2 HS clock lane frequency mismatch between sensor and receiver; termination resistance wrong",
     "multimedia", "MIPI Alliance debugging guide", "high"),
    ("FM-ISP-Timeout-Frame-Freeze",
     "Camera preview freezes; ISP status shows TIMEOUT; kernel log ISP_STALL error",
     "ISP input buffer not filled in time (sensor stopped streaming); ISP watchdog not cleared",
     "multimedia", "Bootlin V4L2 talk 2023", "medium"),
    ("FM-F2FS-Checkpoint-Latency",
     "Camera capture stutters every 60s; jank in video encoder",
     "F2FS filesystem checkpoint triggered during video encoding; IO latency spike blocks V4L2 pipeline",
     "multimedia", "LKML/f2fs mailing list", "medium"),
    ("FM-IRQ-Storm",
     "CPU at 100% in interrupt handler; system unresponsive; /proc/interrupts shows millions of IRQs/s",
     "Peripheral generates level-triggered interrupt but driver does not clear interrupt source register; IRQ re-fires immediately",
     "interrupt", "LKML/irq mailing list", "critical"),
    ("FM-Spurious-IRQ",
     "kernel: irq 64: nobody cared; IRQ masked by kernel",
     "Interrupt affinity set to offline CPU; or GIC route misconfigured after CPU hotplug",
     "interrupt", "LKML/irq mailing list", "medium"),
    ("FM-ITS-MSI-Map-Failure",
     "PCIe device fails to allocate MSI; pci_enable_msi() returns -ENOSPC",
     "ITS device table exhausted or MSI domain not properly configured in DT",
     "interrupt", "LKML/pcie mailing list", "high"),
    ("FM-GIC-Redistributor-Off",
     "CPU receives no interrupts after wake from idle; system hangs",
     "GIC Redistributor power domain gated before wakeup sources deactivated; GICR_WAKER.ChildrenAsleep not checked",
     "interrupt", "ARM GIC-600 TRM erratum list", "critical"),
    ("FM-GPU-Thermal-Runaway",
     "GPU temperature exceeds 100C; thermal shutdown; device reboots",
     "GPU DVFS cooling device not registered with thermal framework; frequency not throttled on overheat",
     "gpu", "Android GPU Inspector docs", "critical"),
    ("FM-GPU-Command-Timeout",
     "GPU job timeout: drm/panfrost: GPU timeout; GPU reset triggered",
     "Shader job depends on stalled DMA transfer; GPU command queue blocked waiting for memory",
     "gpu", "Linux DRM/panfrost driver", "high"),
    ("FM-GPU-Page-Fault",
     "GPU MMU fault: unmapped address; process killed; GPU reset",
     "GPU buffer freed by CPU before GPU command referencing it completes; sync primitive not used",
     "gpu", "Vulkan spec Appendix A / LKML", "high"),
    ("FM-Thermal-Zone-Missing",
     "thermal: thermal_zone_device_register failed; temperature unavailable",
     "TSENS DT node missing or clock/power domain for thermal sensor not enabled at boot",
     "thermal", "Linux thermal framework docs", "medium"),
    ("FM-C-State-Stuck",
     "CPU core offline; hrtimer not firing; latency spikes; /proc/cpuidle shows no C2+ entries",
     "PSCI CPU_SUSPEND returning immediately; platform idle driver not matched in DT compatible string",
     "power", "Linaro Connect HKG18", "high"),
    ("FM-IOMMU-Fault-DMA",
     "IOMMU fault: unhandled context fault from DMA master; peripheral fails",
     "DMA-BUF fd not mapped into IOMMU domain before DMA transfer starts; SMMU stream ID misconfigured",
     "memory", "ARM SMMUv3 documentation", "high"),
    ("FM-CMA-Allocation-Fail",
     "dma_alloc_coherent() returns NULL at runtime; camera/video stalls",
     "CMA reserved memory fragmented at boot by early drivers; contiguous allocation fails",
     "memory", "Linux CMA documentation", "medium"),
    ("FM-DDR-Frequency-Stuck",
     "LPDDR5 devfreq governor not changing frequency; memory bandwidth fixed at minimum",
     "DDR PHY PLL not locked at target frequency; devfreq driver returns error and stops scaling",
     "memory", "JEDEC JESD79-5 / LKML", "medium"),
    ("FM-Watchdog-Bark-Reset",
     "Watchdog bark: CPU0 hung; system hard reset",
     "Kernel deadlock in spinlock path blocks watchdog pet thread; timer not serviced",
     "system", "Android Watchdog documentation", "critical"),
]


def ingest(db_path: str = None) -> int:
    """Ingest common BSP failure modes into the Kuzu database."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = os.path.abspath(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    inserted = 0
    for name, symptom, root_cause, domain, source, severity in _FAILURE_MODES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": domain, "source": source,
            "namespace": "base", "severity": severity,
        }):
            inserted += 1

    # CAUSED_BY relationships
    for fm, comp, desc in [
        ("FM-PMIC-Supply-Sequence-Violation", "PMIC-BUCK1", "PMIC supply sequencer violation causes power-on fail"),
        ("FM-Power-Domain-Off-Under-Use", "PD-CPU-LITTLE", "Power domain gated under active use"),
        ("FM-PSCI-CPU-Suspend-Hang", "GIC-600-Redistributor", "GIC Redistributor not restored before PSCI wake"),
        ("FM-GIC-Redistributor-Off", "GIC-600-Redistributor", "GIC Redistributor gated before wakeup source deactivated"),
        ("FM-IRQ-Storm", "GIC-600", "GIC continually re-triggers level-triggered IRQ"),
        ("FM-ITS-MSI-Map-Failure", "GIC-600-ITS", "ITS device table exhausted"),
        ("FM-PLL-Lock-Timeout", "PLL-CPU-LITTLE", "CPU PLL fails to lock"),
        ("FM-DVFS-Clock-Set-Fail", "PLL-CPU-BIG", "Big cluster PLL VCO range exceeded"),
        ("FM-DVFS-Voltage-Notifier-Timeout", "PMIC-BUCK2", "PMIC BUCK2 voltage change too slow"),
        ("FM-V4L2-Buffer-Overflow", "ISP-Controller", "ISP produces frames faster than userspace dequeues"),
        ("FM-DMA-Buffer-Starvation", "DMA-BUF", "DMA-BUF heap exhausted"),
        ("FM-MIPI-CSI2-Lane-Desync", "MIPI-CSI2-RX", "MIPI CSI-2 receiver lane synchronisation lost"),
        ("FM-GPU-Thermal-Runaway", "GPU-Controller", "GPU cooling device not registered"),
        ("FM-GPU-Command-Timeout", "GPU-AXI-Master", "GPU AXI master stalled waiting for DMA"),
        ("FM-GPU-Page-Fault", "SMMU-v3", "SMMU fault on unmapped GPU buffer"),
        ("FM-IOMMU-Fault-DMA", "SMMU-v3-AXI-Slave", "SMMUv3 stream ID misconfigured for DMA master"),
        ("FM-CMA-Allocation-Fail", "DDR-Controller", "DDR CMA region fragmented"),
        ("FM-DRAM-Init-Fail", "DDR-Controller", "LPDDR5 PHY training timeout in DDR controller"),
        ("FM-DDR-Frequency-Stuck", "PLL-DDR", "DDR PLL not locking at target frequency"),
    ]:
        try:
            conn.execute(
                "MATCH (f:FailureMode {name: $fm}), (c:Component {name: $comp}) "
                "CREATE (f)-[:CAUSED_BY {description: $desc}]->(c)",
                {"fm": fm, "comp": comp, "desc": desc},
            )
        except Exception:
            pass

    # AFFECTS_IF_REMOVED relationships
    for src, dst, desc in [
        ("PMIC-BUCK1", "Cortex-A55-Cluster", "Removing BUCK1 kills LITTLE cluster power"),
        ("PMIC-BUCK2", "Cortex-A76-Cluster", "Removing BUCK2 kills big cluster power"),
        ("GIC-600-Redistributor", "ARM-Cortex-A55", "GIC Redistributor removal blocks all interrupts to A55"),
        ("GIC-600-ITS", "PCIe-Controller", "Removing ITS breaks all MSI/MSI-X for PCIe"),
        ("DMA-BUF", "ISP-Controller", "Removing DMA-BUF stalls ISP frame pipeline"),
        ("SMMU-v3", "GPU-AXI-Master", "Removing SMMU protection exposes GPU to unprotected DMA"),
        ("PLL-CPU-LITTLE", "Cortex-A55-Cluster", "Removing LITTLE PLL freezes LITTLE cluster clock"),
        ("DDR-Controller", "CPU-Cluster-AXI-Master", "DDR controller loss makes all memory inaccessible"),
    ]:
        create_rel(conn, "AFFECTS_IF_REMOVED", "Component", "Component", src, dst, {"description": desc})

    print(f"[common-failure-modes] Inserted {inserted} FailureMode nodes.")
    return inserted


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db-path", default=None)
    args = p.parse_args()
    ingest(args.db_path)
