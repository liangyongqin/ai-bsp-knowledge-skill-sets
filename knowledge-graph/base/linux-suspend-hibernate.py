"""
Linux STR / STD — Suspend-to-RAM and Suspend-to-Disk seed knowledge ingestion.

Ingests open-source documented knowledge about Linux system suspend (STR / S2R)
and hibernation (STD / S4) from Linux kernel documentation and ARM PSCI spec.

References:
  Linux kernel — Documentation/power/states.rst
  Linux kernel — Documentation/power/suspend-and-cpuhotplug.rst
  Linux kernel — Documentation/driver-api/pm/ (dev_pm_ops callbacks)
  Linux kernel — Documentation/power/hibernation.rst
  Linux kernel — kernel/power/suspend.c, kernel/power/hibernate.c
  ARM PSCI spec — DEN0022D (PSCI 1.1): PSCI_SYSTEM_SUSPEND, CPU_SUSPEND
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

# ---------------------------------------------------------------------------
# Component nodes — Linux PM framework subsystems
# ---------------------------------------------------------------------------

_COMPONENTS = [
    # Linux PM core framework
    ("linux-pm-core",
     "pm_subsystem",
     "Linux PM core: top-level system sleep entry point (kernel/power/main.c, "
     "Documentation/power/states.rst). Manages state machine: ON → FREEZE → "
     "SUSPEND/HIBERNATE → OFF/RESUME.",
     "base", "Linux", "2.6+"),

    ("linux-pm-suspend",
     "pm_subsystem",
     "Linux system suspend driver (kernel/power/suspend.c). Implements the "
     "suspend-to-RAM (STR / S2R) path: freeze tasks → suspend devices → "
     "enter platform_suspend_ops → resume devices → thaw tasks. "
     "Ref: Documentation/power/states.rst §3 (suspend-to-ram).",
     "base", "Linux", "2.6+"),

    ("linux-pm-hibernate",
     "pm_subsystem",
     "Linux hibernation driver (kernel/power/hibernate.c). Implements "
     "suspend-to-disk (STD / S4 / S2D) path: freeze tasks → create memory "
     "snapshot (swsusp) → write image to swap → power off. On resume: "
     "bootloader hands off → kernel restores image. "
     "Ref: Documentation/power/hibernation.rst.",
     "base", "Linux", "3.0+"),

    ("linux-pm-runtime",
     "pm_subsystem",
     "Linux runtime PM (drivers/base/power/runtime.c). Per-device idle/active "
     "management independent of system sleep. Drivers call "
     "pm_runtime_get/put; framework calls runtime_suspend/runtime_resume "
     "callbacks from dev_pm_ops. Ref: Documentation/driver-api/pm/devices.rst.",
     "base", "Linux", "2.6.32+"),

    ("linux-pm-wakeup",
     "pm_subsystem",
     "Linux wakeup source framework (drivers/base/power/wakeup.c). Tracks "
     "active wakeup sources to block or abort system suspend. Exported via "
     "/sys/kernel/debug/wakeup_sources and /sys/power/pm_wakeup_irq. "
     "A single active wakeup_source prevents STR entry.",
     "base", "Linux", "3.1+"),

    ("linux-pm-freezer",
     "pm_subsystem",
     "Linux task freezer (kernel/freezer.c). Before system suspend or "
     "hibernation, all user-space tasks and kernel threads marked PF_NOFREEZE "
     "must be frozen. Failure to freeze a kernel thread aborts the suspend "
     "sequence. Ref: Documentation/power/freezing-of-tasks.rst.",
     "base", "Linux", "2.6+"),

    ("linux-swsusp",
     "pm_subsystem",
     "Linux Software Suspend snapshot engine (kernel/power/snapshot.c, "
     "swap.c). For STD: creates a memory image (hibernate image), writes it "
     "to swap partition or swap file, then the system powers off. Image size "
     "is typically 50% of RAM. Requires sufficient swap space.",
     "base", "Linux", "2.6.11+"),

    ("dev-pm-ops",
     "pm_interface",
     "struct dev_pm_ops — per-driver PM callback table "
     "(include/linux/pm.h). Callbacks used by Linux PM framework:\n"
     "  STR path:  .prepare → .suspend → .suspend_late → .suspend_noirq\n"
     "             (resume) .resume_noirq → .resume_early → .resume → .complete\n"
     "  STD path:  .prepare → .freeze → .freeze_late → .freeze_noirq\n"
     "             (thaw)  .thaw_noirq → .thaw_early → .thaw → .complete\n"
     "             (power off) .poweroff → .poweroff_late → .poweroff_noirq\n"
     "             (restore) .restore_noirq → .restore_early → .restore → .complete\n"
     "Ref: Documentation/driver-api/pm/devices.rst.",
     "base", "Linux", "2.6.29+"),

    ("linux-genpd",
     "pm_subsystem",
     "Linux Generic PM Domains (drivers/base/power/domain.c). Manages "
     "hardware power domains (e.g. CPU cluster, GPU, ISP). On system suspend "
     "all devices in a domain are suspended before the domain is powered off. "
     "Platform-specific SPM (MTK) or RPMH (Qualcomm) implement the actual "
     "power-off sequence. Ref: Documentation/driver-api/pm/devices.rst §genpd.",
     "base", "Linux", "3.1+"),

    ("linux-platform-suspend-ops",
     "pm_interface",
     "struct platform_suspend_ops — platform-level STR hooks "
     "(include/linux/suspend.h). .valid(), .begin(), .prepare(), .enter(), "
     ".wake(), .finish(), .end(). The .enter() callback invokes PSCI "
     "SYSTEM_SUSPEND on ARM platforms to hand off to firmware for DDR "
     "self-refresh and rail sequencing.",
     "base", "Linux", "2.6+"),

    # ARM PSCI firmware interface
    ("PSCI-SYSTEM_SUSPEND",
     "firmware_interface",
     "ARM PSCI SYSTEM_SUSPEND (function ID 0x8400_000E, DEN0022D §5.16). "
     "Called by Linux platform_suspend_ops.enter() to hand control to firmware. "
     "Firmware sequences: DDR → self-refresh, peripheral rails → off, "
     "CPU cluster → power-gated. On wakeup: IRQ asserted → firmware restores "
     "rails → releases CPU reset → Linux resumes from WFI.",
     "base", "ARM", "PSCI-1.0+"),

    ("PSCI-CPU_SUSPEND",
     "firmware_interface",
     "ARM PSCI CPU_SUSPEND (function ID 0xC400_0001, DEN0022D §5.4). "
     "Used for per-CPU and per-cluster idle (C-states). Power-state parameter "
     "encodes retention vs power-down and the deepest affected power level. "
     "Distinct from SYSTEM_SUSPEND which suspends the entire platform.",
     "base", "ARM", "PSCI-0.2+"),

    # Hibernation-specific: bootloader resume
    ("bootloader-hibernate-resume",
     "boot_component",
     "Bootloader hibernation image detection. On power-on after STD, bootloader "
     "checks for 'resume=' kernel cmdline or UEFI hibernate variable. If found, "
     "loads hibernation kernel and passes control for image restore. "
     "U-Boot: 'bootm' with hibernate environment. "
     "UEFI: EFI_ACPI_6_4_FIRMWARE_WAKING_VECTOR.",
     "base", "generic", ""),
]

# ---------------------------------------------------------------------------
# Power domain nodes — system-level sleep states
# ---------------------------------------------------------------------------

_POWER_DOMAINS = [
    ("PD-SYSTEM-STR",
     "system_sleep_domain",
     "System sleep state for STR (Suspend-to-RAM / S2R). DDR remains in "
     "self-refresh; CPU, GPU, ISP, NPU power domains are off. Minimum leakage "
     "state while preserving memory contents. Wakeup via GPIO/IRQ restores "
     "all powered-off domains before resuming Linux.",
     "base", 1100.0, 0.0),

    ("PD-SYSTEM-STD",
     "system_sleep_domain",
     "System sleep state for STD (Suspend-to-Disk / Hibernation / S4). All "
     "power rails off including DDR. Memory contents saved to swap storage "
     "before power-off. Resume requires full cold-boot sequence plus "
     "hibernation image restore from swap. Not applicable to Android targets.",
     "base", 0.0, 0.0),
]

# ---------------------------------------------------------------------------
# Failure mode nodes — STR
# ---------------------------------------------------------------------------

_STR_FAILURES = [
    ("STR-blocked-by-wakeup-source",
     "STR entry fails; /sys/power/state returns -EBUSY",
     "Active wakeup_source blocking suspend. Common offenders: partial wake "
     "lock held by userspace (via /sys/power/wake_lock), unprocessed IRQ "
     "pending, driver calling __pm_stay_awake() without matching release. "
     "Debug: cat /sys/kernel/debug/wakeup_sources | sort -rn -k10 | head",
     "power",
     "linux-pm-wakeup",
     "base"),

    ("STR-resume-hang-driver-fail",
     "System enters STR successfully but hangs during resume; serial console "
     "freezes at driver name",
     "A driver's .resume() or .resume_early() callback deadlocks or panics. "
     "Often caused by: IRQ not re-enabled before driver accesses hardware, "
     "clock/regulator not yet available at resume time, incorrect resume order "
     "in PM domain dependency chain. "
     "Debug: add 'no_console_suspend' to kernel cmdline; check last driver "
     "printed before hang; use initcall_debug to trace resume sequence.",
     "power",
     "dev-pm-ops",
     "base"),

    ("STR-wakeup-latency-regression",
     "STR resume takes significantly longer than baseline (>500 ms delta)",
     "Regression in resume latency. Root causes: driver added slow .resume() "
     "operation (firmware download, calibration); PM domain dependency chain "
     "lengthened; DDR frequency not restored to max before CPU-intensive "
     "resume code runs; thermal condition forces reduced OPP on resume. "
     "Debug: enable PM_DEBUG, parse ftrace power:suspend_resume events for "
     "per-driver resume timing.",
     "power",
     "linux-pm-suspend",
     "base"),

    ("STR-power-rail-not-restored",
     "Device fails after STR resume; dmesg shows regulator errors or "
     "undefined register reads",
     "PMIC rail sequencing error on resume: a peripheral rail is not restored "
     "before its driver's .resume() runs. Can also be caused by PSCI firmware "
     "bug leaving a rail off. "
     "Debug: compare PMIC register dump pre-suspend vs post-resume; "
     "check platform_suspend_ops .wake() and .finish() for rail restore order.",
     "power",
     "PSCI-SYSTEM_SUSPEND",
     "base"),

    ("STR-lost-wakeup-irq",
     "STR succeeds but system does not wake on expected IRQ; stuck in sleep",
     "Wakeup IRQ fires in the window between wakeup_source deactivation and "
     "WFI entry, and the edge is lost. Also caused by: GIC wakeup routing not "
     "configured (irq_set_irq_wake() not called), PMIC wakeup pin polarity "
     "misconfigured, firmware not forwarding wakeup event to AP cluster. "
     "Debug: check /sys/power/pm_wakeup_irq after failed wakeup attempt; "
     "enable GIC debug registers to verify IRQ pending state.",
     "power",
     "linux-pm-wakeup",
     "base"),

    ("STR-kernel-thread-not-freezable",
     "STR aborted with 'Freezing of tasks failed' in dmesg",
     "A kernel thread without PF_NOFREEZE is not responding to the freezer "
     "within the timeout (default 20 s). Common causes: thread stuck in "
     "uninterruptible sleep (D state) waiting for I/O or mutex; driver "
     "kthread not calling try_to_freeze() in its main loop. "
     "Debug: look for [name] D in /proc/*/status at abort time; "
     "add try_to_freeze() to the thread's main loop.",
     "power",
     "linux-pm-freezer",
     "base"),
]

# ---------------------------------------------------------------------------
# Failure mode nodes — STD
# ---------------------------------------------------------------------------

_STD_FAILURES = [
    ("STD-image-write-failure",
     "Hibernation aborted; dmesg shows 'PM: Not enough free swap' or I/O error "
     "writing hibernate image",
     "Swap partition or file is too small (must be ≥ image size, typically "
     "50-70% of RAM). Also caused by: F2FS foreground GC running during image "
     "write causing I/O stall; eMMC write cache flush timeout. "
     "Debug: check /proc/swaps for available swap space; "
     "tune vm.dirty_ratio before hibernation to reduce dirty pages.",
     "storage",
     "linux-swsusp",
     "base"),

    ("STD-image-corrupted",
     "STD resume fails with 'PM: Image mismatch' or 'invalid magic' in dmesg; "
     "system boots fresh instead of restoring",
     "Hibernate image on swap is corrupted or stale. Causes: swap written to "
     "after hibernate image was saved (dual-boot, fsck); kernel version changed "
     "between hibernate and resume (image is version-tagged); "
     "swap encryption key changed. "
     "Debug: check dmesg for 'swsusp: resume failed'; "
     "verify swap UUID matches /sys/power/resume device.",
     "storage",
     "linux-swsusp",
     "base"),

    ("STD-device-freeze-failure",
     "Hibernation aborted during freeze phase; dmesg shows driver name and "
     "'PM: Device failed to freeze'",
     "A driver's .freeze() or .freeze_noirq() callback returned an error. "
     "Common causes: DMA transfer in progress at freeze time; driver holds a "
     "mutex that cannot be acquired with IRQs disabled; device hardware in "
     "inconsistent state. "
     "Debug: enable CONFIG_PM_DEBUG; look for error return in .freeze() path; "
     "check driver for in-flight DMA at freeze time.",
     "power",
     "dev-pm-ops",
     "base"),

    ("STD-bootloader-no-resume",
     "After STD power-off, system performs a full cold boot instead of "
     "restoring hibernation image",
     "Bootloader does not detect or pass the resume= kernel parameter. "
     "Causes: bootloader not configured to check hibernate variable; "
     "UEFI firmware clears waking vector on power-cycle; "
     "kernel cmdline does not include resume=/dev/swapX. "
     "Debug: verify 'resume=' is in /proc/cmdline; check bootloader config "
     "for hibernate/resume entry; confirm swap device UUID matches.",
     "boot",
     "bootloader-hibernate-resume",
     "base"),
]

# ---------------------------------------------------------------------------
# Ingest function
# ---------------------------------------------------------------------------

def ingest(db_path: str = None) -> int:
    """Ingest Linux STR/STD suspend-hibernate knowledge into the Kuzu database."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = os.path.abspath(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    inserted = 0

    # Component nodes
    for name, ctype, desc, ns, vendor, version in _COMPONENTS:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "description": desc,
            "namespace": ns, "vendor": vendor, "version": version,
        }):
            inserted += 1

    # Power domain nodes
    for name, dtype, desc, ns, vmv, ima in _POWER_DOMAINS:
        if upsert_node(conn, "PowerDomain", {
            "name": name, "type": dtype, "description": desc,
            "namespace": ns, "voltage_mv": vmv, "current_ma": ima,
        }):
            inserted += 1

    # STR failure modes
    for name, symptom, root_cause, domain, affected, ns in _STR_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": domain, "source": "linux-kernel-docs",
            "namespace": ns, "severity": "high",
        }):
            inserted += 1

    # STD failure modes
    for name, symptom, root_cause, domain, affected, ns in _STD_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": domain, "source": "linux-kernel-docs",
            "namespace": ns, "severity": "medium",
        }):
            inserted += 1

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    # linux-pm-suspend uses PSCI_SYSTEM_SUSPEND to enter platform sleep
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "ClockSource",
               "linux-pm-suspend", "clk-ref-26mhz",
               {"description": "PM suspend path requires reference clock stable before resume"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-suspend", "PSCI-SYSTEM_SUSPEND",
               {"description": "linux-pm-suspend calls PSCI SYSTEM_SUSPEND via platform_suspend_ops.enter()"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-hibernate", "linux-swsusp",
               {"description": "linux-pm-hibernate delegates memory snapshot to linux-swsusp"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-hibernate", "bootloader-hibernate-resume",
               {"description": "STD resume path: bootloader detects image and hands off to kernel"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-core", "linux-pm-suspend",
               {"description": "PM core dispatches to suspend path for STR"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-core", "linux-pm-hibernate",
               {"description": "PM core dispatches to hibernate path for STD"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-core", "linux-pm-freezer",
               {"description": "PM core invokes task freezer before suspend and hibernate"})

    create_rel(conn, "ROUTES_TO", "Component", "Component",
               "linux-pm-core", "linux-pm-wakeup",
               {"description": "PM core checks wakeup sources before allowing suspend entry"})

    # Power domain: STR keeps DDR powered via self-refresh
    create_rel(conn, "POWERS", "PowerDomain", "Component",
               "PD-SYSTEM-STR", "linux-pm-suspend",
               {"description": "STR system sleep domain: DDR self-refresh active, CPU/GPU off"})

    # STR failure modes — CAUSED_BY their triggering component
    for fm_name, comp_name, desc in [
        ("STR-blocked-by-wakeup-source", "linux-pm-wakeup",
         "Active wakeup_source prevents PM core from entering suspend"),
        ("STR-resume-hang-driver-fail", "dev-pm-ops",
         "Driver .resume() callback deadlock or panic"),
        ("STR-wakeup-latency-regression", "linux-pm-suspend",
         "Slow .resume() callback or DDR frequency not restored"),
        ("STR-power-rail-not-restored", "PSCI-SYSTEM_SUSPEND",
         "PSCI firmware rail restoration error on resume"),
        ("STR-lost-wakeup-irq", "linux-pm-wakeup",
         "Wakeup IRQ lost in window before WFI entry"),
        ("STR-kernel-thread-not-freezable", "linux-pm-freezer",
         "Kernel thread not responding to freezer within timeout"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   fm_name, comp_name, {"description": desc})

    # STD failure modes — CAUSED_BY their triggering component
    for fm_name, comp_name, desc in [
        ("STD-image-write-failure", "linux-swsusp",
         "Insufficient swap space or I/O error writing hibernate image"),
        ("STD-image-corrupted", "linux-swsusp",
         "Hibernate image on swap corrupted or version mismatch"),
        ("STD-device-freeze-failure", "dev-pm-ops",
         "Driver .freeze() callback returned error"),
        ("STD-bootloader-no-resume", "bootloader-hibernate-resume",
         "Bootloader did not pass resume= parameter to kernel"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   fm_name, comp_name, {"description": desc})

    print(f"[linux-suspend-hibernate] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db-path", default=None)
    args = p.parse_args()
    ingest(args.db_path)
