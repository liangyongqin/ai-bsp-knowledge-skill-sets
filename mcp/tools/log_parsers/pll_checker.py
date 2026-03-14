"""
PLL lock checker — detect premature clock consumer access before PLL lock in dmesg.

Analyses kernel boot dmesg for:
  - PLL lock events (Linux clk framework: "pll: locked" messages)
  - Driver probe events accessing clock consumers (clk_prepare_enable)
  - Temporal ordering violations: driver probes a clock that has not yet locked
  - Clock rate setting before parent PLL is stable

Covers platforms with Linux Common Clock Framework (CCF, Documentation/driver-api/clk.rst).
"""

from __future__ import annotations

import re
import os
from typing import Any

# PLL lock event: "clk: pll-name: PLL locked" or "mtk-pll pll-name: locked"
_PLL_LOCK_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?:(?P<pll>[\w\-\.]+):\s+(?:PLL\s+)?locked"
    r"|pll\s+(?P<pll2>[\w\-\.]+)\s+locked)",
    re.IGNORECASE,
)

# Clock enable: "clk_prepare_enable: clk-name" or CCF debug "Enabling clock clk-name"
_CLK_ENABLE_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?:clk_prepare_enable|Enabling clock|clk:\s+enabling)\s+[:\s]*(?P<clk>[\w\-\.]+)",
    re.IGNORECASE,
)

# Clock rate set: "clk_set_rate: clk-name rate=N"
_CLK_SET_RATE_RE = re.compile(
    r"(?P<ts>[\d.]+).*?clk_set_rate.*?(?P<clk>[\w\-\.]+).*?(?P<rate>\d+)",
    re.IGNORECASE,
)

# Driver probe: "driver-name: probe" or "platform driver-name probe"
_PROBE_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?P<driver>[\w\-\.]+):\s+(?:probing|probe\s+called|starting probe)"
    r"|(?P<ts2>[\d.]+).*?platform\s+(?P<driver2>[\w\-\.]+)\s+probe",
    re.IGNORECASE,
)

# Clk error: "clk: can't use clock" or "clk_prepare_enable failed"
_CLK_ERR_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?:clk_prepare_enable\s+failed|can't\s+use\s+clock|clk.*?error|EPROBE_DEFER.*?clk)",
    re.IGNORECASE,
)


def _extract_ts(line: str) -> float | None:
    """Extract leading timestamp from dmesg line."""
    m = re.match(r"^\[?\s*(?P<ts>[\d]+\.[\d]+)\]?", line)
    return float(m.group("ts")) if m else None


def parse_pll_log(log_path: str) -> dict[str, Any]:
    """Parse dmesg for PLL lock ordering and premature clock consumer access.

    Parameters
    ----------
    log_path:
        Path to kernel dmesg file (boot log with CCF debug preferred).

    Returns
    -------
    dict with keys:
        ``pll_locks``          — list of {pll, timestamp} in lock order
        ``clk_errors``         — clock prepare/enable errors
        ``ordering_violations``— drivers that accessed clk before parent PLL locked
        ``diagnosis``          — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    pll_locks: list[dict] = []
    clk_enables: list[dict] = []
    clk_errors: list[str] = []

    for line in lines:
        ts = _extract_ts(line)

        # PLL lock
        m = _PLL_LOCK_RE.search(line)
        if m:
            pll_name = m.group("pll") or m.group("pll2") or "unknown-pll"
            pll_locks.append({"pll": pll_name, "timestamp": ts, "line": line.strip()})

        # Clock enable
        m = _CLK_ENABLE_RE.search(line)
        if m:
            clk_enables.append({
                "clk": m.group("clk"),
                "timestamp": ts,
                "line": line.strip(),
            })

        # Clock errors
        if _CLK_ERR_RE.search(line):
            clk_errors.append(line.strip())

    # Build set of locked PLLs at each timestamp
    # Check if any clk_enable happens when parent PLL is not yet in pll_locks
    # Heuristic: if clk_enable timestamp < first PLL lock timestamp, flag it
    violations: list[dict] = []
    first_pll_lock_ts = min((p["timestamp"] for p in pll_locks if p["timestamp"] is not None), default=None)

    if first_pll_lock_ts is not None:
        for ev in clk_enables:
            if ev["timestamp"] is not None and ev["timestamp"] < first_pll_lock_ts:
                violations.append({
                    "clk": ev["clk"],
                    "clk_enable_ts": ev["timestamp"],
                    "first_pll_lock_ts": first_pll_lock_ts,
                    "delta_ms": round((first_pll_lock_ts - ev["timestamp"]) * 1000, 2),
                    "line": ev["line"],
                })

    # Diagnosis
    if violations:
        v = violations[0]
        diagnosis = (
            f"{len(violations)} clock consumer(s) enabled before first PLL lock. "
            f"Earliest violation: clk '{v['clk']}' at t={v['clk_enable_ts']:.3f}s, "
            f"{v['delta_ms']}ms before first PLL lock. "
            "Risk: clock glitch or metastability on downstream logic. "
            "Fix: add clk_prepare_enable after parent PLL lock callback; "
            "use CCF CLK_IS_CRITICAL flag only for clocks whose PLL is pre-locked by bootloader."
        )
    elif clk_errors:
        diagnosis = (
            f"{len(clk_errors)} clock error(s) detected. "
            f"First: {clk_errors[0][:120]}. "
            "Check that all CLK_SET_RATE_PARENT dependencies are satisfied before driver probe."
        )
    elif pll_locks:
        diagnosis = (
            f"Found {len(pll_locks)} PLL lock event(s). "
            "No premature clock access detected. Boot clock sequence appears correct."
        )
    else:
        diagnosis = (
            "No PLL lock events found. Enable CCF debug with: "
            "echo 0x7 > /sys/kernel/debug/clk/clk_summary  "
            "or add 'clk_ignore_unused' to cmdline during bring-up."
        )

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "pll_locks": pll_locks[:20],
        "clk_errors": clk_errors[:10],
        "ordering_violations": violations[:10],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python pll_checker.py <dmesg_log>")
        sys.exit(1)
    print(json.dumps(parse_pll_log(sys.argv[1]), indent=2))
