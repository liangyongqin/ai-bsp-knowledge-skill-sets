"""
IRQ statistics parser — /proc/interrupts snapshot analysis.

Parses one or two /proc/interrupts snapshots to:
  - Compute per-IRQ rate (if two snapshots provided with elapsed time)
  - Detect interrupt storms (>10,000 IRQ/s on a single line)
  - Detect per-CPU imbalance (all interrupts on CPU0)
  - Summarise top interrupt sources
"""

from __future__ import annotations

import re
import os
from typing import Any

# /proc/interrupts line:
#  IRQ_NUM:  CPU0   CPU1  ...  type  chip_name  action_name
_IRQ_LINE_RE = re.compile(
    r"^\s*(?P<irq>\d+|[A-Z]+):\s+(?P<counts>[\d\s]+)\s+(?P<meta>.+)$"
)

STORM_THRESHOLD_PER_SEC = 10_000


def _parse_snapshot(lines: list[str]) -> dict[str, dict]:
    """Parse /proc/interrupts into {irq: {counts: [...], meta: str}}."""
    result = {}
    for line in lines:
        m = _IRQ_LINE_RE.match(line)
        if not m:
            continue
        irq = m.group("irq")
        counts = [int(x) for x in m.group("counts").split()]
        meta = m.group("meta").strip()
        result[irq] = {"counts": counts, "total": sum(counts), "meta": meta}
    return result


def parse_irq_stats(
    snapshot_path: str,
    snapshot_path_after: str | None = None,
    elapsed_sec: float = 1.0,
) -> dict[str, Any]:
    """Analyse /proc/interrupts snapshot(s).

    Parameters
    ----------
    snapshot_path:
        Path to first /proc/interrupts snapshot (or only snapshot).
    snapshot_path_after:
        Optional path to second snapshot taken ``elapsed_sec`` later.
    elapsed_sec:
        Time between snapshots in seconds (default 1.0).

    Returns
    -------
    dict with keys:
        ``top_irqs``        — top 15 IRQs by count / rate
        ``storms``          — IRQs exceeding storm threshold
        ``imbalanced_irqs`` — IRQs where >95% of events hit one CPU
        ``diagnosis``       — human-readable summary
    """
    path1 = os.path.abspath(snapshot_path)
    if not os.path.isfile(path1):
        return {"error": f"File not found: {path1}"}

    with open(path1, "r", errors="replace") as fh:
        lines1 = fh.readlines()
    snap1 = _parse_snapshot(lines1)

    rate_mode = False
    snap2 = {}
    if snapshot_path_after:
        path2 = os.path.abspath(snapshot_path_after)
        if os.path.isfile(path2):
            with open(path2, "r", errors="replace") as fh:
                lines2 = fh.readlines()
            snap2 = _parse_snapshot(lines2)
            rate_mode = True

    # Build per-IRQ entries
    entries: list[dict] = []
    for irq, data in snap1.items():
        entry: dict[str, Any] = {
            "irq": irq,
            "meta": data["meta"],
            "total": data["total"],
        }
        if rate_mode and irq in snap2:
            delta = snap2[irq]["total"] - data["total"]
            rate = delta / elapsed_sec
            entry["rate_per_sec"] = round(rate, 1)
            entry["delta"] = delta
        entries.append(entry)

    # Sort by rate (if available) else total
    sort_key = "rate_per_sec" if rate_mode else "total"
    entries.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

    top_irqs = entries[:15]

    # Storm detection
    storms = []
    if rate_mode:
        storms = [e for e in entries if e.get("rate_per_sec", 0) > STORM_THRESHOLD_PER_SEC]

    # CPU imbalance detection (only if we have per-CPU counts)
    imbalanced = []
    for irq, data in snap1.items():
        counts = data["counts"]
        total = sum(counts)
        if total < 100:
            continue
        max_cpu_count = max(counts)
        if max_cpu_count / total > 0.95:
            imbalanced.append({
                "irq": irq,
                "dominant_cpu": counts.index(max_cpu_count),
                "percent_on_dominant": round(100 * max_cpu_count / total, 1),
                "meta": data["meta"],
            })

    # Diagnosis
    if storms:
        s = storms[0]
        diagnosis = (
            f"INTERRUPT STORM: IRQ {s['irq']} at {s.get('rate_per_sec', '?')}/s "
            f"({s['meta']}). "
            "Check: device driver missing interrupt mask/ACK in handler. "
            "Escalate to /interrupt-virtualization-expert."
        )
    elif imbalanced:
        diagnosis = (
            f"{len(imbalanced)} IRQ(s) showing severe CPU imbalance. "
            f"IRQ {imbalanced[0]['irq']}: {imbalanced[0]['percent_on_dominant']}% on CPU{imbalanced[0]['dominant_cpu']}. "
            "Use irqbalance or set /proc/irq/N/smp_affinity_list."
        )
    else:
        diagnosis = "No interrupt storms or severe imbalance detected."

    return {
        "mode": "rate" if rate_mode else "snapshot",
        "elapsed_sec": elapsed_sec if rate_mode else None,
        "top_irqs": top_irqs,
        "storms": storms,
        "imbalanced_irqs": imbalanced[:10],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    args = sys.argv[1:]
    if not args:
        print("Usage: python irq_stat_parser.py <snapshot1> [snapshot2] [elapsed_sec]")
        sys.exit(1)
    path1 = args[0]
    path2 = args[1] if len(args) > 1 else None
    elapsed = float(args[2]) if len(args) > 2 else 1.0
    print(json.dumps(parse_irq_stats(path1, path2, elapsed), indent=2))
