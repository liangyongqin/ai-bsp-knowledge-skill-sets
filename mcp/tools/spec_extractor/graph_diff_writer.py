"""
Graph Diff Writer — idempotent Kuzu write for spec extractor output.

Converts the structured dict produced by ``parse_ipxact()`` or ``pdf_ingest()``
into Kuzu graph nodes and relationships under ``namespace="custom"``.

Behaviour:
  - Uses ``upsert_node()`` from ``_ingest_helpers`` — silently skips nodes
    whose primary key already exists (idempotent).
  - Computes a diff summary: how many nodes were new vs already present.
  - Validates the structured dict against a minimal schema before writing.
  - Never writes ``namespace="base"`` nodes — all custom data is isolated.

Usage::

    from mcp.tools.spec_extractor.graph_diff_writer import write_to_graph, validate_spec_dict

    data = parse_ipxact("/path/to/component.xml")
    errors = validate_spec_dict(data)
    if not errors:
        result = write_to_graph(data, db_path="/path/to/custom.db", soc_name="mt6989")
        print(result)
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup — find _ingest_helpers relative to repo root
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..", "..")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")

for _p in (_BASE_DIR, _SCHEMA_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_ACCESS_TYPES = {"read-write", "read-only", "write-only", "read-writeOnce", "writeOnce"}

_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$|^\d+$")


def validate_spec_dict(data: dict) -> list[str]:
    """Validate a structured spec dict before writing to the graph.

    Parameters
    ----------
    data:
        Dict returned by ``parse_ipxact()`` or ``pdf_ingest()``.
        Expected keys: ``components``, ``registers``, ``bit_fields``.

    Returns
    -------
    list[str]
        List of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["data must be a dict"]

    components = data.get("components", [])
    registers = data.get("registers", [])
    bit_fields = data.get("bit_fields", [])

    if not components and not registers:
        errors.append("No components or registers found — nothing to write")
        return errors

    # Validate registers
    seen_addresses: dict[str, str] = {}  # address → reg_name
    for reg in registers:
        name = reg.get("name", "")
        addr = reg.get("absolute_address", reg.get("address", ""))
        access = reg.get("access", "read-write")
        size = reg.get("size", 32)

        if not name:
            errors.append(f"Register missing name: {reg}")
        if addr and not _HEX_RE.match(str(addr)):
            errors.append(f"Register '{name}' has invalid address format: {addr}")
        if addr and addr in seen_addresses and seen_addresses[addr] != name:
            errors.append(
                f"Address overlap: register '{name}' and '{seen_addresses[addr]}' "
                f"both at {addr}"
            )
        if addr:
            seen_addresses[addr] = name
        if access not in _ACCESS_TYPES:
            errors.append(
                f"Register '{name}' has unknown access type '{access}'. "
                f"Expected one of: {', '.join(sorted(_ACCESS_TYPES))}"
            )
        if not isinstance(size, int) or size not in (8, 16, 32, 64):
            errors.append(f"Register '{name}' has unusual size {size} (expected 8/16/32/64)")

    # Validate bit fields
    for bf in bit_fields:
        reg_name = bf.get("register", "?")
        field_name = bf.get("name", "?")
        bit_offset = bf.get("bit_offset", 0)
        bit_width = bf.get("bit_width", 1)
        msb = bf.get("msb", bit_offset + bit_width - 1)

        if msb >= 64:
            errors.append(
                f"Field '{field_name}' in register '{reg_name}' has MSB={msb} "
                "which exceeds maximum register width (64 bits)"
            )
        if bit_width < 1:
            errors.append(f"Field '{field_name}' in '{reg_name}' has invalid width {bit_width}")

    return errors


# ---------------------------------------------------------------------------
# Graph writer
# ---------------------------------------------------------------------------

def write_to_graph(
    data: dict,
    db_path: str,
    soc_name: str = "custom",
    component_name: str | None = None,
) -> dict[str, Any]:
    """Write spec extractor output to the Kuzu knowledge graph.

    All nodes are written with ``namespace="custom"`` so they never pollute
    the ``base`` open-source knowledge. Existing nodes with the same primary
    key are silently skipped (idempotent).

    Parameters
    ----------
    data:
        Structured dict from ``parse_ipxact()`` or ``pdf_ingest()``.
    db_path:
        Path to the Kuzu database directory.
    soc_name:
        SoC identifier (e.g. ``"mt6989"``). Used in component description.
    component_name:
        Override for the top-level component name. If ``None``, taken from
        the first entry in ``data["components"]``.

    Returns
    -------
    dict
        ``{new_nodes, skipped_nodes, new_relationships, errors}``
    """
    try:
        import kuzu
        import schema as _schema
        from _ingest_helpers import upsert_node, create_rel
    except ImportError as e:
        return {"error": f"Missing dependency: {e}. Run: pip install kuzu"}

    db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    new_nodes = 0
    skipped_nodes = 0
    new_rels = 0
    write_errors: list[str] = []

    components = data.get("components", [])
    registers = data.get("registers", [])

    # Determine top-level component name
    top_comp_name = component_name
    if not top_comp_name and components:
        top_comp_name = components[0].get("name", "unknown-ip")
    if not top_comp_name:
        top_comp_name = "unknown-ip"

    # Write top-level Component node
    comp_desc = f"{soc_name} — {top_comp_name} IP block (custom namespace)"
    if components:
        c = components[0]
        if c.get("description"):
            comp_desc = c["description"]

    if upsert_node(conn, "Component", {
        "name": top_comp_name,
        "type": "ip-block",
        "namespace": "custom",
        "vendor": soc_name,
        "version": components[0].get("version", "") if components else "",
        "description": comp_desc,
    }):
        new_nodes += 1
    else:
        skipped_nodes += 1

    # Write Register nodes and link to Component
    for reg in registers:
        reg_name = reg.get("name", "")
        if not reg_name:
            continue

        # Qualify register name with component to avoid collisions between IPs
        qualified_name = f"{top_comp_name}::{reg_name}"
        addr = reg.get("absolute_address", reg.get("address", "0x0"))
        access = reg.get("access", "read-write")
        reset_val = reg.get("reset_value", "0x0")

        try:
            addr_int = int(str(addr), 16) if str(addr).startswith("0x") else int(str(addr))
        except ValueError:
            addr_int = 0

        if upsert_node(conn, "Register", {
            "name": qualified_name,
            "address": addr_int,
            "access_type": access,
            "reset_value": str(reset_val),
            "component": top_comp_name,
            "namespace": "custom",
        }):
            new_nodes += 1
        else:
            skipped_nodes += 1

    # Write bus interfaces as sub-Component nodes
    if components:
        for c in components:
            for bi in c.get("bus_interfaces", []):
                bi_name = f"{top_comp_name}::busif::{bi['name']}"
                bi_desc = f"Bus interface {bi['name']} type={bi.get('bus_type', '?')} mode={bi.get('mode', '?')}"
                if upsert_node(conn, "Component", {
                    "name": bi_name,
                    "type": "bus-interface",
                    "namespace": "custom",
                    "vendor": soc_name,
                    "version": "",
                    "description": bi_desc,
                }):
                    new_nodes += 1
                    # Link bus interface to parent component
                    try:
                        create_rel(conn, "ROUTES_TO", "Component", "Component",
                                   src_name=bi_name, dst_name=top_comp_name)
                        new_rels += 1
                    except Exception as e:
                        write_errors.append(f"Rel error for {bi_name}: {e}")
                else:
                    skipped_nodes += 1

    result = {
        "db_path": db_path,
        "component": top_comp_name,
        "namespace": "custom",
        "new_nodes": new_nodes,
        "skipped_nodes": skipped_nodes,
        "new_relationships": new_rels,
        "total_registers": len(registers),
        "errors": write_errors,
        "diagnosis": (
            f"Wrote {new_nodes} new nodes ({skipped_nodes} already existed). "
            f"{len(registers)} registers processed. "
            f"Verify with: MATCH (r:Register {{namespace:'custom'}}) RETURN r.name, r.address LIMIT 10"
        ),
    }
    logger.info("[graph_diff_writer] %s", result["diagnosis"])
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Write IP-XACT/PDF spec data to Kuzu graph")
    parser.add_argument("spec_json", help="JSON file from parse_ipxact or pdf_ingest")
    parser.add_argument("--db", default="knowledge-graph/custom/custom.db", help="Kuzu DB path")
    parser.add_argument("--soc", default="custom", help="SoC name (e.g. mt6989)")
    parser.add_argument("--component", default=None, help="Override component name")
    args = parser.parse_args()

    with open(args.spec_json) as fh:
        spec_data = json.load(fh)

    errors = validate_spec_dict(spec_data)
    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        import sys as _sys
        _sys.exit(1)

    result = write_to_graph(spec_data, db_path=args.db, soc_name=args.soc,
                            component_name=args.component)
    print(json.dumps(result, indent=2))
