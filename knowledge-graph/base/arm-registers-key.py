"""
Key ARM/SoC Registers seed — open-source knowledge ingestion.

Adds commonly referenced hardware registers from ARM TRMs and Linux
devicetree bindings that BSP engineers encounter during debugging.

Sources:
  - ARM GIC-600 TRM (ARM DDI 0500) — register map
  - ARM SMMUv3 Architecture Spec IHI0070 — register map
  - ARM CoreSight TRM — register map
  - Linux kernel Documentation/devicetree/bindings/
  - ARM PMU architecture spec — system registers

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
# Registers — GIC-600
# ---------------------------------------------------------------------------

_GIC_REGS = [
    ("GICD_CTLR",       "0x0000", 32, "RW", "0x00000000",
     "GIC Distributor Control Register — enables Group 0/1S/1NS interrupts, "
     "ARE (Affinity Routing Enable), E1NWF (Enable 1-of-N Wakeup)",
     "GIC-600", "base"),
    ("GICD_TYPER",       "0x0004", 32, "RO", "impl-defined",
     "GIC Distributor Type Register — reports number of SPIs, LPIs, security states; "
     "ITLinesNumber field defines max SPI count",
     "GIC-600", "base"),
    ("GICD_ISENABLER0",  "0x0100", 32, "RW", "0x0000FFFF",
     "GIC Distributor Interrupt Set-Enable Register 0 — sets enable for SGIs/PPIs (0-31); "
     "write 1 to enable, read returns current state",
     "GIC-600", "base"),
    ("GICR_WAKER",       "0x0014", 32, "RW", "impl-defined",
     "GIC Redistributor Wake Register — ChildrenAsleep/ProcessorSleep bits; "
     "must be checked before powering down CPU; critical for suspend/resume path",
     "GIC-600-Redistributor", "base"),
    ("GICR_PENDBASER",   "0x0078", 64, "RW", "0x00000000",
     "GIC Redistributor LPI Pending Table Base — physical address of LPI pending table in DRAM; "
     "must be configured before enabling LPIs; size depends on GICD_TYPER.IDbits",
     "GIC-600-Redistributor", "base"),
    ("GITS_BASER0",      "0x0100", 64, "RW", "0x00000000",
     "GIC ITS Translation Table Base Register 0 — Device Table base address and size; "
     "maps DeviceID to interrupt translation table; critical for MSI routing",
     "GIC-600-ITS", "base"),
    ("GITS_CBASER",      "0x0080", 64, "RW", "0x00000000",
     "GIC ITS Command Queue Base — physical address of ITS command ring buffer; "
     "commands: MAPD, MAPC, MAPI, MOVI, INVALL for LPI management",
     "GIC-600-ITS", "base"),
]

# ---------------------------------------------------------------------------
# Registers — SMMUv3
# ---------------------------------------------------------------------------

_SMMU_REGS = [
    ("SMMU_CR0",         "0x0020", 32, "RW", "0x00000000",
     "SMMUv3 Control Register 0 — SMMUEN (enable), EVENTQEN (event queue enable), "
     "CMDQEN (command queue enable), PRIQEN (PRI queue enable)",
     "SMMUv3-TCU", "base"),
    ("SMMU_STRTAB_BASE", "0x0080", 64, "RW", "0x00000000",
     "SMMUv3 Stream Table Base Register — physical address and size of stream table; "
     "supports linear (small) and 2-level (large) formats; RA/LOG2SIZE fields",
     "SMMUv3-Stream-Table", "base"),
    ("SMMU_CMDQ_BASE",   "0x0090", 64, "RW", "0x00000000",
     "SMMUv3 Command Queue Base Register — physical address of CMDQ ring buffer; "
     "LOG2SIZE sets queue size (max 2^19 entries)",
     "SMMUv3-Command-Queue", "base"),
    ("SMMU_EVTQ_BASE",   "0x00A0", 64, "RW", "0x00000000",
     "SMMUv3 Event Queue Base Register — physical address of EVTQ ring buffer; "
     "captures translation faults, permission faults, config errors",
     "SMMUv3-Event-Queue", "base"),
    ("SMMU_GERROR",      "0x0060", 32, "RO", "0x00000000",
     "SMMUv3 Global Error Register — reports catastrophic errors: "
     "CMDQ error, EVTQ overflow, PRIQ overflow, STRTAB error; "
     "sticky bits cleared via SMMU_GERRORN",
     "SMMUv3-TCU", "base"),
]

# ---------------------------------------------------------------------------
# Registers — PMU system registers
# ---------------------------------------------------------------------------

_PMU_REGS = [
    ("PMCR_EL0",         "S3_3_C9_C12_0", 64, "RW", "impl-defined",
     "Performance Monitors Control Register — E (enable), P (event counter reset), "
     "C (cycle counter reset), D (clock divider), N (number of counters); "
     "accessed via perf_event_open() in userspace",
     "linux-perf-arm", "base"),
    ("PMCCNTR_EL0",      "S3_3_C9_C13_0", 64, "RW", "0x0",
     "Performance Monitors Cycle Count Register — counts CPU cycles; "
     "64-bit counter; wraps to 0; overflow triggers IRQ-PMU-* interrupt",
     "linux-perf-arm", "base"),
    ("PMSNEVFR_EL1",     "S3_0_C9_C9_1", 64, "RW", "0x0",
     "SPE Sampling Event Filter Register — controls which events trigger SPE samples; "
     "used to reduce sample rate for specific event types",
     "linux-perf-spe", "base"),
]

# ---------------------------------------------------------------------------
# Registers — Display / DSI
# ---------------------------------------------------------------------------

_DISPLAY_REGS = [
    ("DSI_CMD_PKT_STATUS","impl-offset", 32, "RO", "0x00000000",
     "DSI Command Packet Status — TX FIFO full/empty, RX FIFO empty, "
     "command transmission busy; checked during panel init sequence",
     "MIPI-DSI2-Host", "base"),
    ("DSI_PHY_STATUS",   "impl-offset", 32, "RO", "impl-defined",
     "DSI PHY Status — lane stop state, PHY lock, ULPS active/not-active; "
     "checked during PHY initialization and lane error recovery",
     "MIPI-DSI2-DPHY", "base"),
    ("DISP_OVL_SRC_CON", "impl-offset", 32, "RW", "0x00000000",
     "Display OVL Source Control — enables/disables overlay layers; "
     "each bit enables one input layer; must match DRM plane configuration",
     "display-ovl", "base"),
]

# ---------------------------------------------------------------------------
# Registers — Thermal sensor
# ---------------------------------------------------------------------------

_THERMAL_REGS = [
    ("TSENS_STATUS",     "impl-offset", 32, "RO", "impl-defined",
     "Thermal Sensor Status — current temperature reading (raw ADC value), "
     "valid bit, min/max threshold crossed flags; "
     "conversion: temp_mC = (raw * slope) + offset",
     "tsens-soc", "base"),
    ("TSENS_THRESHOLD_HIGH", "impl-offset", 32, "RW", "0xFFFFFFFF",
     "TSENS High Threshold — triggers high-temperature interrupt when crossed; "
     "must be set before enabling thermal zone polling; "
     "typically set to passive trip point temperature",
     "tsens-soc", "base"),
]

# ---------------------------------------------------------------------------
# Additional Components for undercovered areas
# ---------------------------------------------------------------------------

_EXTRA_COMPONENTS = [
    ("linux-regulator-core",    "framework",  "linux",
     "Linux regulator framework (drivers/regulator/) — manages voltage/current regulators, "
     "constraint enforcement (min/max voltage, modes), consumer/supplier abstraction; "
     "PMIC drivers register regulators; consumers request via regulator_get()/enable()/set_voltage()",
     "base"),
    ("linux-pinctrl",           "framework",  "linux",
     "Linux pin control framework (drivers/pinctrl/) — manages GPIO multiplexing, "
     "pin configuration (pull-up/down, drive strength, schmitt trigger); "
     "device tree pinctrl-0/pinctrl-names properties; critical for BSP bring-up",
     "base"),
    ("linux-reset-controller",  "framework",  "linux",
     "Linux reset controller framework (drivers/reset/) — manages hardware reset lines; "
     "assert/deassert/reset API for IP block resets; "
     "device tree resets property; required for peripheral initialization sequence",
     "base"),
    ("linux-watchdog",          "framework",  "linux",
     "Linux watchdog framework (drivers/watchdog/) — hardware watchdog timer management; "
     "userspace via /dev/watchdog; kernel lockup detector; "
     "pretimeout framework for bark-before-bite behavior",
     "base"),
    ("linux-remoteproc",        "framework",  "linux",
     "Linux remoteproc framework (drivers/remoteproc/) — manages heterogeneous processors "
     "(DSP, MCU, modem); firmware loading, lifecycle management, crash recovery; "
     "sysfs at /sys/class/remoteproc/; rpmsg for inter-processor communication",
     "base"),
    ("linux-rpmsg",             "framework",  "linux",
     "Linux rpmsg framework (drivers/rpmsg/) — inter-processor messaging over shared memory; "
     "name-service announcement, endpoint-based routing; "
     "used for CPU↔DSP, CPU↔MCU, CPU↔modem communication in SoCs",
     "base"),
    ("linux-mailbox",           "framework",  "linux",
     "Linux mailbox framework (drivers/mailbox/) — hardware mailbox controller abstraction; "
     "doorbell interrupts between processors; "
     "ARM MHU (Message Handling Unit), platform-specific implementations",
     "base"),
    ("linux-iio",               "framework",  "linux",
     "Linux IIO (Industrial I/O) framework — ADC, DAC, accelerometer, gyroscope, "
     "magnetometer, light, pressure sensors; provides triggered buffer and event interface; "
     "sysfs at /sys/bus/iio/; used for PMIC ADC and sensor hubs",
     "base"),
    ("linux-nvmem",             "framework",  "linux",
     "Linux nvmem framework (drivers/nvmem/) — non-volatile memory abstraction for "
     "OTP/eFuse, EEPROM, SRAM; provides read-only/read-write cell API; "
     "used for chip ID, calibration data, secure boot keys; sysfs at /sys/bus/nvmem/",
     "base"),
    ("linux-firmware-loader",   "framework",  "linux",
     "Linux firmware loading framework — request_firmware() / request_firmware_nowait(); "
     "loads binary blobs from /lib/firmware/; used for GPU, WiFi, modem, DSP firmware; "
     "supports compressed firmware and firmware fallback paths",
     "base"),
    ("linux-dma-engine",        "framework",  "linux",
     "Linux DMA Engine framework (drivers/dma/) — generic DMA controller abstraction; "
     "async memcpy, slave SG, cyclic transfers; integrates with audio, SPI, UART DMA; "
     "dmaengine_submit()/dma_async_issue_pending() API",
     "base"),
    ("linux-clk-core",          "framework",  "linux",
     "Linux Common Clock Framework core (drivers/clk/clk.c) — "
     "tree-structured clock management; enable/disable reference counting, "
     "rate propagation, re-parenting; clk_prepare_enable()/clk_set_rate() API; "
     "device tree clocks/clock-names properties",
     "base"),
    ("linux-phy-core",          "framework",  "linux",
     "Linux Generic PHY framework (drivers/phy/) — abstracts transceiver hardware; "
     "USB PHY, PCIe PHY, MIPI D-PHY/C-PHY, SATA PHY; "
     "phy_init()/phy_power_on()/phy_set_mode() API; "
     "device tree phys/phy-names properties",
     "base"),
    ("linux-i2c-core",          "framework",  "linux",
     "Linux I2C core framework — I2C bus adapter management, client driver binding; "
     "i2c_transfer()/i2c_smbus_* API; used for PMIC, sensors, codec, panel communication; "
     "device tree i2c-bus node with reg and clock-frequency",
     "base"),
    ("linux-spi-core",          "framework",  "linux",
     "Linux SPI core framework — SPI controller driver and protocol driver abstraction; "
     "spi_sync()/spi_async() API; used for flash, display, sensor communication; "
     "DMA capable for large transfers",
     "base"),
    ("linux-gpio-core",         "framework",  "linux",
     "Linux GPIO core framework (drivers/gpio/) — GPIO descriptor API; "
     "gpiod_get()/gpiod_set_value()/gpiod_direction_*(); "
     "GPIO IRQ support, GPIO character device (/dev/gpiochipN); "
     "device tree gpios property",
     "base"),
    ("linux-pwm-core",          "framework",  "linux",
     "Linux PWM framework (drivers/pwm/) — Pulse Width Modulation controller abstraction; "
     "used for backlight, fan, LED, vibrator control; "
     "pwm_config()/pwm_enable() API; device tree pwms property",
     "base"),
    ("linux-led-core",          "framework",  "linux",
     "Linux LED class framework (drivers/leds/) — LED device abstraction with triggers; "
     "brightness control, blink patterns, hardware LED engines; "
     "sysfs at /sys/class/leds/; used for notification LED, charging indicator",
     "base"),
    ("linux-input-core",        "framework",  "linux",
     "Linux input subsystem (drivers/input/) — unified event interface for keyboards, "
     "touchscreens, buttons, sensors; generates EV_KEY/EV_ABS/EV_REL events; "
     "/dev/input/eventN; evdev protocol; used by Android input HAL",
     "base"),
    ("linux-power-supply",      "framework",  "linux",
     "Linux power supply framework (drivers/power/supply/) — battery, charger, "
     "USB power delivery abstraction; reports capacity, voltage, current, status; "
     "sysfs at /sys/class/power_supply/; uevent notifications for Android",
     "base"),
    ("ARM-MHU",                 "mailbox",    "ARM",
     "ARM Message Handling Unit (MHU) — hardware mailbox controller for inter-processor "
     "communication; doorbell interrupts between application processor and SCP/MCP; "
     "used for SCMI transport; v2 supports multiple channels and bidirectional doorbell",
     "base"),
    ("ARM-SCP",                 "firmware",   "ARM",
     "ARM System Control Processor (SCP) — dedicated management processor on SoC; "
     "handles power management, clock/voltage control, sensor monitoring via SCMI; "
     "runs SCP firmware (open-source SCP-firmware project); communicates via MHU mailbox",
     "base"),
    ("linux-scmi-core",         "framework",  "linux",
     "Linux SCMI framework (drivers/firmware/arm_scmi/) — System Control and Management Interface; "
     "protocol-based communication with SCP: power, performance, clock, sensor, reset protocols; "
     "transport via MHU mailbox, shared memory, or virtio",
     "base"),
    ("ARM-CMN-Watchpoint",      "debug",      "ARM",
     "CMN Watchpoint — hardware transaction watchpoint in CHI mesh interconnect; "
     "triggers on address/opcode/NodeID match; used for bus traffic debugging; "
     "configured via CMN DTC (Debug Trace Controller)",
     "base"),
    ("linux-ftrace",            "framework",  "linux",
     "Linux ftrace framework — function tracer, event tracing, latency analysis; "
     "tracefs at /sys/kernel/tracing/; trace_printk() for kernel driver debugging; "
     "integrates with perf, BPF, and kernel function graph tracing",
     "base"),
    ("linux-kprobes",           "framework",  "linux",
     "Linux kprobes/kretprobes — dynamic kernel function instrumentation; "
     "insert breakpoints at any kernel instruction; used by BPF, systemtap, perf-probe; "
     "critical for BSP driver debugging without rebuilding kernel",
     "base"),
    ("linux-dynamic-debug",     "framework",  "linux",
     "Linux dynamic debug — runtime enable/disable of pr_debug()/dev_dbg() messages per-file, "
     "per-function, or per-line; controlled via /sys/kernel/debug/dynamic_debug/control; "
     "essential for BSP driver bring-up without kernel recompilation",
     "base"),
    ("linux-debugfs",           "framework",  "linux",
     "Linux debugfs — RAM-based filesystem for kernel debug interfaces; "
     "mounted at /sys/kernel/debug/; used by DRM, regmap, clk, PM for internal state dumps; "
     "not present in production CONFIG_DEBUG_FS=n builds",
     "base"),
    ("linux-regmap",            "framework",  "linux",
     "Linux regmap framework (drivers/base/regmap/) — register abstraction for I2C/SPI/MMIO; "
     "caching, read/write wrappers, register field helpers; "
     "debugfs dump of all register values; essential for PMIC, codec, sensor drivers",
     "base"),
    ("linux-devcoredump",       "framework",  "linux",
     "Linux devcoredump framework — captures device crash dumps to /sys/class/devcoredump/; "
     "used by GPU (adreno), WiFi, modem drivers for post-mortem analysis; "
     "dump stored as binary blob, userspace reads and parses",
     "base"),
    ("linux-serdev",            "framework",  "linux",
     "Linux serdev (serial device bus) — model serial-attached peripherals as bus devices; "
     "used for BT/WiFi combo chips, GPS modules; replaces legacy tty-based serial binding; "
     "supports DT binding with compatible string",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    # Register nodes
    all_regs = _GIC_REGS + _SMMU_REGS + _PMU_REGS + _DISPLAY_REGS + _THERMAL_REGS
    for name, address, size_bits, access_type, reset_value, desc, component, ns in all_regs:
        if upsert_node(conn, "Register", {
            "name": name, "address": address, "size_bits": size_bits,
            "access_type": access_type, "reset_value": reset_value,
            "description": desc, "component": component, "namespace": ns,
        }):
            inserted += 1

    # Extra Component nodes
    for name, ctype, vendor, desc, ns in _EXTRA_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Regulator → PMIC
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-regulator-core", dst_name="PMIC-BUCK1")

    # Pinctrl → platform devices
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-pinctrl", dst_name="MIPI-DSI2-Host")

    # Reset controller → IP blocks
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-reset-controller", dst_name="GPU-Controller")

    # Remoteproc → rpmsg → mailbox
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-remoteproc", dst_name="linux-rpmsg")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-rpmsg", dst_name="linux-mailbox")

    # nvmem → OTP fuses
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-nvmem", dst_name="OTP-Fuse-Controller")

    # Firmware loader → remoteproc
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-firmware-loader", dst_name="linux-remoteproc")

    print(f"[arm-registers-key] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
