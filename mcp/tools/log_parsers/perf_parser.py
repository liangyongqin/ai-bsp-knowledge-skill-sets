"""
perf stat log parser — IPC, cache miss rate, and branch prediction per CPU cluster.

Parses text output from:
  perf stat -a --topdown -e cycles,instructions,cache-misses,cache-references,
             branch-misses,branches -C 0-3 sleep 5

or a simple `perf stat` text dump.
"""

from __future__ import annotations

import re
import os
from typing import Any

# perf stat line:  "     12,345,678      cycles"
# or:              "     12,345,678      cycles:u                  # 1.23 GHz"
_STAT_LINE_RE = re.compile(
    r"^\s*(?P<value>[\d,\.]+)\s+(?P<event>[\w\-:]+)"
    r"(?:\s+#\s+(?P<rate>[^\n]+))?"
)

# Topdown hierarchy line: "  S0-C0  Frontend Bound:  12.34%"
_TOPDOWN_RE = re.compile(
    r"(?P<scope>S\d+-C\d+|CPU\d+|system wide)\s+(?P<metric>[\w\s]+):\s+(?P<pct>[\d.]+)%",
    re.IGNORECASE,
)

# Elapsed time: "       5.002265637 seconds time elapsed"
_ELAPSED_RE = re.compile(r"(?P<sec>[\d.]+)\s+seconds?\s+time\s+elapsed")

# CPUs utilized: "      3.456 CPUs utilized"
_CPUS_UTIL_RE = re.compile(r"(?P<util>[\d.]+)\s+CPUs?\s+utilized")

IPC_WARN_THRESHOLD = 1.0   # IPC below this indicates stall-bound workload
CACHE_MISS_WARN_PCT = 5.0  # L1/LLC miss rate above this is problematic


def _parse_value(raw: str) -> float:
    """Convert '12,345,678' or '1.23' to float."""
    return float(raw.replace(",", ""))


def parse_perf_stat(log_path: str) -> dict[str, Any]:
    """Parse a `perf stat` text log.

    Parameters
    ----------
    log_path:
        Path to `perf stat` text output (redirect stderr to file with 2>&1).

    Returns
    -------
    dict with keys:
        ``counters``        — raw event counters {event: value}
        ``ipc``             — instructions per cycle (float or None)
        ``cache_miss_pct``  — L1/LLC miss percentage (float or None)
        ``branch_miss_pct`` — branch misprediction percentage (float or None)
        ``elapsed_sec``     — measurement window in seconds
        ``cpus_utilized``   — average CPU utilization
        ``topdown``         — topdown breakdown if present
        ``diagnosis``       — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    counters: dict[str, float] = {}
    elapsed_sec: float | None = None
    cpus_utilized: float | None = None
    topdown: list[dict] = []

    for line in lines:
        # Elapsed time
        m = _ELAPSED_RE.search(line)
        if m:
            elapsed_sec = float(m.group("sec"))
            continue

        # CPUs utilized
        m = _CPUS_UTIL_RE.search(line)
        if m:
            cpus_utilized = float(m.group("util"))
            continue

        # Topdown metrics
        m = _TOPDOWN_RE.search(line)
        if m:
            topdown.append({
                "scope": m.group("scope"),
                "metric": m.group("metric").strip(),
                "pct": float(m.group("pct")),
            })
            continue

        # Generic event counter line
        m = _STAT_LINE_RE.match(line)
        if m:
            event = m.group("event").rstrip(":u").rstrip(":k")
            try:
                counters[event] = _parse_value(m.group("value"))
            except ValueError:
                pass

    # Derived metrics
    cycles = counters.get("cycles", 0)
    instructions = counters.get("instructions", 0)
    ipc = (instructions / cycles) if cycles > 0 else None

    cache_refs = counters.get("cache-references", 0)
    cache_misses = counters.get("cache-misses", 0)
    cache_miss_pct = (100.0 * cache_misses / cache_refs) if cache_refs > 0 else None

    branches = counters.get("branches", 0)
    branch_misses = counters.get("branch-misses", 0)
    branch_miss_pct = (100.0 * branch_misses / branches) if branches > 0 else None

    # Diagnosis
    issues = []
    if ipc is not None and ipc < IPC_WARN_THRESHOLD:
        issues.append(
            f"Low IPC={ipc:.2f} (threshold {IPC_WARN_THRESHOLD}) — "
            "workload is memory/stall-bound. "
            "Check cache miss rate and memory bandwidth. "
            "Consider reviewing prefetch policy or LPDDR5 ODT tuning."
        )
    if cache_miss_pct is not None and cache_miss_pct > CACHE_MISS_WARN_PCT:
        issues.append(
            f"High cache miss rate={cache_miss_pct:.1f}% (threshold {CACHE_MISS_WARN_PCT}%). "
            "Identify hot data structures and evaluate working-set size vs LLC capacity."
        )
    if branch_miss_pct is not None and branch_miss_pct > 5.0:
        issues.append(
            f"Branch misprediction rate={branch_miss_pct:.1f}%. "
            "Profile hot branches with `perf annotate` — consider PGO or branch hint macros."
        )

    if issues:
        diagnosis = " | ".join(issues)
    elif ipc is not None:
        diagnosis = f"IPC={ipc:.2f} — workload appears compute-bound. No critical stall indicators."
    else:
        diagnosis = "Insufficient counter data to compute IPC. Ensure cycles+instructions events are collected."

    return {
        "file": log_path,
        "elapsed_sec": elapsed_sec,
        "cpus_utilized": cpus_utilized,
        "counters": counters,
        "ipc": round(ipc, 3) if ipc is not None else None,
        "cache_miss_pct": round(cache_miss_pct, 2) if cache_miss_pct is not None else None,
        "branch_miss_pct": round(branch_miss_pct, 2) if branch_miss_pct is not None else None,
        "topdown": topdown[:20],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python perf_parser.py <perf_stat_log>")
        sys.exit(1)
    print(json.dumps(parse_perf_stat(sys.argv[1]), indent=2))
