"""
Linux CPUFreq / OPP / EAS — seed knowledge ingestion.

Ingests open-source documented knowledge about Linux CPUFreq OPP model
and Energy Aware Scheduling (EAS) from kernel documentation.

Reference: Linux kernel docs — Documentation/admin-guide/pm/cpufreq.rst,
           Documentation/scheduler/sched-energy.rst,
           ACPI Specification 6.4 section 8.4 (C-states),
           JEDEC JESD79-5 (LPDDR5)
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

_COMPONENTS = [
    ("cpufreq-schedutil", "cpufreq_governor", "Linux schedutil governor: sets frequency from scheduler utilisation signals (PELT)", "base", "Linux", "4.7+"),
    ("cpufreq-performance", "cpufreq_governor", "Linux performance governor: always selects maximum OPP", "base", "Linux", "2.6+"),
    ("cpufreq-powersave", "cpufreq_governor", "Linux powersave governor: always selects minimum OPP", "base", "Linux", "2.6+"),
    ("cpufreq-userspace", "cpufreq_governor", "Linux userspace governor: frequency set by userspace via sysfs", "base", "Linux", "2.6+"),
    ("cpufreq-ondemand", "cpufreq_governor", "Linux ondemand governor: legacy load-based frequency scaling", "base", "Linux", "2.6+"),
    ("cpufreq-conservative", "cpufreq_governor", "Linux conservative governor: gradual step-up/down frequency scaling", "base", "Linux", "2.6+"),
    ("EAS-Energy-Model", "eas_component", "Linux EAS energy model: per-CPU-cluster power cost tables used by the scheduler", "base", "Linux", "5.0+"),
    ("EAS-Task-Placement", "eas_component", "Linux EAS task placement: schedutil + energy model drives find_energy_efficient_cpu()", "base", "Linux", "5.0+"),
    ("EAS-PELT", "eas_component", "Linux PELT (Per-Entity Load Tracking): exponential moving average of CPU utilisation", "base", "Linux", "3.8+"),
    ("EAS-Capacity-Aware-Wakeup", "eas_component", "Linux capacity-aware wakeup: selects idle CPU with spare capacity before boosting", "base", "Linux", "5.0+"),
    ("EAS-Util-Est", "eas_component", "Linux utilisation estimation (util_est): removes sleep-time bias from PELT signal", "base", "Linux", "5.5+"),
    ("PLL-CPU-LITTLE", "pll", "CPU LITTLE cluster PLL, feeds Cortex-A55 cluster, 400 MHz to 1.8 GHz range", "base", "generic", ""),
    ("PLL-CPU-BIG", "pll", "CPU big cluster PLL, feeds Cortex-A76/A78 cluster, 800 MHz to 3.2 GHz range", "base", "generic", ""),
    ("XTAL-26MHz", "crystal_oscillator", "26 MHz crystal reference oscillator, input to all SoC PLLs", "base", "generic", ""),
    ("PLL-GPU", "pll", "GPU PLL, feeds GPU core clock, 200 MHz to 900 MHz range", "base", "generic", ""),
    ("PLL-DDR", "pll", "DDR PLL, feeds LPDDR4/LPDDR5 memory controller", "base", "generic", ""),
    ("PMIC-BUCK1", "voltage_regulator", "PMIC BUCK1 converter: Cortex-A55 LITTLE cluster supply, 0.5 V to 1.05 V", "base", "generic", ""),
    ("PMIC-BUCK2", "voltage_regulator", "PMIC BUCK2 converter: Cortex-A76/A78 big cluster supply, 0.55 V to 1.1 V", "base", "generic", ""),
    ("PMIC-BUCK3", "voltage_regulator", "PMIC BUCK3 converter: GPU supply, 0.5 V to 0.95 V", "base", "generic", ""),
    ("PMIC-BUCK4", "voltage_regulator", "PMIC BUCK4 converter: SoC logic supply (NPU, ISP, DSP)", "base", "generic", ""),
    ("PMIC-LDO1", "ldo_regulator", "PMIC LDO1: always-on 1.8 V supply for IO and clocking", "base", "generic", ""),
    ("cpufreq-core", "linux_subsystem", "Linux CPUFreq core: policy, driver, governor framework", "base", "Linux", "2.6+"),
    ("opp-core", "linux_subsystem", "Linux OPP (Operating Performance Point) core library - drivers/opp/", "base", "Linux", "3.2+"),
    ("regulator-framework", "linux_subsystem", "Linux regulator framework: voltage/current regulator abstraction", "base", "Linux", "2.6+"),
    ("thermal-framework", "linux_subsystem", "Linux thermal framework: thermal zones, cooling devices, governors", "base", "Linux", "3.8+"),
    ("devfreq-core", "linux_subsystem", "Linux devfreq: device DVFS framework for GPU, DDR, ISP", "base", "Linux", "3.4+"),
    ("Cortex-A55-Cluster", "cpu_cluster", "4x Cortex-A55 LITTLE cluster (efficiency cores)", "base", "ARM", ""),
    ("Cortex-A76-Cluster", "cpu_cluster", "3x Cortex-A76 big cluster (performance cores)", "base", "ARM", ""),
    ("Cortex-A78-Cluster", "cpu_cluster", "1x Cortex-A78 prime cluster (highest performance core)", "base", "ARM", ""),
    ("ACPI-C0", "cpu_cstate", "C0: CPU executing (active)", "base", "ACPI", ""),
    ("ACPI-C1", "cpu_cstate", "C1: CPU clock halted, fast wake (ARM WFI)", "base", "ACPI", ""),
    ("ACPI-C1E", "cpu_cstate", "C1E: Enhanced halt, enhanced power savings, min 10 us target residency", "base", "ACPI", ""),
    ("ACPI-C2", "cpu_cstate", "C2: CPU cache flushed, stop grant cycle, min 100 us target residency", "base", "ACPI", ""),
    ("ACPI-C3", "cpu_cstate", "C3: CPU cache invalidated, bus mastering disabled, 400 us residency", "base", "ACPI", ""),
    ("ACPI-C6", "cpu_cstate", "C6: CPU core power gated, L1/L2 cache saved, 600 us residency", "base", "ACPI", ""),
    ("ARM-WFI", "cpu_idle_state", "ARM WFI (Wait-For-Interrupt): clock gating idle, maps to C1", "base", "ARM", ""),
    ("ARM-WFE", "cpu_idle_state", "ARM WFE (Wait-For-Event): standby for event-based wake", "base", "ARM", ""),
    ("ARM-PSCI-CPU_SUSPEND", "cpu_idle_state", "ARM PSCI CPU_SUSPEND: platform-managed deep idle with state retention", "base", "ARM", ""),
    ("ARM-PSCI-SYSTEM_SUSPEND", "system_suspend_state", "ARM PSCI SYSTEM_SUSPEND: full system suspend, DDR self-refresh", "base", "ARM", ""),
]

_LITTLE_OPPS = [(400, 650), (600, 700), (800, 750), (1000, 800), (1200, 850), (1400, 900), (1600, 950), (1800, 1000)]
_BIG_OPPS    = [(800, 700), (1000, 750), (1200, 800), (1400, 825), (1600, 850), (1800, 875), (2000, 900), (2200, 937), (2400, 975), (2600, 1025)]
_PRIME_OPPS  = [(1000, 750), (1400, 800), (1800, 850), (2200, 900), (2600, 962), (3000, 1025), (3200, 1100)]
_GPU_OPPS    = [(200, 600), (400, 680), (600, 750), (750, 820), (900, 900)]

_POWER_DOMAINS = [
    ("PD-CPU-LITTLE", "cpu_power_domain", "Power domain for Cortex-A55 LITTLE cluster", "base", 750.0, 1500.0),
    ("PD-CPU-BIG", "cpu_power_domain", "Power domain for Cortex-A76 big cluster", "base", 850.0, 3000.0),
    ("PD-CPU-PRIME", "cpu_power_domain", "Power domain for Cortex-A78 prime core", "base", 900.0, 2000.0),
    ("PD-GPU", "gpu_power_domain", "Power domain for GPU cluster", "base", 700.0, 2500.0),
    ("PD-NPU", "npu_power_domain", "Power domain for NPU (AI accelerator)", "base", 750.0, 1500.0),
    ("PD-DISPLAY", "display_power_domain", "Power domain for display subsystem", "base", 800.0, 500.0),
    ("PD-ISP", "isp_power_domain", "Power domain for Image Signal Processor", "base", 750.0, 800.0),
    ("PD-DDR", "memory_power_domain", "Power domain for LPDDR5 memory controller", "base", 1100.0, 1200.0),
    ("PD-ALWAYS-ON", "always_on_domain", "Always-on power domain: PMU, boot ROM, security", "base", 750.0, 50.0),
]

_CLOCK_SOURCES = [
    ("clk-a55-0", "cpu_clock", "Cortex-A55 core 0 clock", "base", 1800000000, "PLL-CPU-LITTLE"),
    ("clk-a55-1", "cpu_clock", "Cortex-A55 core 1 clock", "base", 1800000000, "PLL-CPU-LITTLE"),
    ("clk-a55-2", "cpu_clock", "Cortex-A55 core 2 clock", "base", 1800000000, "PLL-CPU-LITTLE"),
    ("clk-a55-3", "cpu_clock", "Cortex-A55 core 3 clock", "base", 1800000000, "PLL-CPU-LITTLE"),
    ("clk-a76-0", "cpu_clock", "Cortex-A76 core 0 clock", "base", 2600000000, "PLL-CPU-BIG"),
    ("clk-a76-1", "cpu_clock", "Cortex-A76 core 1 clock", "base", 2600000000, "PLL-CPU-BIG"),
    ("clk-a76-2", "cpu_clock", "Cortex-A76 core 2 clock", "base", 2600000000, "PLL-CPU-BIG"),
    ("clk-a78-0", "cpu_clock", "Cortex-A78 prime core clock", "base", 3200000000, "PLL-CPU-BIG"),
    ("clk-gpu-core", "gpu_clock", "GPU shader core clock", "base", 900000000, "PLL-GPU"),
    ("clk-ddr", "memory_clock", "LPDDR5 memory controller clock", "base", 3200000000, "PLL-DDR"),
    ("clk-ref-26mhz", "reference_clock", "26 MHz crystal reference clock", "base", 26000000, ""),
]


def ingest(db_path: str = None) -> int:
    """Ingest Linux CPUFreq/OPP/EAS knowledge into the Kuzu database."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = os.path.abspath(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    inserted = 0

    # OPP component nodes
    for freq_mhz, volt_mv in _LITTLE_OPPS:
        name = f"OPP-A55-{freq_mhz}MHz"
        if upsert_node(conn, "Component", {
            "name": name, "type": "opp",
            "description": f"Cortex-A55 OPP: {freq_mhz} MHz @ {volt_mv} mV",
            "namespace": "base", "vendor": "Linux", "version": "opp-v2",
        }):
            inserted += 1

    for freq_mhz, volt_mv in _BIG_OPPS:
        name = f"OPP-A76-{freq_mhz}MHz"
        if upsert_node(conn, "Component", {
            "name": name, "type": "opp",
            "description": f"Cortex-A76 OPP: {freq_mhz} MHz @ {volt_mv} mV",
            "namespace": "base", "vendor": "Linux", "version": "opp-v2",
        }):
            inserted += 1

    for freq_mhz, volt_mv in _PRIME_OPPS:
        name = f"OPP-A78-{freq_mhz}MHz"
        if upsert_node(conn, "Component", {
            "name": name, "type": "opp",
            "description": f"Cortex-A78 OPP: {freq_mhz} MHz @ {volt_mv} mV",
            "namespace": "base", "vendor": "Linux", "version": "opp-v2",
        }):
            inserted += 1

    for freq_mhz, volt_mv in _GPU_OPPS:
        name = f"OPP-GPU-{freq_mhz}MHz"
        if upsert_node(conn, "Component", {
            "name": name, "type": "opp",
            "description": f"GPU OPP: {freq_mhz} MHz @ {volt_mv} mV",
            "namespace": "base", "vendor": "Linux", "version": "opp-v2",
        }):
            inserted += 1

    for name, ctype, desc, ns, vendor, version in _COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "description": desc,
            "namespace": ns, "vendor": vendor, "version": version,
        }):
            inserted += 1

    for name, dtype, desc, ns, vmv, ima in _POWER_DOMAINS:
        if upsert_node(conn, "PowerDomain", {
            "name": name, "type": dtype, "description": desc,
            "namespace": ns, "voltage_mv": vmv, "current_ma": ima,
        }):
            inserted += 1

    for name, ctype, desc, ns, freq, parent in _CLOCK_SOURCES:
        if upsert_node(conn, "ClockSource", {
            "name": name, "type": ctype, "description": desc,
            "namespace": ns, "frequency_hz": freq, "parent_clk": parent,
        }):
            inserted += 1

    # POWERS relationships
    for pd, comp, desc in [
        ("PD-CPU-LITTLE", "Cortex-A55-Cluster", "PMIC-BUCK1 supplies Cortex-A55 LITTLE cluster via PD-CPU-LITTLE"),
        ("PD-CPU-BIG", "Cortex-A76-Cluster", "PMIC-BUCK2 supplies Cortex-A76 big cluster via PD-CPU-BIG"),
        ("PD-CPU-PRIME", "Cortex-A78-Cluster", "PMIC-BUCK2 supplies Cortex-A78 prime cluster via PD-CPU-PRIME"),
        ("PD-GPU", "GPU-AXI-Master", "PMIC-BUCK3 supplies GPU via PD-GPU"),
    ]:
        create_rel(conn, "POWERS", "PowerDomain", "Component", pd, comp, {"description": desc})

    # CLOCKS relationships
    for clk, comp, desc in [
        ("clk-a55-0", "Cortex-A55-Cluster", "CPU core 0 clock feeds Cortex-A55 cluster"),
        ("clk-a76-0", "Cortex-A76-Cluster", "CPU core 0 clock feeds Cortex-A76 cluster"),
        ("clk-a78-0", "Cortex-A78-Cluster", "CPU prime core clock feeds Cortex-A78 cluster"),
        ("clk-gpu-core", "GPU-AXI-Master", "GPU core clock feeds GPU"),
    ]:
        create_rel(conn, "CLOCKS", "ClockSource", "Component", clk, comp, {"description": desc})

    # DEPENDS_ON_CLOCK relationships
    for comp, clk, desc in [
        ("Cortex-A55-Cluster", "clk-a55-0", "Cortex-A55 cluster depends on PLL-CPU-LITTLE derived clock"),
        ("Cortex-A76-Cluster", "clk-a76-0", "Cortex-A76 cluster depends on PLL-CPU-BIG derived clock"),
        ("Cortex-A78-Cluster", "clk-a78-0", "Cortex-A78 cluster depends on PLL-CPU-BIG derived clock"),
        ("cpufreq-schedutil", "clk-a55-0", "schedutil governor controls A55 cluster clock frequency"),
        ("cpufreq-schedutil", "clk-a76-0", "schedutil governor controls A76 cluster clock frequency"),
    ]:
        create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "ClockSource", comp, clk, {"description": desc})

    # SUPPLIES relationships
    for src, dst, vmv, desc in [
        ("PMIC-BUCK1", "Cortex-A55-Cluster", 750.0, "PMIC BUCK1 supplies Cortex-A55 LITTLE cluster"),
        ("PMIC-BUCK2", "Cortex-A76-Cluster", 850.0, "PMIC BUCK2 supplies Cortex-A76 big cluster"),
        ("PMIC-BUCK2", "Cortex-A78-Cluster", 900.0, "PMIC BUCK2 also supplies Cortex-A78 prime core"),
        ("PMIC-BUCK3", "GPU-AXI-Master", 750.0, "PMIC BUCK3 supplies GPU"),
    ]:
        create_rel(conn, "SUPPLIES", "Component", "Component", src, dst,
                   {"voltage_mv": vmv, "description": desc})

    print(f"[linux-dvfs-eas] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db-path", default=None)
    args = p.parse_args()
    ingest(args.db_path)
