"""
Suspend/resume log parser — STR/STD diagnosis from pm_debug dmesg and wakeup sources.

Parses:
  - dmesg with pm_debug=1 (detailed PM callback trace)
  - /sys/kernel/debug/wakeup_sources (active wakeup source listing)
  - /sys/power/pm_wakeup_irq (last wakeup IRQ number)
  - ftrace power:suspend_resume events (handled by ftrace_parser.py for timing;
    this parser handles the dmesg narrative form)
"""

from __future__ import annotations

import re
import os
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# PM device suspend/resume callback: "PM: Calling <driver> <callback>"
_PM_CALL_RE = re.compile(
    r"PM:\s+(?:Calling|Finishing)\s+(?P<driver>\S+)\s+\((?P<cb>[^)]+)\)"
)

# PM error: "PM: Device <driver> failed to <action> error -<N>"
_PM_ERROR_RE = re.compile(
    r"PM:\s+(?:Device\s+)?(?P<driver>\S+)\s+failed\s+to\s+(?P<action>\w+).*?(?P<errno>-?\d+)"
)

# Wakeup source line from /sys/kernel/debug/wakeup_sources:
# name  active_count  event_count  wakeup_count  expire_count  active_since  ...
_WAKEUP_SRC_RE = re.compile(
    r"^(?P<name>\S+)\s+(?P<active_count>\d+)\s+(?P<event_count>\d+)\s+"
    r"(?P<wakeup_count>\d+)\s+(?P<expire_count>\d+)\s+(?P<active_since>\d+)"
)

# Suspend abort: "PM: Wakeup pending, System sleep aborted"
_ABORT_RE = re.compile(r"PM:.*?(?:abort|ABORT|Wakeup pending)", re.IGNORECASE)

# Resume complete timestamp: "PM: resume of devices complete after N.NNN msecs"
_RESUME_COMPLETE_RE = re.compile(
    r"PM:.*?resume.*?complete.*?(?P<ms>[\d.]+)\s*msecs?"
)

# Suspend complete: "PM: suspend of devices complete after N.NNN msecs"
_SUSPEND_COMPLETE_RE = re.compile(
    r"PM:.*?suspend.*?complete.*?(?P<ms>[\d.]+)\s*msecs?"
)

# Freezing tasks: "Freezing user space processes"
_FREEZE_START_RE = re.compile(r"Freezing user space processes")
_FREEZE_FAIL_RE = re.compile(r"Freezing of tasks (?:failed|aborted)")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_pm_debug_dmesg(lines: list[str]) -> dict[str, Any]:
    """Parse pm_debug=1 dmesg output for suspend/resume failures and timing."""
    errors: list[dict] = []
    aborts: list[str] = []
    suspend_ms: float | None = None
    resume_ms: float | None = None
    freeze_failed = False

    for line in lines:
        # Errors
        m = _PM_ERROR_RE.search(line)
        if m:
            errors.append({
                "driver": m.group("driver"),
                "action": m.group("action"),
                "errno": int(m.group("errno")),
                "line": line.strip(),
            })

        # Abort messages
        if _ABORT_RE.search(line):
            aborts.append(line.strip())

        # Timing
        m = _SUSPEND_COMPLETE_RE.search(line)
        if m:
            suspend_ms = float(m.group("ms"))

        m = _RESUME_COMPLETE_RE.search(line)
        if m:
            resume_ms = float(m.group("ms"))

        # Freeze failure
        if _FREEZE_FAIL_RE.search(line):
            freeze_failed = True

    result: dict[str, Any] = {
        "errors": errors,
        "aborts": aborts,
        "freeze_failed": freeze_failed,
    }
    if suspend_ms is not None:
        result["suspend_total_ms"] = suspend_ms
    if resume_ms is not None:
        result["resume_total_ms"] = resume_ms

    if errors:
        result["diagnosis"] = (
            f"{len(errors)} driver(s) failed during suspend/resume. "
            f"First failure: driver='{errors[0]['driver']}' action='{errors[0]['action']}' "
            f"errno={errors[0]['errno']}. "
            "Add 'no_console_suspend' to cmdline and check serial log for the last driver "
            "printed before hang."
        )
    elif freeze_failed:
        result["diagnosis"] = (
            "Task freezer failed. A kernel thread is not responding to freeze within timeout. "
            "Check /proc/*/status for 'D' state threads at the time of failure. "
            "The offending thread's main loop is likely missing try_to_freeze()."
        )
    elif aborts:
        result["diagnosis"] = (
            "Suspend was aborted by a pending wakeup event. "
            "Check wakeup_sources for the active source: "
            "cat /sys/kernel/debug/wakeup_sources | sort -rn -k10 | head"
        )

    return result


def _parse_wakeup_sources(lines: list[str]) -> dict[str, Any]:
    """Parse /sys/kernel/debug/wakeup_sources content."""
    sources: list[dict] = []
    active: list[dict] = []

    for line in lines:
        m = _WAKEUP_SRC_RE.match(line)
        if not m or m.group("name") == "name":  # skip header
            continue
        entry = {
            "name": m.group("name"),
            "active_count": int(m.group("active_count")),
            "wakeup_count": int(m.group("wakeup_count")),
            "active_since_ms": int(m.group("active_since")),
        }
        sources.append(entry)
        if entry["active_since_ms"] > 0:
            active.append(entry)

    # Sort by wakeup_count descending
    sources.sort(key=lambda x: x["wakeup_count"], reverse=True)
    active.sort(key=lambda x: x["active_since_ms"], reverse=True)

    result: dict[str, Any] = {
        "total_sources": len(sources),
        "active_sources": active,
        "top_wakeup_sources": sources[:10],
    }

    if active:
        result["diagnosis"] = (
            f"{len(active)} wakeup source(s) currently active — these will block STR entry. "
            f"Most persistent: '{active[0]['name']}' (active for {active[0]['active_since_ms']} ms). "
            "Use 'echo 0 > /sys/power/wake_lock' only after confirming the source is safe to release."
        )
    else:
        result["diagnosis"] = "No currently active wakeup sources. Suspend should not be blocked by wakeup_source."

    return result


def _read_pm_wakeup_irq(path: str) -> dict[str, Any]:
    """Read /sys/power/pm_wakeup_irq."""
    try:
        with open(path) as f:
            irq_num = f.read().strip()
        if irq_num == "0" or not irq_num:
            return {"pm_wakeup_irq": None, "note": "No wakeup IRQ recorded (system may not have woken via IRQ)"}
        return {
            "pm_wakeup_irq": int(irq_num),
            "note": f"Last wakeup caused by IRQ {irq_num}. "
                    f"Identify with: cat /proc/interrupts | grep '^ *{irq_num}:'"
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_suspend_resume_log(
    log_path: str,
    wakeup_sources_path: str | None = None,
    pm_wakeup_irq_path: str | None = None,
) -> dict[str, Any]:
    """Parse suspend/resume related logs for STR/STD diagnosis.

    Parameters
    ----------
    log_path:
        Path to dmesg log (with pm_debug=1 ideally) or ftrace narrative log.
    wakeup_sources_path:
        Optional path to /sys/kernel/debug/wakeup_sources snapshot.
    pm_wakeup_irq_path:
        Optional path to /sys/power/pm_wakeup_irq snapshot.

    Returns
    -------
    dict with keys:
        ``pm_debug``        — driver errors, aborts, timing from dmesg
        ``wakeup_sources``  — active wakeup source analysis (if provided)
        ``last_wakeup_irq`` — last wakeup IRQ (if provided)
        ``summary``         — top-line diagnosis
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    result: dict[str, Any] = {
        "file": log_path,
        "lines_parsed": len(lines),
        "pm_debug": _parse_pm_debug_dmesg(lines),
    }

    if wakeup_sources_path:
        ws_path = os.path.abspath(wakeup_sources_path)
        if os.path.isfile(ws_path):
            with open(ws_path, "r", errors="replace") as fh:
                ws_lines = fh.readlines()
            result["wakeup_sources"] = _parse_wakeup_sources(ws_lines)

    if pm_wakeup_irq_path:
        result["last_wakeup_irq"] = _read_pm_wakeup_irq(pm_wakeup_irq_path)

    # Build summary
    pm = result["pm_debug"]
    if pm.get("errors"):
        result["summary"] = f"DRIVER FAILURE: {pm['errors'][0]['driver']} failed to {pm['errors'][0]['action']}."
    elif pm.get("freeze_failed"):
        result["summary"] = "FREEZE FAILURE: kernel thread not responding to freezer."
    elif pm.get("aborts"):
        result["summary"] = "SUSPEND ABORTED: wakeup event pending at suspend time."
    else:
        result["summary"] = "No critical PM errors found in log."

    return result


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python suspend_resume_parser.py <dmesg_log> [wakeup_sources] [pm_wakeup_irq]")
        sys.exit(1)
    args = sys.argv[1:]
    print(json.dumps(parse_suspend_resume_log(*args), indent=2))
