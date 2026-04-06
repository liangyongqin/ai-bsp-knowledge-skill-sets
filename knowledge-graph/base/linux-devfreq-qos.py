"""
Linux Devfreq, PM QoS & Interconnect Framework seed — open-source knowledge ingestion.

Adds device frequency scaling, quality-of-service, and interconnect
bandwidth management components used across BSP subsystems.

Sources:
  - Linux kernel Documentation/driver-api/devfreq.rst
  - Linux kernel Documentation/power/pm_qos_interface.rst
  - Linux kernel Documentation/interconnect/interconnect.rst
  - Linux kernel drivers/devfreq/ source code
  - Linux kernel drivers/interconnect/ source code

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
# Components — Devfreq framework
# ---------------------------------------------------------------------------

_DEVFREQ_CORE = [
    ("linux-devfreq-core",      "framework",  "linux",
     "Linux devfreq core (drivers/devfreq/devfreq.c) — generic DVFS framework for "
     "non-CPU devices (GPU, DDR, ISP, DSP); polls utilisation stats via get_dev_status(), "
     "invokes governor to select target frequency; sysfs at /sys/class/devfreq/",
     "base"),
    ("devfreq-gov-simple-ondemand", "governor", "linux",
     "Devfreq simple_ondemand governor — frequency scaling based on utilisation ratio; "
     "if busy% > upthreshold, set max freq; else scale proportionally; "
     "tunables: upthreshold (default 90), downdifferential (default 5)",
     "base"),
    ("devfreq-gov-performance", "governor",   "linux",
     "Devfreq performance governor — always sets maximum frequency; "
     "used for benchmark or low-latency workloads; no power savings",
     "base"),
    ("devfreq-gov-powersave",   "governor",   "linux",
     "Devfreq powersave governor — always sets minimum frequency; "
     "maximum power savings at cost of performance",
     "base"),
    ("devfreq-gov-userspace",   "governor",   "linux",
     "Devfreq userspace governor — frequency controlled from userspace via sysfs; "
     "used for testing and vendor-specific governors (e.g., Android GPU governor)",
     "base"),
    ("devfreq-gov-passive",     "governor",   "linux",
     "Devfreq passive governor — mirrors frequency of a parent devfreq device; "
     "used for coupled devices (e.g., DDR follows CPU frequency); "
     "requires devfreq_passive_data with parent pointer",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Devfreq device drivers
# ---------------------------------------------------------------------------

_DEVFREQ_DRIVERS = [
    ("devfreq-ddr",             "driver",     "linux",
     "DDR devfreq driver — scales LPDDR5/DDR5 frequency via SCMI or direct PLL control; "
     "OPP table defines frequency-voltage pairs; critical for memory bandwidth scaling; "
     "typically uses passive governor coupled to CPU load",
     "base"),
    ("devfreq-gpu",             "driver",     "linux",
     "GPU devfreq driver — scales GPU core frequency based on GPU utilisation; "
     "works alongside GPU-specific power management; "
     "integrates with thermal framework via devfreq-cooling",
     "base"),
    ("devfreq-isp",             "driver",     "linux",
     "ISP devfreq driver — scales image signal processor frequency; "
     "adapts to camera resolution/frame-rate mode; higher modes need higher ISP clock",
     "base"),
    ("devfreq-bus",             "driver",     "linux",
     "Bus/interconnect devfreq driver — scales NoC/bus frequency to match traffic demand; "
     "reduces power when system is lightly loaded; "
     "Qualcomm: devfreq-bw-hwmon; MediaTek: mtk-cci-devfreq",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — PM QoS framework
# ---------------------------------------------------------------------------

_PMQOS = [
    ("linux-pm-qos-core",       "framework",  "linux",
     "Linux PM QoS core (kernel/power/qos.c) — aggregates quality-of-service constraints "
     "from drivers and userspace; types: cpu_dma_latency, freq_qos (min/max), dev_pm_qos; "
     "ensures latency/throughput guarantees across subsystems",
     "base"),
    ("pm-qos-cpu-latency",      "qos",        "linux",
     "CPU DMA latency PM QoS — constrains CPU idle depth (C-state selection); "
     "lower values prevent deep idle states; used by latency-sensitive drivers "
     "(USB, audio, network) to ensure fast interrupt response",
     "base"),
    ("pm-qos-freq",             "qos",        "linux",
     "Frequency QoS (freq_qos) — per-policy min/max frequency constraints; "
     "aggregated across thermal, userspace, and driver requests; "
     "cpufreq and devfreq respect these constraints when setting frequency",
     "base"),
    ("pm-qos-dev",              "qos",        "linux",
     "Device PM QoS — per-device constraints: resume_latency (max acceptable wake time), "
     "latency_tolerance, flags (no_power_off); drivers register via dev_pm_qos_add_request(); "
     "runtime PM checks these before entering low-power states",
     "base"),
    ("pm-qos-interconnect",     "qos",        "linux",
     "Interconnect PM QoS — bandwidth requests for NoC/bus paths; "
     "devices declare required bandwidth via icc_set_bw(); "
     "interconnect framework aggregates and sets NoC frequency",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Interconnect framework
# ---------------------------------------------------------------------------

_INTERCONNECT = [
    ("linux-icc-core",          "framework",  "linux",
     "Linux interconnect core (drivers/interconnect/core.c) — models on-chip bus topology "
     "as a graph of nodes and paths; drivers request bandwidth between endpoints via "
     "icc_set_bw(src, dst, avg_bw, peak_bw); framework aggregates and forwards to NoC driver",
     "base"),
    ("icc-provider-qcom",       "driver",     "linux",
     "Qualcomm interconnect provider — models SDM/SM SoC NoC topology; "
     "BCM (Bus Clock Manager) votes translated to RPMH commands; "
     "paths: apps→DDR, apps→config, GPU→DDR, camera→DDR",
     "base"),
    ("icc-provider-mtk",        "driver",     "linux",
     "MediaTek interconnect provider — models MTK SoC bus topology; "
     "EMI (External Memory Interface) and SMI (SoC Memory Interface) bandwidth control; "
     "paths: CPU→EMI, GPU→EMI, camera→SMI→EMI",
     "base"),
    ("icc-path-ddr",            "interconnect","linux",
     "Interconnect DDR path — aggregated bandwidth request to memory controller; "
     "combines requests from CPU, GPU, camera, display, modem subsystems; "
     "drives DDR devfreq frequency selection",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — OPP (Operating Performance Points)
# ---------------------------------------------------------------------------

_OPP = [
    ("linux-opp-core",          "framework",  "linux",
     "Linux OPP (Operating Performance Points) framework — manages voltage-frequency pairs "
     "for CPU, GPU, and other devices; parses DT opp-table nodes; "
     "provides opp_table to cpufreq, devfreq, and power model consumers",
     "base"),
    ("opp-table-cpu",           "config",     "linux",
     "CPU OPP table — device tree node listing voltage-frequency pairs per CPU cluster; "
     "includes opp-microvolt, opp-microamp, opp-level; "
     "used by cpufreq driver and EAS energy model",
     "base"),
    ("opp-table-gpu",           "config",     "linux",
     "GPU OPP table — voltage-frequency pairs for GPU core; "
     "includes opp-peak-kBps for memory bandwidth at each OPP; "
     "used by GPU devfreq driver and thermal power model",
     "base"),
    ("opp-table-ddr",           "config",     "linux",
     "DDR OPP table — voltage-frequency pairs for memory controller; "
     "defines LPDDR5 data rates (e.g., 6400 MT/s, 4800 MT/s, 3200 MT/s); "
     "used by DDR devfreq driver for bandwidth scaling",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Runtime PM
# ---------------------------------------------------------------------------

_RUNTIME_PM = [
    ("linux-runtime-pm",        "framework",  "linux",
     "Linux Runtime PM framework (drivers/base/power/runtime.c) — per-device power management; "
     "auto-suspend, runtime suspend/resume callbacks; reference counting via pm_runtime_get/put; "
     "enables per-peripheral clock gating and power domain control",
     "base"),
    ("linux-genpd",             "framework",  "linux",
     "Linux Generic Power Domain (genpd) framework — hierarchical power domain management; "
     "groups devices into power domains; domain can be powered off when all devices are suspended; "
     "supports nested domains (e.g., camera domain within multimedia domain)",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_DEVFREQ_FAILURES = [
    ("FM-Devfreq-Gov-Stuck-Min",
     "GPU/DDR stuck at minimum frequency; performance severely degraded; devfreq sysfs shows min_freq",
     "Devfreq governor polling stopped due to device runtime-suspended; "
     "or freq_qos constraint capped max below usable range; "
     "check /sys/class/devfreq/*/governor and min_freq/max_freq",
     "dvfs",
     "Linux Documentation/driver-api/devfreq.rst",
     "base"),
    ("FM-ICC-Bandwidth-Underflow",
     "Memory bandwidth insufficient; DDR utilisation at 100% but frequency not scaling up",
     "Interconnect path bandwidth request too low; device driver not calling icc_set_bw() "
     "with correct peak_bw; or interconnect provider not translating BW to correct DDR OPP",
     "interconnect",
     "Linux Documentation/interconnect/interconnect.rst",
     "base"),
    ("FM-PM-QoS-Latency-Violation",
     "Audio glitches or USB disconnects during screen-off; devices wake too slowly",
     "CPU DMA latency QoS request removed during suspend; deep C-state entry exceeds "
     "device resume latency requirement; add pm_qos_request with appropriate latency",
     "power",
     "Linux Documentation/power/pm_qos_interface.rst",
     "base"),
    ("FM-OPP-Table-DT-Mismatch",
     "cpufreq/devfreq init fails: OPP table not found; frequency scaling disabled",
     "OPP table node missing or not linked to device node in DT; "
     "check operating-points-v2 phandle and opp-table compatible string",
     "dvfs",
     "Linux Documentation/devicetree/bindings/opp/opp-v2.yaml",
     "base"),
    ("FM-Genpd-Race-Condition",
     "Kernel oops in genpd_power_off path; use-after-free in power domain driver",
     "Race between runtime PM put and device driver accessing hardware; "
     "device register access after power domain gated; "
     "add pm_runtime_get_sync() before register access",
     "power",
     "Linux Documentation/power/runtime_pm.rst",
     "base"),
    ("FM-DDR-Devfreq-No-OPP",
     "DDR stuck at boot frequency; devfreq init: no OPP found for DDR device",
     "DDR controller device node missing OPP table or SCMI perf domain not configured; "
     "DDR frequency scaling requires either direct OPP table or SCMI performance protocol",
     "memory",
     "Linux drivers/devfreq/ and Documentation/firmware-guide/arm/scmi.rst",
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
        _DEVFREQ_CORE + _DEVFREQ_DRIVERS + _PMQOS +
        _INTERCONNECT + _OPP + _RUNTIME_PM
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _DEVFREQ_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Devfreq core → governors
    for gov in ("devfreq-gov-simple-ondemand", "devfreq-gov-performance",
                "devfreq-gov-powersave", "devfreq-gov-userspace", "devfreq-gov-passive"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="linux-devfreq-core", dst_name=gov)

    # Devfreq drivers → devfreq core
    for drv in ("devfreq-ddr", "devfreq-gpu", "devfreq-isp", "devfreq-bus"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=drv, dst_name="linux-devfreq-core")

    # DDR devfreq → DDR controller
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-ddr", dst_name="DDR-Controller")

    # GPU devfreq → GPU controller
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-gpu", dst_name="GPU-Controller")

    # ISP devfreq → ISP controller
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-isp", dst_name="ISP-Controller")

    # PM QoS → cpuidle, cpufreq
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pm-qos-cpu-latency", dst_name="cpuidle-arm")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pm-qos-freq", dst_name="cpu-freq-arm")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pm-qos-freq", dst_name="linux-devfreq-core")

    # Interconnect → devfreq DDR
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-icc-core", dst_name="devfreq-bus")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="icc-path-ddr", dst_name="devfreq-ddr")

    # Provider implementations
    for prov in ("icc-provider-qcom", "icc-provider-mtk"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=prov, dst_name="linux-icc-core")

    # OPP tables → consumers
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-opp-core", dst_name="cpu-freq-arm")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-opp-core", dst_name="linux-devfreq-core")

    # Runtime PM → genpd
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-runtime-pm", dst_name="linux-genpd")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-Devfreq-Gov-Stuck-Min",      "linux-devfreq-core"),
        ("FM-ICC-Bandwidth-Underflow",    "linux-icc-core"),
        ("FM-PM-QoS-Latency-Violation",   "pm-qos-cpu-latency"),
        ("FM-OPP-Table-DT-Mismatch",     "linux-opp-core"),
        ("FM-Genpd-Race-Condition",       "linux-genpd"),
        ("FM-DDR-Devfreq-No-OPP",        "devfreq-ddr"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-devfreq-qos] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
