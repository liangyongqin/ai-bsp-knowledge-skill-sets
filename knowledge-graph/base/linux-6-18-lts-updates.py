"""
Linux 6.18 LTS — BSP-relevant features (seed knowledge ingestion).

Linux 6.18 was released 2025-11-30 and designated LTS (supported until
Dec 2027). This is the kernel most new BSPs will baseline against in 2026.

Captures BSP-relevant additions:
  - sched_ext hierarchical scheduler foundation (scx_sched struct, kernel 6.16+)
  - Intel P-State Dynamic Efficiency Control (DEC) — HWP without EPP
  - int340x thermal driver: Intel Power Slider (Panther Lake)
  - qcom-tsens: Snapdragon X2 Elite ('Glymur') temperature sensor
  - Renesas RZ/G3E / RZ/G3S thermal driver
  - Step-wise thermal governor: faster cooling-level decrease on falling temp
  - Clearwater Forest E-core server (Intel Idle driver)
  - Airoha EN7581 CPUFreq / thermal

Sources:
  - Linux 6.18 release notes (kernelnewbies.org/Linux_6.18)
  - Phoronix: "Linux 6.18 Power Management Brings Panther Lake Power Slider"
  - Phoronix: "Sched_Ext Boasts CPU Selection Improvements In Linux 6.16"
  - CNX Software: Linux 6.18 LTS release — Arm, RISC-V, MIPS
  - kernel.org Documentation/scheduler/sched-ext.rst
  - kernel.org Documentation/thermal/

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
# Components
# ---------------------------------------------------------------------------

_L618_COMPONENTS = [
    ("linux-sched-ext-hierarchical",  "scheduler",    "linux",
     "Linux sched_ext hierarchical scheduler foundation (kernel 6.16+, "
     "matured in 6.18 LTS) — struct scx_sched encapsulates per-instance "
     "scheduler state to prepare for multiple hierarchical schedulers; "
     "BPF-based pluggable scheduler; Meta / Google production deployments; "
     "relevant to BSP for custom power-aware scheduling policies on "
     "heterogeneous (little / big / prime) clusters",
     "base"),
    ("linux-scx-cpu-selection",       "scheduler",    "linux",
     "sched_ext CPU selection improvements (kernel 6.16+) — better "
     "CPU-topology awareness in BPF scheduler select_cpu hook; allowed-cpus "
     "mask supports per-task affinity; reduces cross-cluster migration cost "
     "on DynamIQ / Neoverse DSU layouts; verify via bpftool prog show "
     "name scx_select_cpu",
     "base"),
    ("linux-int340x-power-slider",    "thermal-driver", "linux",
     "Linux int340x thermal driver — Intel Power Slider feature (kernel 6.18); "
     "exposes DPTF-backed performance-vs-efficiency slider for Panther Lake "
     "and later Intel laptops; sysfs: /sys/class/thermal/thermal_zone*/; "
     "out-of-scope for ARM-based BSPs but conceptually mirrors Qualcomm "
     "perf-mode sysfs",
     "base"),
    ("linux-qcom-tsens-glymur",       "thermal-driver", "linux",
     "Linux qcom-tsens driver — Snapdragon X2 Elite (codename 'Glymur') "
     "temperature sensor support (kernel 6.18); 18 thermal zones on the "
     "SoC; Linux thermal framework reads via regmap-based tsens-common.c; "
     "compatible string: 'qcom,glymur-tsens'; ARM64 BSP reference for "
     "Qualcomm compute platforms",
     "base"),
    ("linux-renesas-rzg3-thermal",    "thermal-driver", "linux",
     "Linux Renesas RZ/G3E and RZ/G3S thermal driver (kernel 6.18) — new "
     "driver rcar-gen4-thermal extended for RZ/G3 family; 2 TSC (Thermal "
     "Sensor Controller) instances per SoC; feeds Linux thermal framework; "
     "relevant for industrial / automotive BSPs on Renesas ARM platforms",
     "base"),
    ("linux-step-wise-faster-cool",   "thermal-governor", "linux",
     "Linux step-wise thermal governor update (kernel 6.18) — now reduces "
     "cooling level earlier when thermal zone temperature is dropping "
     "(previously waited for sustained drop); reduces CPU-freq clamp "
     "duration by ~15% on bursty workloads; no sysfs API change; verify "
     "via /sys/class/thermal/thermal_zone*/policy = step_wise",
     "base"),
    ("linux-intel-pstate-dec",        "cpufreq-driver", "linux",
     "Linux intel_pstate Dynamic Efficiency Control (DEC) (kernel 6.18) — "
     "allows HWP (Hardware P-States) without EPP (Energy Performance "
     "Preference) when DEC is present in hardware; lets HW P-unit manage "
     "efficiency autonomously; Intel-only; conceptually analogous to ARM "
     "ACPM-firmware-managed DVFS",
     "base"),
    ("linux-airoha-en7581-cpufreq",   "cpufreq-driver", "linux",
     "Linux airoha-cpufreq driver (kernel 6.14+) — supports Airoha EN7581 "
     "SoC CPU frequency via SMC (Secure Monitor Call) APIs to TF-A; "
     "ARM-based SoC for networking appliances; driver uses generic OPP "
     "tables and SCMI-like interface",
     "base"),
    ("linux-intel-idle-cwf",          "cpuidle-driver", "linux",
     "Linux intel_idle driver — Clearwater Forest (CWF) E-core server "
     "support (kernel 6.14+); adds new C-state definitions; not directly "
     "relevant to mobile BSPs but documents the pattern for "
     "server-class C-state tables",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes — BSP-relevant regressions on Linux 6.18 baseline
# ---------------------------------------------------------------------------

_L618_FAILURES = [
    ("FM-SchedExt-BPF-Watchdog-Panic",
     "kernel panic: 'sched_ext: BPF scheduler watchdog timeout; ejecting scx_sched and reverting to CFS'",
     "BPF sched_ext scheduler stalled (no dispatch for SCX_WATCHDOG_MAX_TIMEOUT); "
     "common causes: BPF program bug (infinite loop in select_cpu), priority "
     "inversion with kthread, or locked-out CPU from hotplug event; kernel "
     "auto-ejects scx_sched and falls back to CFS; collect BPF prog dump via "
     "bpftool; disable scx via /sys/kernel/sched_ext/ops while triaging",
     "scheduler",
     "Linux Documentation/scheduler/sched-ext.rst",
     "base"),
    ("FM-Glymur-TSENS-Calibration-Skew",
     "Snapdragon X2 Elite reports thermal zone temperature 15-20°C higher than IR-camera-measured die temp",
     "qcom-tsens on Glymur uses per-sensor calibration fuses; if fuse-blow "
     "during manufacturing was incomplete or the bootloader did not propagate "
     "calibration data to the Linux driver, TSENS readings are raw counts "
     "instead of compensated degrees Celsius; check device-tree nvmem-cells "
     "property for tsens calibration; compare MR4-style telemetry if present",
     "thermal",
     "Linux drivers/thermal/qcom/tsens.c; device-tree nvmem-cells binding",
     "base"),
    ("FM-Step-Wise-Governor-Overcool",
     "After 6.18 upgrade, CPU clamp drops earlier but frame-rate re-dips under sustained heavy load",
     "Step-wise governor now decrements cooling level earlier; if thermal "
     "zone trip-point hysteresis is too narrow (<2°C), governor oscillates "
     "between cooling levels; symptom is frame-rate judder despite overall "
     "cooler operation; widen trip-point hysteresis in device-tree thermal "
     "zones to 3-5°C for bursty workloads",
     "thermal",
     "Linux Documentation/thermal/sysfs-api.rst; drivers/thermal/gov_step_wise.c",
     "base"),
    ("FM-SchedExt-AllowedCPUs-NUMA-Miss",
     "BPF scheduler places tasks on wrong cluster after 6.18 upgrade; perf regression on big.LITTLE",
     "sched_ext CPU selection with allowed_cpus mask did not encode cluster "
     "topology correctly; prime/big/little heterogeneity requires the BPF "
     "scheduler to query topology via bpf_cpumask_* helpers and read "
     "cpu_capacity_orig; audit BPF prog for per-task energy-model awareness; "
     "compare against in-tree scx_rusty or scx_lavd reference implementations",
     "scheduler",
     "Linux tools/sched_ext/; Documentation/scheduler/sched-ext.rst",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    for name, ctype, vendor, desc, ns in _L618_COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _L618_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # scx internals
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-scx-cpu-selection", dst_name="linux-sched-ext-hierarchical")

    # Link to pre-existing scheduler / thermal components where possible
    for drv in ("linux-int340x-power-slider", "linux-qcom-tsens-glymur",
                "linux-renesas-rzg3-thermal", "linux-step-wise-faster-cool"):
        create_rel(conn, "SHARED_WITH", "Component", "Component",
                   src_name=drv, dst_name="linux-thermal-core")

    # CPUFreq drivers share the generic cpufreq core if present
    for drv in ("linux-intel-pstate-dec", "linux-airoha-en7581-cpufreq"):
        create_rel(conn, "SHARED_WITH", "Component", "Component",
                   src_name=drv, dst_name="linux-cpufreq-core")

    # Failure modes → components
    for fm_name, comp_name in [
        ("FM-SchedExt-BPF-Watchdog-Panic",     "linux-sched-ext-hierarchical"),
        ("FM-Glymur-TSENS-Calibration-Skew",   "linux-qcom-tsens-glymur"),
        ("FM-Step-Wise-Governor-Overcool",     "linux-step-wise-faster-cool"),
        ("FM-SchedExt-AllowedCPUs-NUMA-Miss",  "linux-scx-cpu-selection"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[linux-6-18-lts-updates] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
