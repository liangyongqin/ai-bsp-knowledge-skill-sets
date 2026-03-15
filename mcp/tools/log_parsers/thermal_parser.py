"""
Thermal log parser — LVTS throttling events from dmesg / kernel thermal drivers.

Parses dmesg for Linux thermal framework events:
  - Thermal zone temperature readings
  - Trip point crossings (throttling onset)
  - Cooling device state changes (CPU/GPU frequency step-down)
  - LVTS (Low Voltage Thermal Sensor) events on MTK platforms
"""

from __future__ import annotations

import re
import os
from collections import defaultdict
from typing import Any

# Thermal zone temperature: "thermal thermal_zone0: ... temp: 65000"
_ZONE_TEMP_RE = re.compile(
    r"thermal[_ ](?:thermal_)?zone(\d+).*?temp[:\s]+(?P<temp_mc>\d+)"
)

# Trip point crossed: "thermal_zone0: critical temperature reached(125 C), shutting down"
# or: "tzX: trip point Y crossed"
_TRIP_CROSSED_RE = re.compile(
    r"(?:zone\d+|tz\d+|thermal).*?(?:trip\s*point\s*(?P<trip>\d+)\s*crossed"
    r"|critical\s+temperature\s+reached\((?P<crit_c>\d+))"
    , re.IGNORECASE
)

# Cooling device state: "cpufreq_cooling0: set max_state 5"
_COOLING_RE = re.compile(
    r"(?P<dev>[\w\-]+cooling\d*)[:\s]+.*?(?:state|max_state)[:\s]+(?P<state>\d+)"
)

# Generic throttle message
_THROTTLE_RE = re.compile(r"throttl", re.IGNORECASE)


def parse_thermal_log(log_path: str) -> dict[str, Any]:
    """Parse a dmesg log for thermal throttling events.

    Parameters
    ----------
    log_path:
        Path to dmesg output file.

    Returns
    -------
    dict with keys:
        ``trip_crossings``    — list of trip point crossing events
        ``cooling_events``    — cooling device state changes
        ``max_temp_mc``       — peak temperature seen (millicelsius)
        ``throttle_count``    — total throttle-related log lines
        ``diagnosis``         — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    trip_crossings: list[str] = []
    cooling_events: list[dict] = []
    max_temp_mc = 0
    throttle_count = 0

    for line in lines:
        # Temperature readings
        m = _ZONE_TEMP_RE.search(line)
        if m:
            t = int(m.group("temp_mc"))
            if t > max_temp_mc:
                max_temp_mc = t

        # Trip crossings
        m = _TRIP_CROSSED_RE.search(line)
        if m:
            trip_crossings.append(line.strip())

        # Cooling state changes
        m = _COOLING_RE.search(line)
        if m:
            cooling_events.append({
                "device": m.group("dev"),
                "state": int(m.group("state")),
                "line": line.strip(),
            })

        # Generic throttle lines
        if _THROTTLE_RE.search(line):
            throttle_count += 1

    max_temp_c = max_temp_mc / 1000 if max_temp_mc is not None and max_temp_mc > 0 else None

    temp_str = f"{max_temp_c:.1f}°C" if max_temp_c is not None else "unknown"
    diagnosis = "No thermal throttling events detected."
    if trip_crossings:
        diagnosis = (
            f"{len(trip_crossings)} trip point crossing(s) detected. "
            f"Peak temperature: {temp_str}. "
            f"{len(cooling_events)} cooling device state change(s). "
            "Review EAS energy model and thermal budget allocation. "
            "Escalate to /power-thermal-expert for DVFS/EAS tuning."
        )
    elif throttle_count > 0:
        diagnosis = (
            f"{throttle_count} throttle-related log line(s) found but no trip point crossing. "
            f"Peak temperature seen: {temp_str}. May be near-threshold."
        )

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "trip_crossings": trip_crossings[:20],  # cap output
        "cooling_events": cooling_events[:20],
        "max_temp_celsius": max_temp_c,
        "throttle_log_lines": throttle_count,
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python thermal_parser.py <dmesg_log>")
        sys.exit(1)
    print(json.dumps(parse_thermal_log(sys.argv[1]), indent=2))
