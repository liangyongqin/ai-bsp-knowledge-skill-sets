"""
VM Exit counter — KVM ARM VM Exit frequency analysis from perf kvm stat.

Parses output of:
  perf kvm stat report --event=vmexit  (from a `perf kvm stat record` session)
  or: perf kvm stat live

Detects:
  - High-frequency VM Exits by exit reason
  - IRQ/FIQ exits that may indicate interrupt virtualization overhead
  - MMIO exits from un-trapped device ranges
  - Timer exits (virtual timer, host timer)
  - System register (sysreg) exits

ARM KVM exit reasons defined in arch/arm64/include/uapi/asm/kvm.h (KVM_EXIT_*).

Reference: Linux Documentation/virt/kvm/, ARM GICv4 Architecture spec.
"""

from __future__ import annotations

import re
import os
from typing import Any

# perf kvm stat report output:
# Reason                        Samples  Samples%  Time%    Min Time  Max Time  Avg time
# TRAP_WFI                      123456   45.67%    23.45%   0.12us    5.67us    1.23us
_VMEXIT_ROW_RE = re.compile(
    r"^(?P<reason>[\w_\-\. ]+?)\s{2,}"
    r"(?P<samples>\d+)\s+"
    r"(?P<samples_pct>[\d.]+)%\s+"
    r"(?P<time_pct>[\d.]+)%\s+"
    r"(?P<min_us>[\d.]+)us\s+"
    r"(?P<max_us>[\d.]+)us\s+"
    r"(?P<avg_us>[\d.]+)us"
)

# Alternative: simpler perf kvm stat live format
# "Exit reason: TRAP_WFI count=12345"
_VMEXIT_SIMPLE_RE = re.compile(
    r"(?:Exit reason|vmexit)[:\s]+(?P<reason>[\w_]+)\s+(?:count|samples)[=:\s]+(?P<count>\d+)",
    re.IGNORECASE,
)

# ARM KVM exit reason categories
IRQFIQ_REASONS = {"IRQ", "FIQ", "ARM_EXCEPTION_IRQ", "ARM_EXCEPTION_EL1_SERROR"}
TIMER_REASONS  = {"TRAP_WFI", "TRAP_WFE", "TIMER", "VTIMER", "PTIMER"}
SYSREG_REASONS = {"TRAP_MSR_WFI", "TRAP_SYSREG", "SYSTEM_REGISTER", "SYSREGS"}
MMIO_REASONS   = {"MMIO", "DATA_ABORT", "TRAP_MMIO"}
HYPERCALL_REASONS = {"HVC", "HYPERCALL", "PSCI"}

# Cost thresholds
HIGH_EXIT_RATE_PER_SEC = 50_000
VM_EXIT_COST_CYCLES = 3000  # typical A55 VM Exit cost in cycles


def _categorise(reason: str) -> str:
    r = reason.upper().replace(" ", "_")
    if any(k in r for k in IRQFIQ_REASONS):
        return "IRQ/FIQ"
    if any(k in r for k in TIMER_REASONS):
        return "Timer/WFI"
    if any(k in r for k in SYSREG_REASONS):
        return "SysReg"
    if any(k in r for k in MMIO_REASONS):
        return "MMIO"
    if any(k in r for k in HYPERCALL_REASONS):
        return "Hypercall"
    return "Other"


def parse_vm_exit_stats(log_path: str, elapsed_sec: float = 1.0) -> dict[str, Any]:
    """Parse perf kvm stat report output for VM Exit analysis.

    Parameters
    ----------
    log_path:
        Path to `perf kvm stat report` output file.
    elapsed_sec:
        Measurement window in seconds (for rate calculation).

    Returns
    -------
    dict with keys:
        ``exits_by_reason``   — per-reason exit count, pct, avg latency
        ``exits_by_category`` — aggregated by category (IRQ/FIQ, Timer, MMIO, ...)
        ``total_exits``       — total VM Exit count
        ``exit_rate_per_sec`` — total exits per second
        ``top_exits``         — top 10 exit reasons by count
        ``diagnosis``         — human-readable summary
    """
    path = os.path.abspath(log_path)
    if not os.path.isfile(path):
        return {"error": f"File not found: {path}"}

    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()

    exits: list[dict] = []
    by_category: dict[str, int] = {}

    for line in lines:
        # Full perf kvm stat report format
        m = _VMEXIT_ROW_RE.match(line)
        if m:
            reason = m.group("reason").strip()
            cat = _categorise(reason)
            entry = {
                "reason": reason,
                "category": cat,
                "samples": int(m.group("samples")),
                "samples_pct": float(m.group("samples_pct")),
                "time_pct": float(m.group("time_pct")),
                "avg_us": float(m.group("avg_us")),
                "max_us": float(m.group("max_us")),
            }
            exits.append(entry)
            by_category[cat] = by_category.get(cat, 0) + entry["samples"]
            continue

        # Simple format
        m = _VMEXIT_SIMPLE_RE.search(line)
        if m:
            reason = m.group("reason")
            cat = _categorise(reason)
            count = int(m.group("count"))
            exits.append({
                "reason": reason,
                "category": cat,
                "samples": count,
            })
            by_category[cat] = by_category.get(cat, 0) + count

    if not exits:
        return {
            "error": "No VM Exit data found. Run: perf kvm stat record -a sleep 5 && perf kvm stat report"
        }

    total = sum(e["samples"] for e in exits)
    exit_rate = total / elapsed_sec if elapsed_sec > 0 else 0
    exits.sort(key=lambda x: x["samples"], reverse=True)

    # Diagnosis
    top = exits[:3]
    top_desc = ", ".join(f"{e['reason']}×{e['samples']}" for e in top)
    issues = []

    irq_count = by_category.get("IRQ/FIQ", 0)
    mmio_count = by_category.get("MMIO", 0)

    if exit_rate > HIGH_EXIT_RATE_PER_SEC:
        issues.append(
            f"VM Exit rate={exit_rate:.0f}/s exceeds threshold {HIGH_EXIT_RATE_PER_SEC}/s. "
            "High exit rate causes significant virtualization overhead. "
            f"CPU cost ≈ {exit_rate * VM_EXIT_COST_CYCLES / 1e9:.1f} Gcycles/s on A55."
        )
    if mmio_count > total * 0.3:
        issues.append(
            f"MMIO exits = {mmio_count} ({100*mmio_count//total}% of total). "
            "Device ranges should use GICv4 direct injection or kernel PV drivers "
            "to eliminate MMIO traps. Audit /proc/iomem for missing 'virtio' mappings."
        )
    if irq_count > total * 0.5:
        issues.append(
            f"IRQ/FIQ exits = {irq_count} ({100*irq_count//total}% of total). "
            "Enable GICv4 LPI direct injection to eliminate vIRQ delivery exits. "
            "Verify ITS MAPD/MAPC/MAPTI tables are valid (use its_validator tool)."
        )

    if issues:
        diagnosis = " | ".join(issues) + f" Top exits: {top_desc}."
    else:
        diagnosis = (
            f"Total VM Exits: {total} at {exit_rate:.0f}/s. "
            f"No critical overhead detected. Top: {top_desc}."
        )

    return {
        "file": path,
        "elapsed_sec": elapsed_sec,
        "total_exits": total,
        "exit_rate_per_sec": round(exit_rate, 1),
        "top_exits": exits[:10],
        "exits_by_category": by_category,
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    args = sys.argv[1:]
    if not args:
        print("Usage: python vm_exit_counter.py <perf_kvm_stat_report> [elapsed_sec]")
        sys.exit(1)
    elapsed = float(args[1]) if len(args) > 1 else 1.0
    print(json.dumps(parse_vm_exit_stats(args[0], elapsed), indent=2))
