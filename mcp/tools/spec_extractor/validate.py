"""
Register Validation — spot-check extracted register addresses against known-good values.

Validates extracted register definitions by:
  1. Checking address format (valid hex string)
  2. Checking bit field ranges (LSB ≤ MSB, both in [0, size-1])
  3. Checking access type strings against the allowed set
  4. Comparing addresses against a caller-supplied known-good reference dict

Usage::

    from mcp.tools.spec_extractor.validate import validate_registers
    result = validate_registers(registers, {"CTRL_REG": "0x1000"})
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed access type values (canonical)
# ---------------------------------------------------------------------------

_VALID_ACCESS_TYPES = frozenset([
    "RW", "RO", "WO", "RC", "RS", "W1C", "W1S", "W0C", "W0S",
    "read-write", "read-only", "write-only",
])

_HEX_RE = re.compile(r"^0[xX][0-9A-Fa-f]+$")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _is_valid_hex(value: str) -> bool:
    """Return True if *value* is a non-empty hex string (``0x…``)."""
    if not value:
        return False
    return bool(_HEX_RE.match(value.strip()))


def _validate_bit_field(bf: dict, reg_size: int) -> list[str]:
    """Return a list of error strings for a single bit field dict."""
    errors = []
    msb = bf.get("msb")
    lsb = bf.get("lsb")
    bit_width = bf.get("bit_width")

    if msb is None or lsb is None:
        errors.append(f"bit_field '{bf.get('name')}': missing msb/lsb")
        return errors

    if lsb > msb:
        errors.append(f"bit_field '{bf.get('name')}': lsb ({lsb}) > msb ({msb})")
    if msb >= reg_size:
        errors.append(
            f"bit_field '{bf.get('name')}': msb ({msb}) >= register size ({reg_size})"
        )
    if lsb < 0:
        errors.append(f"bit_field '{bf.get('name')}': lsb ({lsb}) < 0")

    if bit_width is not None and bit_width != (msb - lsb + 1):
        errors.append(
            f"bit_field '{bf.get('name')}': declared bit_width ({bit_width}) "
            f"!= msb-lsb+1 ({msb - lsb + 1})"
        )

    access = bf.get("access", "")
    if access and access not in _VALID_ACCESS_TYPES:
        errors.append(f"bit_field '{bf.get('name')}': unknown access type '{access}'")

    return errors


def _validate_single_register(reg: dict, known_good: dict[str, str]) -> dict:
    """Validate a single register dict.

    Returns a result dict with keys: ``name``, ``passed``, ``errors``.
    """
    name = reg.get("name", "UNKNOWN")
    address = reg.get("address", "")
    size = reg.get("size", 32)
    access = reg.get("access", "")
    bit_fields = reg.get("bit_fields", [])
    errors: list[str] = []

    # 1. Address format
    if not _is_valid_hex(address):
        errors.append(f"address '{address}' is not a valid hex string")

    # 2. Access type
    if access and access not in _VALID_ACCESS_TYPES:
        errors.append(f"unknown access type '{access}'")

    # 3. Bit field ranges
    for bf in bit_fields:
        errors.extend(_validate_bit_field(bf, size))

    # 4. Known-good address comparison
    if name in known_good:
        expected = known_good[name].strip().lower()
        actual = address.strip().lower()
        # Normalise: ensure both start with 0x
        if not expected.startswith("0x"):
            expected = "0x" + expected
        if actual != expected:
            errors.append(
                f"address mismatch: extracted={actual!r} expected={expected!r}"
            )

    return {
        "name": name,
        "address": address,
        "passed": len(errors) == 0,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_registers(
    registers: list[dict[str, Any]],
    known_good: dict[str, str],
) -> dict[str, Any]:
    """Validate extracted register definitions against known-good values.

    Parameters
    ----------
    registers:
        List of register dicts as returned by :func:`extract_registers` or
        :func:`parse_ipxact`.  Each dict must have at minimum: ``name``,
        ``address``, ``size``, ``access``, ``bit_fields``.
    known_good:
        Mapping of ``{register_name: expected_hex_address}``.
        Example: ``{"CTRL_REG": "0x1000", "STATUS_REG": "0x1004"}``.

    Returns
    -------
    dict
        Structure::

            {
                "passed": [list of passing register dicts],
                "failed": [list of failing register dicts with "errors" key],
                "coverage": float,        # fraction of known_good entries found
                "total": int,
                "pass_count": int,
                "fail_count": int,
            }
    """
    passed: list[dict] = []
    failed: list[dict] = []
    found_known_good: set[str] = set()

    for reg in registers:
        name = reg.get("name", "")
        result = _validate_single_register(reg, known_good)
        if name in known_good:
            found_known_good.add(name)
        if result["passed"]:
            passed.append(result)
        else:
            failed.append(result)
            logger.debug("Register %s failed validation: %s", name, result["errors"])

    coverage = len(found_known_good) / len(known_good) if known_good else 1.0

    summary = {
        "passed": passed,
        "failed": failed,
        "coverage": round(coverage, 4),
        "total": len(registers),
        "pass_count": len(passed),
        "fail_count": len(failed),
        "known_good_found": list(found_known_good),
        "known_good_missing": [k for k in known_good if k not in found_known_good],
    }

    logger.info(
        "validate_registers: %d/%d passed, coverage=%.1f%%",
        len(passed), len(registers), coverage * 100,
    )
    return summary
