"""
ftrace log parser — C-state residency and suspend/resume event analysis.

Parses trace-cmd / ftrace text output for:
  - power:cpu_idle events  → C-state residency per CPU
  - power:suspend_resume   → per-stage suspend/resume timing
  - power:cpu_frequency    → DVFS transition events

Input: path to a trace-cmd text report (trace-cmd report -i trace.dat)
       or a raw /sys/kernel/debug/tracing/trace snapshot.
"""

from __future__ import annotations

import re
import os
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# cpu_idle: <idle>-0 [002] d..2 12345.678: cpu_idle: state=3 cpu_id=2
_CPU_IDLE_RE = re.compile(
    r"cpu_idle:\s+state=(?P<state>\d+|-?\d+)\s+cpu_id=(?P<cpu>\d+)"
)

# suspend_resume: <...>-1 [000] d..2 12345.678: suspend_resume: syscore_resume[0] end
_SUSPEND_RESUME_RE = re.compile(
    r"(?P<ts>[\d.]+).*?suspend_resume:\s+(?P<action>\S+)\s*(?:\[(?P<idx>\d+)\])?\s*(?P<phase>begin|end|start|finish)?"
)

# cpu_frequency: cpu_frequency: state=1800000 cpu_id=0
_CPU_FREQ_RE = re.compile(
    r"cpu_frequency:\s+state=(?P<freq_khz>\d+)\s+cpu_id=(?P<cpu>\d+)"
)

# Timestamp prefix: "    <task>-PID  [CPU] flags  TIMESTAMP: ..."
_TS_RE = re.compile(r"^\s*\S+\s+\[(?P<cpu>\d+)\]\s+\S+\s+(?P<ts>[\d.]+):")


# ---------------------------------------------------------------------------
# C-state residency analysis
# ---------------------------------------------------------------------------

def _parse_cstate_residency(lines: list[str]) -> dict[str, Any]:
    """Compute per-CPU C-state residency from cpu_idle events."""
    # state -1 or 4294967295 means "exit idle" (CPU woke up)
    WAKEUP_STATES = {-1, 4294967295}

    # {cpu: [(ts, state)]}
    events: dict[int, list[tuple[float, int]]] = defaultdict(list)

    for line in lines:
        m = _CPU_IDLE_RE.search(line)
        if not m:
            continue
        ts_m = _TS_RE.match(line)
        ts = float(ts_m.group("ts")) if ts_m else 0.0
        state = int(m.group("state")) % (2**32)  # handle unsigned wrap
        if state == 4294967295:
            state = -1
        cpu = int(m.group("cpu"))
        events[cpu].append((ts, state))

    if not events:
        return {"error": "No cpu_idle events found in trace"}

    # Compute residency: time between enter(state=N) and exit(state=-1)
    # {cpu: {state: total_ms}}
    residency: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    total_time: dict[int, float] = defaultdict(float)

    for cpu, ev_list in events.items():
        ev_list.sort(key=lambda x: x[0])
        last_enter: dict[int, float] = {}
        for ts, state in ev_list:
            if state in WAKEUP_STATES:
                # CPU woke up — close all open enter events
                for s, enter_ts in list(last_enter.items()):
                    residency[cpu][s] += (ts - enter_ts) * 1000  # ms
                    total_time[cpu] += (ts - enter_ts) * 1000
                last_enter.clear()
            else:
                last_enter[state] = ts

    # Format results
    result = {}
    for cpu in sorted(residency.keys()):
        cpu_total = sum(residency[cpu].values())
        states = {}
        for state in sorted(residency[cpu].keys()):
            ms = residency[cpu][state]
            states[f"C{state}"] = {
                "total_ms": round(ms, 2),
                "percent": round(100 * ms / cpu_total, 1) if cpu_total > 0 else 0.0,
            }
        result[f"CPU{cpu}"] = {"states": states, "total_idle_ms": round(cpu_total, 2)}

    return {"cstate_residency": result, "event_count": sum(len(v) for v in events.values())}


# ---------------------------------------------------------------------------
# Suspend/resume timing analysis
# ---------------------------------------------------------------------------

def _parse_suspend_resume(lines: list[str]) -> dict[str, Any]:
    """Extract per-stage suspend/resume timing from power:suspend_resume events."""
    stages: list[dict] = []
    open_stages: dict[str, float] = {}

    for line in lines:
        m = _SUSPEND_RESUME_RE.search(line)
        if not m:
            continue
        ts = float(m.group("ts"))
        action = m.group("action")
        phase = m.group("phase") or ""

        key = action
        if phase in ("begin", "start"):
            open_stages[key] = ts
        elif phase in ("end", "finish"):
            if key in open_stages:
                duration_ms = (ts - open_stages.pop(key)) * 1000
                stages.append({"stage": action, "duration_ms": round(duration_ms, 2)})

    # Sort by duration descending to surface slowest stages first
    stages.sort(key=lambda x: x["duration_ms"], reverse=True)

    if not stages:
        return {"warning": "No suspend_resume events found — ensure 'power:suspend_resume' tracepoint is enabled"}

    total_ms = sum(s["duration_ms"] for s in stages)
    return {
        "suspend_resume_stages": stages,
        "total_measured_ms": round(total_ms, 2),
        "slowest_stage": stages[0] if stages else None,
    }


# ---------------------------------------------------------------------------
# DVFS frequency transition analysis
# ---------------------------------------------------------------------------

def _parse_dvfs_transitions(lines: list[str]) -> dict[str, Any]:
    """Count and summarise CPU frequency transitions from cpu_frequency events."""
    # {cpu: {freq_mhz: count}}
    freq_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for line in lines:
        m = _CPU_FREQ_RE.search(line)
        if not m:
            continue
        freq_mhz = int(m.group("freq_khz")) // 1000
        cpu = int(m.group("cpu"))
        freq_counts[cpu][freq_mhz] += 1

    if not freq_counts:
        return {"warning": "No cpu_frequency events found — ensure 'power:cpu_frequency' tracepoint is enabled"}

    result = {}
    for cpu in sorted(freq_counts.keys()):
        total = sum(freq_counts[cpu].values())
        freqs = {f"{f}MHz": cnt for f, cnt in sorted(freq_counts[cpu].items())}
        result[f"CPU{cpu}"] = {"transitions": freqs, "total_transitions": total}

    return {"dvfs_transitions": result}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ftrace(log_path: str) -> dict[str, Any]:
    """Parse an ftrace / trace-cmd log file.

    Parameters
    ----------
    log_path:
        Path to the trace-cmd text report or raw ftrace snapshot.

    Returns
    -------
    dict with keys:
        ``cstate_residency``   — per-CPU C-state time and percentage
        ``suspend_resume``     — per-stage suspend/resume timing (if present)
        ``dvfs_transitions``   — frequency transition histogram (if present)
        ``file``               — resolved file path
        ``lines_parsed``       — number of lines processed
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "cstate_residency": _parse_cstate_residency(lines),
        "suspend_resume": _parse_suspend_resume(lines),
        "dvfs_transitions": _parse_dvfs_transitions(lines),
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python ftrace_parser.py <trace_file>")
        sys.exit(1)
    print(json.dumps(parse_ftrace(sys.argv[1]), indent=2))
