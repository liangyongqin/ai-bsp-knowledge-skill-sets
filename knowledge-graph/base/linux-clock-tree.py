"""
Linux Common Clock Framework (CCF) — clock tree seed knowledge.

Sources:
  - Linux Documentation/driver-api/clk.rst
  - Linux kernel/drivers/clk/ (CCF core)
  - ARM PrimeCell PL011 / PL022 clock requirements
  - MIPI D-PHY byte clock generation
  - ARM DEN0022D (PSCI) clock gating on CPU power down

Covers ClockSource nodes (PLLs, oscillators, dividers) and
Component nodes (clock consumers, CCF framework, clock drivers).

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
# ClockSource nodes — root oscillators and PLLs
# ---------------------------------------------------------------------------

_CLOCK_SOURCES = [
    # name, frequency_hz, parent_clk, namespace
    # Root oscillators (SoC external input)
    ("OSC-26M",          26_000_000,    "",               "base"),
    ("OSC-32K",          32_768,        "",               "base"),
    ("TCXO-26M",         26_000_000,    "",               "base"),

    # Main PLLs
    ("PLL-ARMPLL-L",     1_800_000_000, "OSC-26M",        "base"),  # LITTLE cluster PLL
    ("PLL-ARMPLL-B",     2_400_000_000, "OSC-26M",        "base"),  # BIG cluster PLL
    ("PLL-ARMPLL-X",     3_000_000_000, "OSC-26M",        "base"),  # Prime core PLL
    ("PLL-MAINPLL",      2_184_000_000, "OSC-26M",        "base"),  # System/bus PLL
    ("PLL-UNIVPLL",      2_496_000_000, "OSC-26M",        "base"),  # Universal (USB/MIPI/Audio)
    ("PLL-MMPLL",        2_750_000_000, "OSC-26M",        "base"),  # Multimedia PLL (ISP/MDP/Disp)
    ("PLL-GPUPLL",       1_000_000_000, "OSC-26M",        "base"),  # GPU PLL
    ("PLL-EMIPLL",       1_600_000_000, "OSC-26M",        "base"),  # EMI/DRAM PLL (LPDDR5)
    ("PLL-TVDPLL",        594_000_000,  "OSC-26M",        "base"),  # Display HDMI/DSI PLL
    ("PLL-NNAPLL",       1_200_000_000, "OSC-26M",        "base"),  # NPU/APU accelerator PLL
    ("PLL-AUDPLL",        196_608_000,  "OSC-26M",        "base"),  # Audio fractional PLL (48kHz×N)
    ("PLL-MSDCPLL",       384_000_000, "OSC-26M",         "base"),  # eMMC/SD card PLL

    # Dividers derived from PLLs
    ("CLK-SYSPLL-D2",    1_092_000_000, "PLL-MAINPLL",    "base"),  # MAINPLL ÷ 2
    ("CLK-SYSPLL-D4",      546_000_000, "PLL-MAINPLL",    "base"),  # MAINPLL ÷ 4
    ("CLK-SYSPLL-D8",      273_000_000, "PLL-MAINPLL",    "base"),  # MAINPLL ÷ 8
    ("CLK-UNIVPLL-D2",   1_248_000_000, "PLL-UNIVPLL",    "base"),  # UNIVPLL ÷ 2
    ("CLK-UNIVPLL-D4",     624_000_000, "PLL-UNIVPLL",    "base"),  # UNIVPLL ÷ 4
    ("CLK-UNIVPLL-D8",     312_000_000, "PLL-UNIVPLL",    "base"),  # UNIVPLL ÷ 8
    ("CLK-MMPLL-D2",     1_375_000_000, "PLL-MMPLL",      "base"),  # MMPLL ÷ 2
    ("CLK-MMPLL-D4",       687_500_000, "PLL-MMPLL",      "base"),  # MMPLL ÷ 4
    ("CLK-EMIPLL-D2",      800_000_000, "PLL-EMIPLL",     "base"),  # EMI PLL ÷ 2 (LPDDR5 byte clock)
    ("CLK-GPUPLL-D2",      500_000_000, "PLL-GPUPLL",     "base"),  # GPU ÷ 2

    # Peripheral clocks
    ("CLK-UART-26M",       26_000_000,  "OSC-26M",        "base"),  # UART baud clock
    ("CLK-I2C-HS",         400_000,     "OSC-26M",        "base"),  # I2C high-speed 400kHz
    ("CLK-SPI-52M",        52_000_000,  "CLK-UNIVPLL-D8", "base"),  # SPI master clock
    ("CLK-USB3-REF",       100_000_000, "PLL-UNIVPLL",    "base"),  # USB3 PIPE/PHY ref clock
    ("CLK-PCIE-AUX",        100_000_000,"PLL-MAINPLL",    "base"),  # PCIe AUX (25MHz ×4)
    ("CLK-CSI-BYTE",        750_000_000,"PLL-MMPLL",      "base"),  # MIPI CSI-2 byte clock (6 Gbps lane ÷ 8)
    ("CLK-ISP-MAIN",        560_000_000,"CLK-MMPLL-D2",   "base"),  # ISP main processing clock
    ("CLK-VENC",            416_000_000,"CLK-MMPLL-D4",   "base"),  # Video encoder clock
    ("CLK-DISP",            273_000_000,"CLK-SYSPLL-D8",  "base"),  # Display controller clock
    ("CLK-AUD-INTBUS",       26_000_000,"PLL-AUDPLL",     "base"),  # Audio interconnect bus clock
    ("CLK-MSDC-HS400",      400_000_000,"PLL-MSDCPLL",    "base"),  # eMMC HS400 clock (400 MHz / 2 = 200 MB/s ×2 DDR)
]

# ---------------------------------------------------------------------------
# Component nodes — CCF framework + clock drivers
# ---------------------------------------------------------------------------

_CLOCK_COMPONENTS = [
    ("linux-ccf-core",      "framework",   "linux", "Linux Common Clock Framework (CCF) — clk_hw, clk_ops, clk_init_data; provider/consumer model", "base"),
    ("linux-clk-mux",       "clk-driver",  "linux", "CCF clock mux driver — selects between parent clocks; implements clk_set_parent()",            "base"),
    ("linux-clk-divider",   "clk-driver",  "linux", "CCF clock divider driver — integer/fractional divider; CLK_DIVIDER_ROUND_CLOSEST",              "base"),
    ("linux-clk-gate",      "clk-driver",  "linux", "CCF clock gate driver — enable/disable via register bit; CLK_IGNORE_UNUSED for always-on clk", "base"),
    ("linux-clk-pll",       "clk-driver",  "linux", "CCF PLL driver — integer/fractional PLL; handles lock polling, min/max rate constraints",       "base"),
    ("linux-clk-composite", "clk-driver",  "linux", "CCF composite clock — mux + gate + divider combined into single clk_hw; common SoC pattern",   "base"),
    ("linux-clkdev",        "framework",   "linux", "Linux clock lookup table (clkdev) — maps device+con_id string to clk_hw; legacy I2C/SPI lookup","base"),
    ("linux-clk-summary",   "debug",       "linux", "Linux /sys/kernel/debug/clk/clk_summary — CCF tree dump: enable count, rate, parent",          "base"),
    ("linux-clk-scmi",      "clk-driver",  "linux", "SCMI clock driver — delegates clk_set_rate to firmware via SCMI protocol (DEN0056)",            "base"),
    ("linux-clk-rpchk",     "clk-driver",  "linux", "RPCh clock driver — rate setting via mailbox to remote processor (typical for modem clocks)",    "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — clock tree
# ---------------------------------------------------------------------------

_CLOCK_FAILURES = [
    ("clk-pll-lock-timeout",
     "Kernel boot hangs after PLL enable; dmesg: 'PLL lock timeout'",
     "PLL KVCO/VCTRL out of range; check PLL input frequency and VCO band selection register",
     "boot",
     "Linux Documentation/driver-api/clk.rst §PLL",
     "base"),
    ("clk-rate-rounding-error",
     "Peripheral baud rate wrong; UART/SPI get wrong baud, data corrupted",
     "CLK_DIVIDER_ROUND_CLOSEST not set; rate rounds down causing -3% frequency error exceeding tolerance",
     "clock",
     "Linux Documentation/driver-api/clk.rst §Rate rounding",
     "base"),
    ("clk-orphan-consumer",
     "Driver probe deferred forever; dmesg: 'clk: orphan clk'",
     "Clock provider registered after consumer; use clk_register() ordering or CCF deferred_clk list",
     "clock",
     "Linux CCF core: kernel/drivers/clk/clk.c __clk_resolve_parents()",
     "base"),
    ("clk-unused-domain-keeps-on",
     "Standby current higher than expected; idle power regression",
     "CLK_IGNORE_UNUSED prevents auto-gating; remove flag after bring-up; use clk_notifier instead",
     "power",
     "Linux Documentation/driver-api/clk.rst §CLK_IGNORE_UNUSED",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    # ClockSource nodes
    for name, freq_hz, parent_clk, ns in _CLOCK_SOURCES:
        if upsert_node(conn, "ClockSource", {
            "name": name, "frequency_hz": freq_hz,
            "parent_clk": parent_clk, "namespace": ns,
        }):
            inserted += 1

    # Component nodes
    for name, ctype, vendor, desc, ns in _CLOCK_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # FailureMode nodes
    for name, symptom, root_cause, affected_domain, source, ns in _CLOCK_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships — clock tree hierarchy (CLOCKS: ClockSource→Component consumer)
    # ---------------------------------------------------------------------------

    # PLL → cluster (CPU uses PLL as clock source)
    _cluster_clocks = [
        ("PLL-ARMPLL-L", "Cortex-A55-Cluster"),
        ("PLL-ARMPLL-B", "Cortex-A76-Cluster"),
        ("PLL-ARMPLL-X", "Cortex-X1-Cluster"),
        ("PLL-GPUPLL",   "ISP-pipeline"),
        ("CLK-ISP-MAIN", "ISP-pipeline"),
        ("CLK-CSI-BYTE", "MIPI-CSI2-RX"),
        ("CLK-MSDC-HS400", "eMMC-host-controller"),
        ("CLK-USB3-REF", "USB3-PHY"),
        ("CLK-PCIE-AUX", "PCIe-RC"),
        ("CLK-EMIPLL-D2","DRAM-controller"),
    ]
    for clk_name, comp_name in _cluster_clocks:
        create_rel(conn, "CLOCKS", "ClockSource", "Component",
                   src_name=clk_name, dst_name=comp_name)

    # CCF framework component relationships
    for driver in ("linux-clk-mux", "linux-clk-divider", "linux-clk-gate",
                   "linux-clk-pll", "linux-clk-composite"):
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
                   src_name=driver, dst_name="linux-ccf-core")

    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="linux-clk-scmi", dst_name="arm-scmi")

    # Failure → root cause component/clock
    _fm_comp_causes = [
        ("clk-pll-lock-timeout",      "linux-clk-pll"),
        ("clk-rate-rounding-error",   "linux-clk-divider"),
        ("clk-orphan-consumer",       "linux-ccf-core"),
        ("clk-unused-domain-keeps-on","linux-clk-gate"),
    ]
    for fm_name, comp_name in _fm_comp_causes:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-clock-tree] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
