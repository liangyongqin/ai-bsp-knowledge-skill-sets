"""
Custom SoC Document Ingestion CLI.

Ingests proprietary SoC documentation (PDF TRMs or IP-XACT XML) into the
knowledge-graph/custom/<soc>/ namespace.  All custom data is gitignored.

Usage::

    python scripts/ingest_custom.py \\
        --input /path/to/soc_trm.pdf \\
        --soc mt6989 \\
        --format auto \\
        --verify

    python scripts/ingest_custom.py \\
        --input /path/to/registers.xml \\
        --soc mt6989 \\
        --format ipxact
"""

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")
_SPEC_EXTRACTOR_DIR = os.path.join(_REPO_ROOT, "mcp", "tools", "spec_extractor")

sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _SPEC_EXTRACTOR_DIR)


def _detect_format(input_path: str) -> str:
    """Detect document format from file extension."""
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".xml", ".ipxact", ".component"):
        return "ipxact"
    raise ValueError(
        f"Cannot auto-detect format for extension '{ext}'. "
        "Use --format pdf or --format ipxact."
    )


def _ensure_custom_dir(soc: str) -> str:
    """Create knowledge-graph/custom/<soc>/ if it does not exist."""
    custom_dir = os.path.join(_REPO_ROOT, "knowledge-graph", "custom", soc)
    os.makedirs(custom_dir, exist_ok=True)
    return custom_dir


def _get_custom_db_path(soc: str) -> str:
    """Return the Kuzu DB path for a custom SoC namespace."""
    custom_dir = _ensure_custom_dir(soc)
    return os.path.join(custom_dir, f"{soc}_custom.db")


def _write_json(data: object, path: str) -> None:
    """Write *data* as pretty-printed JSON to *path*."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _ingest_pdf(input_path: str, soc: str, verify: bool) -> None:
    """Run PDF ingestion pipeline and write extracted data."""
    from pdf_ingest import ingest_pdf
    from register_extractor import extract_registers
    from validate import validate_registers

    print(f"[ingest] Extracting text blocks from PDF: {input_path} …")
    blocks = ingest_pdf(input_path, soc)
    print(f"[ingest]   → Extracted {len(blocks)} text blocks.")

    print(f"[ingest] Extracting register definitions …")
    registers = extract_registers(input_path)
    print(f"[ingest]   → Extracted {len(registers)} register definitions.")

    # Write extracted data to custom/<soc>/
    custom_dir = _ensure_custom_dir(soc)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    blocks_path = os.path.join(custom_dir, f"{base_name}_text_blocks.json")
    registers_path = os.path.join(custom_dir, f"{base_name}_registers.json")

    _write_json(blocks, blocks_path)
    _write_json(registers, registers_path)
    print(f"[ingest]   → Wrote text blocks  : {blocks_path}")
    print(f"[ingest]   → Wrote registers     : {registers_path}")

    if verify and registers:
        print(f"[ingest] Running register validation (no known-good reference) …")
        validation = validate_registers(registers, {})
        print(
            f"[ingest]   → Passed: {validation['pass_count']}, "
            f"Failed: {validation['fail_count']}, "
            f"Coverage: {validation['coverage']:.1%}"
        )
        val_path = os.path.join(custom_dir, f"{base_name}_validation.json")
        _write_json(validation, val_path)
        print(f"[ingest]   → Wrote validation    : {val_path}")

    # Persist register nodes into custom Kuzu DB
    _persist_registers_to_graph(registers, soc)


def _ingest_ipxact(input_path: str, soc: str, verify: bool) -> None:
    """Run IP-XACT ingestion pipeline and write extracted data."""
    from ipxact_parser import parse_ipxact
    from validate import validate_registers

    print(f"[ingest] Parsing IP-XACT XML: {input_path} …")
    data = parse_ipxact(input_path)

    components = data.get("components", [])
    registers = data.get("registers", [])
    bit_fields = data.get("bit_fields", [])

    print(
        f"[ingest]   → Components: {len(components)}, "
        f"Registers: {len(registers)}, Bit-fields: {len(bit_fields)}"
    )

    custom_dir = _ensure_custom_dir(soc)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    data_path = os.path.join(custom_dir, f"{base_name}_ipxact.json")
    _write_json(data, data_path)
    print(f"[ingest]   → Wrote IP-XACT data : {data_path}")

    if verify and registers:
        print(f"[ingest] Running register validation …")
        validation = validate_registers(registers, {})
        print(
            f"[ingest]   → Passed: {validation['pass_count']}, "
            f"Failed: {validation['fail_count']}, "
            f"Coverage: {validation['coverage']:.1%}"
        )
        val_path = os.path.join(custom_dir, f"{base_name}_validation.json")
        _write_json(validation, val_path)
        print(f"[ingest]   → Wrote validation    : {val_path}")

    # Persist to custom Kuzu DB
    _persist_ipxact_to_graph(data, soc)


def _persist_registers_to_graph(registers: list[dict], soc: str) -> None:
    """Write extracted Register nodes into the custom Kuzu DB."""
    import kuzu
    import schema as _schema

    db_path = _get_custom_db_path(soc)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    inserted = 0
    for reg in registers:
        name = f"{soc}_{reg.get('name', 'UNKNOWN')}"
        try:
            conn.execute(
                "MERGE (r:Register {name: $name}) "
                "ON CREATE SET r.address = $addr, r.size_bits = $size, "
                "r.access_type = $access, r.reset_value = $reset, "
                "r.description = $desc, r.namespace = $ns, r.component = $comp",
                {
                    "name": name,
                    "addr": reg.get("address", ""),
                    "size": int(reg.get("size", 32)),
                    "access": reg.get("access", "RW"),
                    "reset": reg.get("reset_value", "0x0"),
                    "desc": reg.get("description", "")[:200],
                    "ns": "custom",
                    "comp": soc,
                },
            )
            inserted += 1
        except Exception as e:
            print(f"  [warn] Register {name}: {e}")

    print(f"[ingest]   → Persisted {inserted} Register nodes to {db_path}")


def _persist_ipxact_to_graph(data: dict, soc: str) -> None:
    """Write IP-XACT components and registers into the custom Kuzu DB."""
    import kuzu
    import schema as _schema

    db_path = _get_custom_db_path(soc)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    comp_count = 0
    for comp in data.get("components", []):
        comp_name = f"{soc}_{comp.get('name', 'UNKNOWN')}"
        try:
            conn.execute(
                "MERGE (c:Component {name: $name}) "
                "ON CREATE SET c.type = 'ipxact_component', "
                "c.description = $desc, c.namespace = 'custom', "
                "c.vendor = $vendor, c.version = $version",
                {
                    "name": comp_name,
                    "desc": comp.get("description", "")[:200],
                    "vendor": comp.get("vendor", ""),
                    "version": comp.get("version", ""),
                },
            )
            comp_count += 1
        except Exception as e:
            print(f"  [warn] Component {comp_name}: {e}")

    _persist_registers_to_graph(data.get("registers", []), soc)
    print(f"[ingest]   → Persisted {comp_count} Component nodes.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest custom SoC documentation into the BSP knowledge graph."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input file (PDF or IP-XACT XML)",
    )
    parser.add_argument(
        "--soc",
        required=True,
        help="SoC identifier (e.g. mt6989, sm8650) — used as namespace",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "pdf", "ipxact"],
        default="auto",
        help="Input format (default: auto-detect from extension)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run register validation after extraction",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"[error] Input file not found: {input_path}")
        sys.exit(1)

    fmt = args.format
    if fmt == "auto":
        try:
            fmt = _detect_format(input_path)
        except ValueError as e:
            print(f"[error] {e}")
            sys.exit(1)

    print(f"[ingest] ══════════════════════════════════════")
    print(f"[ingest]  Input  : {input_path}")
    print(f"[ingest]  SoC    : {args.soc}")
    print(f"[ingest]  Format : {fmt}")
    print(f"[ingest]  Verify : {args.verify}")
    print(f"[ingest] ══════════════════════════════════════")

    if fmt == "pdf":
        _ingest_pdf(input_path, args.soc, args.verify)
    else:
        _ingest_ipxact(input_path, args.soc, args.verify)

    print(f"[ingest] Done. Data written to knowledge-graph/custom/{args.soc}/")


if __name__ == "__main__":
    main()
