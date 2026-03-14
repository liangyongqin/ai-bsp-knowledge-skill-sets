"""
PMIC log parser — voltage rail ramp events and sequence violations from kernel log.

Parses dmesg for:
  - Regulator enable/disable events (Linux regulator framework)
  - OCP (Over-Current Protection) events
  - Voltage setting changes
  - Supply sequence order (used to detect VDD_IO before VDD_CORE violations)
"""

from __future__ import annotations

import re
import os
from typing import Any

# Regulator enable: "regulator-name: enabled"  or  "reg-name: is now enabled"
_REG_ENABLE_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?P<reg>[\w\-\.]+):\s+(?:is now\s+)?(?P<state>enabled|disabled)"
)

# Voltage set: "regulator-name: set voltage ... to N uV"
_VOLT_SET_RE = re.compile(
    r"(?P<reg>[\w\-\.]+):\s+set\s+voltage.*?(?P<uv>\d+)\s*uV"
)

# OCP event: "regulator: REGULATOR_EVENT_OCP"  or  "ocp event"
_OCP_RE = re.compile(r"(?:OCP|over.current|overcurrent)", re.IGNORECASE)

# Generic regulator error
_REG_ERROR_RE = re.compile(
    r"regulator[^:]*:\s+(?P<reg>[\w\-]+).*?(?P<err>error|failed|can't|cannot|unable)",
    re.IGNORECASE
)

# Sequence order tracking patterns
_CORE_KEYWORDS = ("vdd_core", "vdd-core", "buck1", "vcpu", "vcore", "dvdd_core")
_IO_KEYWORDS   = ("vdd_io", "vdd-io", "ldo_io", "vccio", "vddio")
_ANA_KEYWORDS  = ("vdd_ana", "vdd-ana", "avdd", "vana", "ana_supply")


def _classify_rail(name: str) -> str:
    nl = name.lower()
    if any(k in nl for k in _CORE_KEYWORDS):
        return "CORE"
    if any(k in nl for k in _IO_KEYWORDS):
        return "IO"
    if any(k in nl for k in _ANA_KEYWORDS):
        return "ANA"
    return "OTHER"


def parse_pmic_log(log_path: str) -> dict[str, Any]:
    """Parse a kernel dmesg log for PMIC / regulator events.

    Parameters
    ----------
    log_path:
        Path to dmesg output file.

    Returns
    -------
    dict with keys:
        ``enable_sequence``    — ordered list of rail enable events
        ``ocp_events``         — over-current protection lines
        ``voltage_changes``    — voltage set events
        ``sequence_violations``— detected CORE/IO/ANA ordering issues
        ``errors``             — regulator error lines
        ``diagnosis``          — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    enable_seq: list[dict] = []
    ocp_events: list[str] = []
    volt_changes: list[dict] = []
    errors: list[str] = []

    for line in lines:
        # Enable/disable
        m = _REG_ENABLE_RE.search(line)
        if m and m.group("state") in ("enabled", "disabled"):
            rail = m.group("reg")
            enable_seq.append({
                "rail": rail,
                "state": m.group("state"),
                "rail_class": _classify_rail(rail),
            })

        # Voltage set
        m = _VOLT_SET_RE.search(line)
        if m:
            volt_changes.append({
                "rail": m.group("reg"),
                "voltage_uv": int(m.group("uv")),
            })

        # OCP
        if _OCP_RE.search(line):
            ocp_events.append(line.strip())

        # Errors
        m = _REG_ERROR_RE.search(line)
        if m:
            errors.append(line.strip())

    # Detect sequence violations: IO or ANA enabled before first CORE enable
    violations: list[str] = []
    core_enabled = False
    for ev in enable_seq:
        if ev["state"] != "enabled":
            continue
        if ev["rail_class"] == "CORE":
            core_enabled = True
        elif ev["rail_class"] in ("IO", "ANA") and not core_enabled:
            violations.append(
                f"SEQUENCE VIOLATION: '{ev['rail']}' ({ev['rail_class']}) "
                "enabled before VDD_CORE — latch-up risk!"
            )

    diagnosis = "No critical PMIC events detected."
    if violations:
        diagnosis = (
            f"{len(violations)} power sequencing violation(s) detected! "
            f"{violations[0]} "
            "Correct order: VDD_CORE → VDD_IO → VDD_ANA. "
            "Escalate to /boot-debug-expert for hardware bring-up review."
        )
    elif ocp_events:
        diagnosis = (
            f"{len(ocp_events)} OCP event(s) detected. "
            "Check BUCK inductor current rating and load transient profile. "
            "Escalate to /power-thermal-expert for DVFS/load analysis."
        )
    elif errors:
        diagnosis = f"{len(errors)} regulator error(s) in log. First: {errors[0][:120]}"

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "enable_sequence": enable_seq,
        "ocp_events": ocp_events[:10],
        "voltage_changes": volt_changes[:20],
        "sequence_violations": violations,
        "errors": errors[:10],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python pmic_log_parser.py <dmesg_log>")
        sys.exit(1)
    print(json.dumps(parse_pmic_log(sys.argv[1]), indent=2))
