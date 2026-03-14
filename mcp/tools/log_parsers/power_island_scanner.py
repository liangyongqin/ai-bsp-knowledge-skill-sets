"""
Power island scanner — detect zombie power island states from pm_domain debug.

Parses:
  - /sys/kernel/debug/pm_genpd/pm_genpd_summary (genpd state dump)
  - dmesg for genpd state change events
  - /sys/kernel/debug/power/runtime_pm_status (runtime PM states per device)

A "zombie" power island is a power domain that:
  - Remains ON even with no active devices (refcount=0)
  - Never transitions to the off state after the last device suspends
  - Shows idle_time=0 despite no attached devices running

Reference: Linux Documentation/power/runtime_pm.rst, kernel/power/domain.c
"""

from __future__ import annotations

import re
import os
from typing import Any

# genpd summary line format:
# domain_name           status   slaves  devices
# -------------------------------------------------------
# pd-cpu0               on       -       cpu0
_GENPD_DOMAIN_RE = re.compile(
    r"^(?P<domain>[\w\-\.]+)\s+(?P<status>on|off|unknown)\s+"
    r"(?P<slaves>\S+)\s+(?P<devices>.*)$",
    re.IGNORECASE,
)

# Alternative format with performance state:
# domain_name (PS: N)   status   ...
_GENPD_DOMAIN_PS_RE = re.compile(
    r"^(?P<domain>[\w\-\.]+)\s*(?:\(PS:\s*\d+\))?\s+(?P<status>on|off)\s+",
    re.IGNORECASE,
)

# dmesg genpd power on/off: "genpd_power_off: pd-name"
_GENPD_EVENT_RE = re.compile(
    r"(?P<ts>[\d.]+).*?genpd_(?P<action>power_on|power_off|sync_state|remove_device)\s+(?P<pd>[\w\-\.]+)",
    re.IGNORECASE,
)

# Runtime PM status line (from /sys/kernel/debug/power/runtime_pm_status or sysfs)
# "  active  since 0ms"  or  "  suspended  since 1234ms"
_RPM_STATUS_RE = re.compile(
    r"(?P<device>[\w\/\-\.]+)\s+(?P<status>active|suspended|unsupported|disabled)\s+"
    r"(?:since\s+(?P<since_ms>\d+)\s*ms)?",
    re.IGNORECASE,
)

# Genpd error
_GENPD_ERR_RE = re.compile(r"genpd.*?(?:error|failed|timeout|timed out)", re.IGNORECASE)


def _parse_genpd_summary(lines: list[str]) -> dict[str, Any]:
    """Parse /sys/kernel/debug/pm_genpd/pm_genpd_summary content."""
    domains: list[dict] = []
    zombie_candidates: list[dict] = []
    in_header = True

    for line in lines:
        line = line.rstrip()
        if not line or line.startswith("-") or line.startswith("domain"):
            in_header = False
            continue
        if in_header:
            continue

        m = _GENPD_DOMAIN_RE.match(line) or _GENPD_DOMAIN_PS_RE.match(line)
        if not m:
            continue

        domain = m.group("domain")
        status = m.group("status").lower()
        devices_str = line[m.end():].strip() if hasattr(m, 'end') else ""

        # Count attached devices (non-empty, non-dash entries)
        device_list = [d.strip() for d in re.split(r"\s{2,}|\t", devices_str) if d.strip() and d.strip() != "-"]

        entry = {
            "domain": domain,
            "status": status,
            "device_count": len(device_list),
            "devices": device_list[:5],
        }
        domains.append(entry)

        # Zombie heuristic: domain is ON but no devices attached
        if status == "on" and len(device_list) == 0:
            zombie_candidates.append(entry)

    return {
        "domains": domains,
        "total_domains": len(domains),
        "on_count": sum(1 for d in domains if d["status"] == "on"),
        "off_count": sum(1 for d in domains if d["status"] == "off"),
        "zombie_candidates": zombie_candidates,
    }


def scan_power_islands(
    genpd_summary_path: str,
    dmesg_path: str | None = None,
) -> dict[str, Any]:
    """Scan power island states for zombie domains.

    Parameters
    ----------
    genpd_summary_path:
        Path to /sys/kernel/debug/pm_genpd/pm_genpd_summary snapshot.
    dmesg_path:
        Optional dmesg for genpd transition events.

    Returns
    -------
    dict with keys:
        ``domains``           — all power domains with status
        ``zombie_candidates`` — domains ON with no attached devices
        ``genpd_errors``      — genpd error lines from dmesg
        ``diagnosis``         — human-readable summary
    """
    path = os.path.abspath(genpd_summary_path)
    if not os.path.isfile(path):
        return {"error": f"File not found: {path}"}

    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()

    parsed = _parse_genpd_summary(lines)
    genpd_errors: list[str] = []
    genpd_events: list[dict] = []

    if dmesg_path:
        dmesg_abs = os.path.abspath(dmesg_path)
        if os.path.isfile(dmesg_abs):
            with open(dmesg_abs, "r", errors="replace") as fh:
                dmesg_lines = fh.readlines()
            for line in dmesg_lines:
                m = _GENPD_EVENT_RE.search(line)
                if m:
                    genpd_events.append({
                        "ts": float(m.group("ts")),
                        "action": m.group("action"),
                        "pd": m.group("pd"),
                    })
                if _GENPD_ERR_RE.search(line):
                    genpd_errors.append(line.strip())

    zombies = parsed["zombie_candidates"]
    diagnosis: str
    if zombies:
        names = ", ".join(z["domain"] for z in zombies[:5])
        diagnosis = (
            f"{len(zombies)} zombie power island(s) detected: {names}. "
            "These domains are ON but have no active devices — they are blocking system power collapse. "
            "Fix: check that all child devices completed runtime_suspend before system suspend; "
            "verify genpd.power_off() is called when device_count reaches 0. "
            "Use: cat /sys/kernel/debug/pm_genpd/pm_genpd_summary to confirm. "
            "Escalate to /boot-debug-expert if power island is gated by hardware isolation cell."
        )
    elif genpd_errors:
        diagnosis = (
            f"{len(genpd_errors)} genpd error(s) in dmesg. "
            f"First: {genpd_errors[0][:120]}. "
            "Check power domain driver probe order and voltage sequencing."
        )
    else:
        diagnosis = (
            f"Scanned {parsed['total_domains']} power domains: "
            f"{parsed['on_count']} ON, {parsed['off_count']} OFF. "
            "No zombie power islands detected."
        )

    return {
        "file": path,
        "domains": parsed["domains"][:30],
        "total_domains": parsed["total_domains"],
        "on_count": parsed["on_count"],
        "off_count": parsed["off_count"],
        "zombie_candidates": zombies,
        "genpd_errors": genpd_errors[:10],
        "genpd_events": genpd_events[:20],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    args = sys.argv[1:]
    if not args:
        print("Usage: python power_island_scanner.py <genpd_summary> [dmesg_log]")
        sys.exit(1)
    dmesg = args[1] if len(args) > 1 else None
    print(json.dumps(scan_power_islands(args[0], dmesg), indent=2))
