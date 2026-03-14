"""
Register Extractor — heuristic register table extraction from non-IP-XACT PDFs.

Uses regex patterns and pdfplumber table detection to extract register
definitions from SoC Technical Reference Manuals that are not in IP-XACT
format.

Heuristics applied:
  - Rows in tables containing hex addresses (0x notation)
  - Rows describing bit ranges ([x:y] or individual bits)
  - Access type strings (RW, RO, WO, RC, RS, W1C, etc.)
  - Register name patterns (ALL_CAPS_WITH_UNDERSCORES)

Usage::

    from mcp.tools.spec_extractor.register_extractor import extract_registers
    registers = extract_registers("/path/to/soc_trm.pdf")
"""

import os
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for heuristic detection
# ---------------------------------------------------------------------------

_HEX_ADDR_RE = re.compile(r"\b0[xX][0-9A-Fa-f]{2,8}\b")
_REG_NAME_RE = re.compile(r"\b([A-Z][A-Z0-9_]{3,40})\b")
_BIT_RANGE_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})\]|\bBit\s+(\d{1,2})\b", re.IGNORECASE)
_ACCESS_TYPE_RE = re.compile(
    r"\b(RW|RO|WO|RC|RS|W1C|W1S|W0C|W0S|R/W|R/O|W/O|Read-Write|Read-Only|Write-Only)\b",
    re.IGNORECASE,
)
_RESET_VALUE_RE = re.compile(r"Reset\s*[=:]\s*(0[xX][0-9A-Fa-f]+|\d+)", re.IGNORECASE)


def _normalise_access(raw: str) -> str:
    """Normalise access type string to a canonical form."""
    mapping = {
        "r/w": "RW", "read-write": "RW", "rw": "RW",
        "r/o": "RO", "read-only": "RO", "ro": "RO",
        "w/o": "WO", "write-only": "WO", "wo": "WO",
        "rc": "RC", "rs": "RS", "w1c": "W1C", "w1s": "W1S",
    }
    return mapping.get(raw.lower(), raw.upper())


def _looks_like_register_row(cells: list[str]) -> bool:
    """Return True if a table row looks like it defines a register."""
    row_text = " ".join(str(c) for c in cells if c)
    has_hex = bool(_HEX_ADDR_RE.search(row_text))
    has_reg_name = bool(_REG_NAME_RE.search(row_text))
    return has_hex and has_reg_name


def _extract_from_table(table: list[list[str | None]], page_num: int) -> list[dict]:
    """Extract register definitions from a pdfplumber table."""
    registers = []
    if not table or len(table) < 2:
        return registers

    # Try to identify header row
    header = [str(c).strip().lower() if c else "" for c in table[0]]
    addr_col = next(
        (i for i, h in enumerate(header) if "offset" in h or "addr" in h), None
    )
    name_col = next(
        (i for i, h in enumerate(header) if "name" in h or "register" in h), None
    )
    desc_col = next(
        (i for i, h in enumerate(header) if "desc" in h or "description" in h), None
    )
    access_col = next(
        (i for i, h in enumerate(header) if "access" in h or "type" in h), None
    )
    reset_col = next(
        (i for i, h in enumerate(header) if "reset" in h or "default" in h), None
    )

    for row in table[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        row_str = [str(c).strip() if c else "" for c in row]
        row_text = " ".join(row_str)

        # Address
        address = ""
        if addr_col is not None and addr_col < len(row_str):
            address = row_str[addr_col]
        if not address:
            m = _HEX_ADDR_RE.search(row_text)
            address = m.group(0) if m else ""

        # Register name
        name = ""
        if name_col is not None and name_col < len(row_str):
            name = row_str[name_col]
        if not name:
            m = _REG_NAME_RE.search(row_text)
            name = m.group(1) if m else f"REG_{address}"

        if not address and not name:
            continue

        # Description
        description = ""
        if desc_col is not None and desc_col < len(row_str):
            description = row_str[desc_col]
        if not description:
            description = row_text[:100]

        # Access type
        access = "RW"
        if access_col is not None and access_col < len(row_str):
            access = _normalise_access(row_str[access_col]) if row_str[access_col] else "RW"
        else:
            m = _ACCESS_TYPE_RE.search(row_text)
            if m:
                access = _normalise_access(m.group(1))

        # Reset value
        reset_value = "0x0"
        if reset_col is not None and reset_col < len(row_str):
            reset_value = row_str[reset_col] or "0x0"
        else:
            m = _RESET_VALUE_RE.search(row_text)
            if m:
                reset_value = m.group(1)

        registers.append({
            "name": name,
            "address": address,
            "size": 32,
            "description": description,
            "access": access,
            "reset_value": reset_value,
            "page": page_num,
            "bit_fields": [],
        })

    return registers


def _extract_bit_fields_from_text(text: str, reg_name: str) -> list[dict]:
    """Heuristically extract bit field definitions from free-form text."""
    bit_fields = []
    lines = text.splitlines()
    for line in lines:
        m_range = _BIT_RANGE_RE.search(line)
        if not m_range:
            continue
        if m_range.group(1) is not None:
            msb, lsb = int(m_range.group(1)), int(m_range.group(2))
        else:
            msb = lsb = int(m_range.group(3))

        m_access = _ACCESS_TYPE_RE.search(line)
        access = _normalise_access(m_access.group(1)) if m_access else "RW"

        m_name = _REG_NAME_RE.search(line)
        field_name = m_name.group(1) if m_name else f"BIT_{lsb}"

        bit_fields.append({
            "name": field_name,
            "msb": msb,
            "lsb": lsb,
            "bit_width": msb - lsb + 1,
            "access": access,
            "description": line.strip()[:120],
        })
    return bit_fields


def _merge_bit_fields(registers: list[dict], page_texts: dict[int, str]) -> list[dict]:
    """Enrich register list with bit fields found in nearby page text."""
    for reg in registers:
        page = reg.get("page", 0)
        text = page_texts.get(page, "")
        if text and reg["name"] in text:
            # Look for bit field lines after the register name mention
            idx = text.find(reg["name"])
            snippet = text[idx: idx + 2000]
            reg["bit_fields"] = _extract_bit_fields_from_text(snippet, reg["name"])
    return registers


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_registers(pdf_path: str) -> list[dict[str, Any]]:
    """Heuristically extract register definitions from a non-IP-XACT PDF.

    Uses pdfplumber table detection and regex heuristics to identify
    register tables, addresses, access types, and bit field descriptions.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file (TRM, register reference manual, etc.).

    Returns
    -------
    list[dict]
        Each register dict has keys:
        ``name``, ``address``, ``size``, ``description``,
        ``access``, ``reset_value``, ``page``, ``bit_fields``.

    Raises
    ------
    FileNotFoundError
        If *pdf_path* does not exist.
    """
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required: pip install pdfplumber")

    registers: list[dict] = []
    page_texts: dict[int, str] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Cache page text for bit-field enrichment
            try:
                text = page.extract_text() or ""
                page_texts[page_num] = text
            except Exception:
                page_texts[page_num] = ""

            # Extract from tables
            try:
                tables = page.extract_tables()
                for table in tables or []:
                    regs = _extract_from_table(table, page_num)
                    registers.extend(regs)
            except Exception as exc:
                logger.debug("Table extraction error page %d: %s", page_num, exc)

            # Also scan free-form text for register definitions
            text = page_texts.get(page_num, "")
            if text:
                for m in _HEX_ADDR_RE.finditer(text):
                    addr = m.group(0)
                    # Look for a register name in the surrounding context
                    start = max(0, m.start() - 60)
                    end = min(len(text), m.end() + 80)
                    context = text[start:end]
                    name_m = _REG_NAME_RE.search(context)
                    if name_m:
                        name = name_m.group(1)
                        # Avoid duplicates
                        if not any(r["address"] == addr and r["name"] == name for r in registers):
                            access_m = _ACCESS_TYPE_RE.search(context)
                            registers.append({
                                "name": name,
                                "address": addr,
                                "size": 32,
                                "description": context.strip()[:120],
                                "access": _normalise_access(access_m.group(1)) if access_m else "RW",
                                "reset_value": "0x0",
                                "page": page_num,
                                "bit_fields": [],
                            })

    # Enrich with bit field info from page text
    registers = _merge_bit_fields(registers, page_texts)

    # Deduplicate by (name, address)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for reg in registers:
        key = (reg["name"], reg["address"])
        if key not in seen:
            seen.add(key)
            unique.append(reg)

    logger.info("extract_registers: found %d unique registers in %s", len(unique), os.path.basename(pdf_path))
    return unique
