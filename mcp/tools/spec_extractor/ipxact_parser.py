"""
IP-XACT Parser — extract structured register/component data from Accellera IP-XACT XML.

Supports Accellera IP-XACT 2022 standard (IEEE 1685-2022) as well as the
widely-deployed 2014 revision.

Extracted structure:
  - Component hierarchy (component → memoryMaps → addressBlocks → registers)
  - Register maps with address offsets and sizes
  - Bit fields with reset values and access types
  - Bus interface definitions

Reference: Accellera IP-XACT 2022 Standard (https://www.accellera.org/downloads/standards/ip-xact)

Usage::

    from mcp.tools.spec_extractor.ipxact_parser import parse_ipxact
    data = parse_ipxact("/path/to/component.xml")
"""

import os
import re
import logging
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# XML namespace maps — IP-XACT 2022 and 2014
# ---------------------------------------------------------------------------

_NS_2022 = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
_NS_2014 = "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"
_NS_LEGACY = "spirit"  # IP-XACT 2009 / legacy

_KNOWN_NAMESPACES = [_NS_2022, _NS_2014]


def _detect_namespace(root: ET.Element) -> str:
    """Detect the IP-XACT XML namespace from the root element tag."""
    tag = root.tag
    m = re.match(r"\{(.+?)\}", tag)
    if m:
        return m.group(1)
    return ""


def _q(ns: str, local: str) -> str:
    """Build a qualified tag name: ``{namespace}localName``."""
    if ns:
        return f"{{{ns}}}{local}"
    return local


def _get_text(elem: ET.Element, tag: str, ns: str, default: str = "") -> str:
    """Find a direct child element and return its stripped text."""
    child = elem.find(_q(ns, tag))
    if child is not None and child.text:
        return child.text.strip()
    return default


def _parse_int(val: str) -> int:
    """Parse decimal or hex integer string."""
    val = val.strip().lower().replace("_", "")
    if val.startswith("0x"):
        return int(val, 16)
    if val.startswith("#"):
        # IP-XACT uses #hex notation sometimes
        return int(val[1:], 16)
    try:
        return int(val)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Parsers for individual structural levels
# ---------------------------------------------------------------------------

def _parse_bit_field(field_elem: ET.Element, ns: str) -> dict:
    """Parse a single <field> element into a dict."""
    name = _get_text(field_elem, "name", ns, "unnamed")
    description = _get_text(field_elem, "description", ns)
    bit_offset_str = _get_text(field_elem, "bitOffset", ns, "0")
    bit_width_str = _get_text(field_elem, "bitWidth", ns, "1")
    access = _get_text(field_elem, "access", ns, "read-write")
    reset_value_str = _get_text(field_elem, "resets", ns, "")

    # reset value may be nested under <resets><reset><value>
    reset_elem = field_elem.find(f".//{_q(ns, 'value')}")
    if reset_elem is not None and reset_elem.text:
        reset_value_str = reset_elem.text.strip()

    try:
        bit_offset = _parse_int(bit_offset_str)
        bit_width = _parse_int(bit_width_str)
    except Exception:
        bit_offset, bit_width = 0, 1

    return {
        "name": name,
        "description": description,
        "bit_offset": bit_offset,
        "bit_width": bit_width,
        "access": access,
        "reset_value": reset_value_str,
        "msb": bit_offset + bit_width - 1,
        "lsb": bit_offset,
    }


def _parse_register(reg_elem: ET.Element, ns: str, base_address: int = 0) -> dict:
    """Parse a single <register> element into a dict."""
    name = _get_text(reg_elem, "name", ns, "UNKNOWN_REG")
    description = _get_text(reg_elem, "description", ns)
    address_offset_str = _get_text(reg_elem, "addressOffset", ns, "0x0")
    size_str = _get_text(reg_elem, "size", ns, "32")
    access = _get_text(reg_elem, "access", ns, "read-write")
    reset_value_str = _get_text(reg_elem, "resetValue", ns, "0x0")

    try:
        address_offset = _parse_int(address_offset_str)
        size = _parse_int(size_str)
    except Exception:
        address_offset, size = 0, 32

    absolute_address = base_address + address_offset

    bit_fields = []
    for field_elem in reg_elem.findall(_q(ns, "field")):
        bit_fields.append(_parse_bit_field(field_elem, ns))

    return {
        "name": name,
        "description": description,
        "address_offset": hex(address_offset),
        "absolute_address": hex(absolute_address),
        "size": size,
        "access": access,
        "reset_value": reset_value_str,
        "bit_fields": bit_fields,
    }


def _parse_address_block(block_elem: ET.Element, ns: str) -> dict:
    """Parse an <addressBlock> element."""
    name = _get_text(block_elem, "name", ns, "default")
    base_addr_str = _get_text(block_elem, "baseAddress", ns, "0x0")
    usage = _get_text(block_elem, "usage", ns, "register")

    try:
        base_address = _parse_int(base_addr_str)
    except Exception:
        base_address = 0

    registers = []
    for reg_elem in block_elem.findall(_q(ns, "register")):
        registers.append(_parse_register(reg_elem, ns, base_address))

    return {
        "name": name,
        "base_address": hex(base_address),
        "usage": usage,
        "registers": registers,
    }


def _parse_memory_map(mm_elem: ET.Element, ns: str) -> dict:
    """Parse a <memoryMap> element."""
    name = _get_text(mm_elem, "name", ns, "default")
    address_blocks = []
    for block_elem in mm_elem.findall(_q(ns, "addressBlock")):
        address_blocks.append(_parse_address_block(block_elem, ns))
    return {"name": name, "address_blocks": address_blocks}


def _parse_bus_interface(bi_elem: ET.Element, ns: str) -> dict:
    """Parse a <busInterface> element."""
    name = _get_text(bi_elem, "name", ns, "unnamed")
    bus_type_elem = bi_elem.find(_q(ns, "busType"))
    bus_type = ""
    if bus_type_elem is not None:
        vendor = bus_type_elem.get("vendor", "")
        library = bus_type_elem.get("library", "")
        bus_name = bus_type_elem.get("name", "")
        bus_type = f"{vendor}:{library}:{bus_name}"
    interface_mode_elem = bi_elem.find(_q(ns, "interfaceMode"))
    mode = ""
    if interface_mode_elem is not None and interface_mode_elem.text:
        mode = interface_mode_elem.text.strip()
    else:
        # Detect master/slave from child elements
        for candidate in ("master", "slave", "mirroredMaster", "mirroredSlave"):
            if bi_elem.find(_q(ns, candidate)) is not None:
                mode = candidate
                break
    return {"name": name, "bus_type": bus_type, "mode": mode}


def _parse_component(comp_elem: ET.Element, ns: str) -> dict:
    """Parse a top-level <component> element."""
    name = _get_text(comp_elem, "name", ns, "unnamed")
    vendor = _get_text(comp_elem, "vendor", ns)
    version = _get_text(comp_elem, "version", ns)
    description = _get_text(comp_elem, "description", ns)

    memory_maps = []
    for mm_elem in comp_elem.findall(f".//{_q(ns, 'memoryMap')}"):
        memory_maps.append(_parse_memory_map(mm_elem, ns))

    bus_interfaces = []
    for bi_elem in comp_elem.findall(_q(ns, "busInterfaces")):
        for interface in bi_elem.findall(_q(ns, "busInterface")):
            bus_interfaces.append(_parse_bus_interface(interface, ns))

    return {
        "name": name,
        "vendor": vendor,
        "version": version,
        "description": description,
        "memory_maps": memory_maps,
        "bus_interfaces": bus_interfaces,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ipxact(path: str) -> dict[str, Any]:
    """Parse an Accellera IP-XACT XML file into a structured dict.

    Supports IP-XACT 2022 (IEEE 1685-2022) and 2014 revisions.

    Parameters
    ----------
    path:
        Absolute or relative path to the IP-XACT XML file.

    Returns
    -------
    dict
        Structure::

            {
                "components": [...],
                "registers": [...],     # flat list across all components
                "bit_fields": [...],    # flat list across all registers
            }

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file is not a valid IP-XACT document.
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"IP-XACT file not found: {path}")

    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError(f"XML parse error in {path}: {exc}") from exc

    root = tree.getroot()
    ns = _detect_namespace(root)

    if ns not in _KNOWN_NAMESPACES:
        logger.warning(
            "Unknown IP-XACT namespace '%s'. Attempting parse with empty namespace.", ns
        )

    tag_local = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag_local not in ("component", "design", "catalog", "abstractionDefinition"):
        raise ValueError(
            f"Root element '{tag_local}' is not a recognised IP-XACT root. "
            "Expected: component, design, catalog, abstractionDefinition."
        )

    components: list[dict] = []
    if tag_local == "component":
        components.append(_parse_component(root, ns))
    else:
        for comp_elem in root.findall(f".//{_q(ns, 'component')}"):
            components.append(_parse_component(comp_elem, ns))

    # Build flat register and bit-field lists for convenience
    all_registers: list[dict] = []
    all_bit_fields: list[dict] = []

    for comp in components:
        for mm in comp.get("memory_maps", []):
            for ab in mm.get("address_blocks", []):
                for reg in ab.get("registers", []):
                    reg_entry = {**reg, "component": comp["name"], "memory_map": mm["name"]}
                    all_registers.append(reg_entry)
                    for bf in reg.get("bit_fields", []):
                        all_bit_fields.append({**bf, "register": reg["name"], "component": comp["name"]})

    return {
        "components": components,
        "registers": all_registers,
        "bit_fields": all_bit_fields,
    }
