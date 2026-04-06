"""
Linux Thermal Framework seed — open-source knowledge ingestion.

Adds thermal management subsystem components: thermal zones, governors,
cooling devices, sensor drivers, and the DTPM (Dynamic Thermal Power
Management) framework.

Sources:
  - Linux kernel Documentation/driver-api/thermal/sysfs-api.rst
  - Linux kernel Documentation/driver-api/thermal/power_allocator.rst
  - Linux kernel drivers/thermal/ source code
  - Linux kernel Documentation/power/powercap/dtpm.rst
  - Linaro Connect SAN19-101: Thermal Governors presentation
  - Linux kernel 6.13 release notes (thermal user thresholds, PCIe cooling)

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
# Components — Thermal core framework
# ---------------------------------------------------------------------------

_THERMAL_CORE = [
    ("linux-thermal-core",       "framework",  "linux",
     "Linux thermal core (drivers/thermal/thermal_core.c) — "
     "registers thermal zones, binds cooling devices to trip points, "
     "polls temperature sensors, invokes governor callbacks; "
     "sysfs interface at /sys/class/thermal/",
     "base"),
    ("thermal-zone-cpu",         "thermal",    "linux",
     "CPU thermal zone — aggregates temperature from on-die CPU thermal sensors, "
     "typically one zone per cluster or per-core; trip points: passive (throttle), "
     "critical (shutdown), hot (warning)",
     "base"),
    ("thermal-zone-gpu",         "thermal",    "linux",
     "GPU thermal zone — monitors GPU die temperature, "
     "binds to GPU devfreq cooling device for frequency throttling",
     "base"),
    ("thermal-zone-battery",     "thermal",    "linux",
     "Battery thermal zone — monitors battery pack temperature via ADC/NTC, "
     "critical trip triggers charging current reduction or system shutdown",
     "base"),
    ("thermal-zone-skin",        "thermal",    "linux",
     "Skin thermal zone — virtual zone estimating device surface temperature "
     "from weighted combination of internal sensors; used for user-comfort throttling",
     "base"),
    ("thermal-zone-modem",       "thermal",    "linux",
     "Modem thermal zone — monitors cellular modem temperature, "
     "cooling action reduces TX power or disables carrier aggregation",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Thermal governors
# ---------------------------------------------------------------------------

_GOVERNORS = [
    ("gov-step-wise",            "governor",   "linux",
     "Step-wise thermal governor — open-loop, threshold+trend based; "
     "increments/decrements cooling state one step per polling interval; "
     "default governor for most thermal zones; simple but can oscillate",
     "base"),
    ("gov-power-allocator",      "governor",   "linux",
     "Power allocator thermal governor — closed-loop PID controller; "
     "output is power budget distributed across power actors (CPU, GPU); "
     "requires cooling devices to implement get_requested_power()/state2power(); "
     "tunables: k_po, k_pu, k_i, k_d, sustainable_power",
     "base"),
    ("gov-bang-bang",             "governor",   "linux",
     "Bang-bang thermal governor — binary on/off control with hysteresis; "
     "designed for fans that cannot be partially throttled; "
     "cooling activated at trip_temp, deactivated at trip_temp - hysteresis",
     "base"),
    ("gov-user-space",           "governor",   "linux",
     "User-space thermal governor — delegates thermal policy to userspace daemon "
     "via /sys/class/thermal/thermal_zoneN/temp and uevent notifications; "
     "Android thermal-engine and vendor thermal HALs use this",
     "base"),
    ("gov-fair-share",           "governor",   "linux",
     "Fair-share thermal governor — distributes cooling across all bound devices "
     "proportionally based on weight; suitable for multiple heterogeneous coolers",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Cooling devices
# ---------------------------------------------------------------------------

_COOLING_DEVICES = [
    ("cpufreq-cooling",          "cooling",    "linux",
     "CPUFreq cooling device — limits CPU max frequency via freq_qos; "
     "registered per cpufreq policy (per-cluster); implements power model "
     "for power_allocator governor (dynamic_power = C*V^2*f)",
     "base"),
    ("devfreq-cooling",          "cooling",    "linux",
     "Devfreq cooling device — limits device max frequency via devfreq QoS; "
     "used for GPU, DDR, ISP; provides power model for power_allocator",
     "base"),
    ("thermal-fan-cooling",      "cooling",    "linux",
     "Fan cooling device — GPIO or PWM controlled fan; "
     "cooling states map to fan speed (RPM); typically bound via bang-bang governor",
     "base"),
    ("pcie-cooling",             "cooling",    "linux",
     "PCIe bandwidth cooling device (Linux 6.13+) — limits PCIe link speed "
     "to reduce power dissipation during thermal events; "
     "drivers/thermal/pcie_cooling.c",
     "base"),
    ("thermal-idle-cooling",     "cooling",    "linux",
     "Thermal idle injection cooling — forces CPU idle periods to reduce power; "
     "injects idle cycles via play_idle_precise(); less aggressive than freq clipping",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Thermal sensors / drivers
# ---------------------------------------------------------------------------

_SENSOR_DRIVERS = [
    ("tsens-soc",                "sensor",     "linux",
     "SoC TSENS (Thermal Sensor) driver — on-die temperature ADC, "
     "typically 10+ sensors spread across CPU/GPU/modem/memory regions; "
     "Qualcomm: drivers/thermal/qcom/tsens-v2.c; MediaTek: drivers/thermal/mediatek/",
     "base"),
    ("virtual-thermal-sensor",   "sensor",     "linux",
     "Virtual thermal sensor — software-computed temperature from weighted average "
     "of multiple physical sensors; used for skin temperature estimation; "
     "configured via DT thermal-sensor-cells",
     "base"),
    ("pmic-thermal",             "sensor",     "linux",
     "PMIC thermal sensor — on-PMIC die temperature measurement, "
     "monitors PMIC junction temperature; critical trip triggers PMIC shutdown",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — DTPM framework (Linux 6.x)
# ---------------------------------------------------------------------------

_DTPM = [
    ("linux-dtpm",               "framework",  "linux",
     "Dynamic Thermal Power Management (DTPM) framework — "
     "hierarchical power cap allocation across CPU, GPU, and subsystems; "
     "integrates with powercap sysfs; enables power-constrained scheduling",
     "base"),
    ("linux-powercap",           "framework",  "linux",
     "Linux powercap framework (drivers/powercap/) — "
     "sysfs interface for power zone constraints; DTPM zones represent "
     "CPU/GPU power budgets; Intel RAPL also uses powercap",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Thermal user thresholds (Linux 6.13)
# ---------------------------------------------------------------------------

_THERMAL_THRESHOLDS = [
    ("thermal-user-threshold",   "framework",  "linux",
     "Thermal user thresholds (Linux 6.13+) — userspace can register temperature thresholds "
     "and receive uevent notification when crossed; decoupled from governor trip points; "
     "enables Android thermal HAL to react at custom temperature levels",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_THERMAL_INTERRUPTS = [
    ("IRQ-TSENS-CPU-HIGH",   "SPI", 250, "level-high", "base"),
    ("IRQ-TSENS-CPU-LOW",    "SPI", 251, "level-high", "base"),
    ("IRQ-TSENS-GPU",        "SPI", 252, "level-high", "base"),
    ("IRQ-TSENS-CRITICAL",   "SPI", 253, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_THERMAL_FAILURES = [
    ("FM-Thermal-Governor-Mismatch",
     "CPU frequency oscillates between max and throttled; poor sustained performance",
     "Step-wise governor used on power-constrained device instead of power_allocator; "
     "step-wise cannot balance power budget across CPU+GPU; switch to IPA (power_allocator)",
     "thermal",
     "Linaro Connect SAN19-101: Thermal Governors",
     "base"),
    ("FM-Power-Model-Uncalibrated",
     "Power allocator governor overshoots or undershoots; thermal violation or excess throttling",
     "Cooling device power model coefficients (dynamic_power_coefficient, static_power) "
     "not calibrated for actual silicon; EAS energy model and thermal power model diverge",
     "thermal",
     "Linux Documentation/driver-api/thermal/power_allocator.rst",
     "base"),
    ("FM-TSENS-Read-Timeout",
     "Thermal zone shows -EINVAL or stale temperature; governor stops throttling",
     "TSENS ADC conversion timeout due to sensor clock gated or power domain off; "
     "ensure thermal sensor clock and power are on before reading",
     "thermal",
     "Linux drivers/thermal/qcom/tsens-v2.c",
     "base"),
    ("FM-Thermal-Trip-Misconfigured",
     "System shuts down at 80°C instead of expected 95°C; or overheats without throttling",
     "DT thermal trip points set incorrectly; critical/passive thresholds swapped or "
     "wrong temperature units (millidegrees vs degrees)",
     "thermal",
     "Linux Documentation/devicetree/bindings/thermal/thermal-zones.yaml",
     "base"),
    ("FM-Skin-Temp-Estimation-Drift",
     "Device feels hot to touch but thermal framework shows low temperature",
     "Virtual skin sensor weights not tuned for device form factor; internal sensors "
     "do not reflect surface temperature accurately; needs empirical calibration",
     "thermal",
     "Android Thermal HAL documentation",
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
        _THERMAL_CORE + _GOVERNORS + _COOLING_DEVICES +
        _SENSOR_DRIVERS + _DTPM + _THERMAL_THRESHOLDS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _THERMAL_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _THERMAL_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Thermal zones → thermal core
    for tz in ("thermal-zone-cpu", "thermal-zone-gpu", "thermal-zone-battery",
               "thermal-zone-skin", "thermal-zone-modem"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=tz, dst_name="linux-thermal-core")

    # Governors → thermal core
    for gov in ("gov-step-wise", "gov-power-allocator", "gov-bang-bang",
                "gov-user-space", "gov-fair-share"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="linux-thermal-core", dst_name=gov)

    # Cooling devices → thermal core
    for cd in ("cpufreq-cooling", "devfreq-cooling", "thermal-fan-cooling",
               "pcie-cooling", "thermal-idle-cooling"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="linux-thermal-core", dst_name=cd)

    # CPUFreq cooling → cpufreq driver
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="cpufreq-cooling", dst_name="cpu-freq-arm")

    # Devfreq cooling → GPU (existing node from gpu-subsystem)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="devfreq-cooling", dst_name="GPU-Controller")

    # Sensors → thermal zones
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="tsens-soc", dst_name="thermal-zone-cpu")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="tsens-soc", dst_name="thermal-zone-gpu")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="virtual-thermal-sensor", dst_name="thermal-zone-skin")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="pmic-thermal", dst_name="thermal-zone-battery")

    # DTPM → powercap
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-dtpm", dst_name="linux-powercap")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-dtpm", dst_name="cpufreq-cooling")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-dtpm", dst_name="devfreq-cooling")

    # User thresholds → thermal core
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="thermal-user-threshold", dst_name="linux-thermal-core")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-Thermal-Governor-Mismatch",      "gov-step-wise"),
        ("FM-Power-Model-Uncalibrated",       "gov-power-allocator"),
        ("FM-TSENS-Read-Timeout",             "tsens-soc"),
        ("FM-Thermal-Trip-Misconfigured",     "linux-thermal-core"),
        ("FM-Skin-Temp-Estimation-Drift",     "virtual-thermal-sensor"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-thermal-framework] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
