"""
Post-Mortem Report Ingestion CLI (Knowledge Sedimentation).

Parses structured post-mortem reports (Markdown or JSON) and ingests them
into the BSP knowledge graph as FailureMode nodes with CAUSED_BY
relationships to Component nodes.

Supports:
  - Markdown post-mortem format (see --help for template)
  - JSON post-mortem format (array of structured objects)
  - --dry-run mode: shows what would be ingested without writing
  - --validate mode: checks extracted entities against the Kuzu schema
  - Incremental ingestion: skips existing nodes (idempotent)

Usage::

    # Ingest a single markdown post-mortem
    python3 scripts/ingest_postmortem.py --input report.md --namespace base

    # Ingest a JSON batch of post-mortems into custom namespace
    python3 scripts/ingest_postmortem.py --input cases.json --namespace custom

    # Dry-run to preview extraction without writing
    python3 scripts/ingest_postmortem.py --input report.md --dry-run

    # Validate extracted entities against the schema
    python3 scripts/ingest_postmortem.py --input report.md --validate
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")

sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _BASE_DIR)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

VALID_DOMAINS = {
    "dvfs", "power", "thermal", "boot", "clock", "debug",
    "multimedia", "camera", "isp", "storage",
    "gpu", "rendering", "display",
    "interrupt", "virtualization", "gic",
    "general",
}

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}


@dataclass
class PostMortemEntry:
    """A single failure mode extracted from a post-mortem report."""
    name: str
    symptom: str
    root_cause: str
    affected_domain: str
    source: str
    severity: str = "medium"
    affected_components: list[str] | None = None
    resolution: str | None = None

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        errors = []
        if not self.name or not self.name.strip():
            errors.append("name is empty")
        if not self.symptom or not self.symptom.strip():
            errors.append("symptom is empty")
        if not self.root_cause or not self.root_cause.strip():
            errors.append("root_cause is empty")
        if self.affected_domain not in VALID_DOMAINS:
            errors.append(
                f"affected_domain '{self.affected_domain}' not in {sorted(VALID_DOMAINS)}"
            )
        if self.severity not in VALID_SEVERITIES:
            errors.append(
                f"severity '{self.severity}' not in {sorted(VALID_SEVERITIES)}"
            )
        if not self.source or not self.source.strip():
            errors.append("source is empty")
        return errors


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def _generate_name(symptom: str, source: str) -> str:
    """Generate a deterministic FailureMode name from symptom + source."""
    slug = re.sub(r"[^a-z0-9]+", "-", symptom.lower().strip())[:60].strip("-")
    h = hashlib.sha256(f"{symptom}|{source}".encode()).hexdigest()[:8]
    return f"FM-PM-{slug}-{h}"


def _parse_markdown_section(text: str) -> list[dict]:
    """Parse a markdown post-mortem into structured sections.

    Expected markdown format (one or more entries separated by '---' or '## '):

        ## Post-Mortem: <title>
        **Symptom:** <observed symptom>
        **Root Cause:** <root cause analysis>
        **Domain:** <affected domain>
        **Severity:** <critical|high|medium|low>
        **Source:** <source document or investigation ID>
        **Components:** <comma-separated component names>
        **Resolution:** <fix or mitigation applied>
    """
    entries = []

    # Split on horizontal rules or H2 headers
    sections = re.split(r"(?:^|\n)(?:---+|\*\*\*+|___+)\s*\n|(?=^## )", text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        fields = {}
        # Extract **Key:** Value patterns — colon may be inside or outside bold
        for match in re.finditer(
            r"\*\*([^*]+?):?\*\*:?\s*(.+?)(?=\n\*\*|\n##|\n---|\Z)",
            section,
            re.DOTALL,
        ):
            key = match.group(1).strip().rstrip(":").lower().replace(" ", "_")
            value = match.group(2).strip()
            # Normalize newlines inside values
            value = re.sub(r"\s*\n\s*", " ", value)
            fields[key] = value

        # Also try # Title as symptom hint
        title_match = re.match(r"^##\s*(?:Post-Mortem:\s*)?(.+)", section)
        if title_match and "title" not in fields:
            fields["title"] = title_match.group(1).strip()

        # Need at least symptom + root_cause to be useful
        if "symptom" in fields and "root_cause" in fields:
            entries.append(fields)

    return entries


def parse_markdown(text: str, default_source: str = "post-mortem") -> list[PostMortemEntry]:
    """Parse markdown post-mortem text into PostMortemEntry objects."""
    raw_entries = _parse_markdown_section(text)
    results = []

    for fields in raw_entries:
        symptom = fields.get("symptom", "")
        source = fields.get("source", default_source)
        name = fields.get("name", _generate_name(symptom, source))

        components_raw = fields.get("components", fields.get("affected_components", ""))
        components = [c.strip() for c in components_raw.split(",") if c.strip()] if components_raw else None

        entry = PostMortemEntry(
            name=name,
            symptom=symptom,
            root_cause=fields.get("root_cause", ""),
            affected_domain=fields.get("domain", fields.get("affected_domain", "general")),
            source=source,
            severity=fields.get("severity", "medium").lower(),
            affected_components=components,
            resolution=fields.get("resolution"),
        )
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def parse_json(text: str) -> list[PostMortemEntry]:
    """Parse JSON post-mortem data into PostMortemEntry objects.

    Accepts either a single object or an array of objects with fields:
    name, symptom, root_cause, affected_domain, source, severity,
    affected_components, resolution.
    """
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON must be an object or array of objects")

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue

        symptom = item.get("symptom", "")
        source = item.get("source", "post-mortem-json")
        name = item.get("name", _generate_name(symptom, source))

        components = item.get("affected_components")
        if isinstance(components, str):
            components = [c.strip() for c in components.split(",") if c.strip()]

        entry = PostMortemEntry(
            name=name,
            symptom=symptom,
            root_cause=item.get("root_cause", ""),
            affected_domain=item.get("affected_domain", "general"),
            source=source,
            severity=item.get("severity", "medium").lower(),
            affected_components=components,
            resolution=item.get("resolution"),
        )
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_format(input_path: str) -> str:
    """Detect format from file extension."""
    ext = os.path.splitext(input_path)[1].lower()
    if ext in (".md", ".markdown", ".txt"):
        return "markdown"
    if ext == ".json":
        return "json"
    raise ValueError(
        f"Cannot auto-detect format for extension '{ext}'. "
        "Use --format markdown or --format json."
    )


def parse_file(input_path: str, fmt: str) -> list[PostMortemEntry]:
    """Parse input file and return list of PostMortemEntry objects."""
    with open(input_path, "r", encoding="utf-8") as fh:
        text = fh.read()

    default_source = os.path.basename(input_path)
    if fmt == "markdown":
        return parse_markdown(text, default_source=default_source)
    elif fmt == "json":
        return parse_json(text)
    else:
        raise ValueError(f"Unknown format: {fmt}")


# ---------------------------------------------------------------------------
# Graph writer
# ---------------------------------------------------------------------------

def write_to_graph(
    entries: list[PostMortemEntry],
    namespace: str,
    db_path: Optional[str] = None,
) -> dict:
    """Write PostMortemEntry objects to the Kuzu knowledge graph.

    Returns a summary dict with counts of created/skipped nodes and rels.
    """
    import kuzu
    import schema as _schema
    from _ingest_helpers import upsert_node, create_rel

    if db_path is None:
        db_path = os.path.join(_BASE_DIR, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)

    stats = {"nodes_created": 0, "nodes_skipped": 0, "rels_created": 0, "rels_skipped": 0}

    for entry in entries:
        created = upsert_node(conn, "FailureMode", {
            "name": entry.name,
            "symptom": entry.symptom,
            "root_cause": entry.root_cause,
            "affected_domain": entry.affected_domain,
            "source": entry.source,
            "namespace": namespace,
            "severity": entry.severity,
        })
        if created:
            stats["nodes_created"] += 1
        else:
            stats["nodes_skipped"] += 1

        # Create CAUSED_BY relationships to affected components
        if entry.affected_components:
            for comp_name in entry.affected_components:
                rel_ok = create_rel(
                    conn, "CAUSED_BY",
                    "FailureMode", "Component",
                    entry.name, comp_name,
                )
                if rel_ok:
                    stats["rels_created"] += 1
                else:
                    stats["rels_skipped"] += 1

    return stats


# ---------------------------------------------------------------------------
# Validate mode
# ---------------------------------------------------------------------------

def validate_entries(entries: list[PostMortemEntry], db_path: Optional[str] = None) -> list[dict]:
    """Validate entries against schema and existing graph data.

    Returns a list of validation result dicts.
    """
    results = []

    # Check if we can verify components against the graph
    known_components: set[str] = set()
    try:
        import kuzu
        if db_path is None:
            db_path = os.path.join(_BASE_DIR, "bsp_base.db")
        if os.path.exists(db_path):
            db = kuzu.Database(db_path)
            conn = kuzu.Connection(db)
            result = conn.execute("MATCH (c:Component) RETURN c.name")
            while result.has_next():
                known_components.add(result.get_next()[0])
    except Exception:
        pass  # Graph not available — skip component validation

    for entry in entries:
        schema_errors = entry.validate()
        component_warnings = []
        if entry.affected_components and known_components:
            for comp in entry.affected_components:
                if comp not in known_components:
                    component_warnings.append(
                        f"Component '{comp}' not found in knowledge graph"
                    )

        results.append({
            "name": entry.name,
            "valid": len(schema_errors) == 0,
            "schema_errors": schema_errors,
            "component_warnings": component_warnings,
        })

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

MARKDOWN_TEMPLATE = """\
## Post-Mortem: <title>
**Symptom:** <what the engineer observed>
**Root Cause:** <determined root cause>
**Domain:** <dvfs|power|thermal|boot|clock|multimedia|camera|gpu|interrupt|general>
**Severity:** <critical|high|medium|low>
**Source:** <investigation ID or document reference>
**Components:** <comma-separated component names from the knowledge graph>
**Resolution:** <fix or mitigation applied>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest post-mortem reports into the BSP knowledge graph.",
        epilog=f"Markdown template:\n\n{MARKDOWN_TEMPLATE}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input file (Markdown or JSON)",
    )
    parser.add_argument(
        "--namespace", choices=["base", "custom"], default="custom",
        help="Graph namespace to write into (default: custom)",
    )
    parser.add_argument(
        "--format", choices=["auto", "markdown", "json"], default="auto",
        dest="fmt",
        help="Input format (default: auto-detect from extension)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be ingested without writing to the graph",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate extracted entities against the Kuzu schema",
    )
    parser.add_argument(
        "--db-path",
        help="Path to Kuzu database (default: knowledge-graph/base/bsp_base.db)",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"[error] Input file not found: {input_path}")
        sys.exit(1)

    fmt = args.fmt
    if fmt == "auto":
        try:
            fmt = detect_format(input_path)
        except ValueError as e:
            print(f"[error] {e}")
            sys.exit(1)

    print(f"[postmortem] ══════════════════════════════════════")
    print(f"[postmortem]  Input     : {input_path}")
    print(f"[postmortem]  Format    : {fmt}")
    print(f"[postmortem]  Namespace : {args.namespace}")
    print(f"[postmortem]  Dry-run   : {args.dry_run}")
    print(f"[postmortem]  Validate  : {args.validate}")
    print(f"[postmortem] ══════════════════════════════════════")

    # Parse
    entries = parse_file(input_path, fmt)
    if not entries:
        print("[postmortem] No post-mortem entries found in input file.")
        sys.exit(0)

    print(f"[postmortem] Extracted {len(entries)} failure mode(s).")

    # Validate
    if args.validate:
        print(f"\n[postmortem] === Validation Results ===")
        results = validate_entries(entries, db_path=args.db_path)
        all_valid = True
        for r in results:
            status = "PASS" if r["valid"] else "FAIL"
            print(f"  [{status}] {r['name']}")
            for err in r["schema_errors"]:
                print(f"         ERROR: {err}")
                all_valid = False
            for warn in r["component_warnings"]:
                print(f"         WARN:  {warn}")
        if all_valid:
            print(f"[postmortem] All {len(results)} entries passed validation.")
        else:
            print(f"[postmortem] Some entries have validation errors.")
            if not args.dry_run:
                print("[postmortem] Fix errors before ingesting (or use --dry-run to preview).")
                sys.exit(1)

    # Dry-run: show what would be written
    if args.dry_run:
        print(f"\n[postmortem] === Dry-Run Preview ===")
        for entry in entries:
            print(f"\n  FailureMode: {entry.name}")
            print(f"    symptom:    {entry.symptom[:80]}{'…' if len(entry.symptom) > 80 else ''}")
            print(f"    root_cause: {entry.root_cause[:80]}{'…' if len(entry.root_cause) > 80 else ''}")
            print(f"    domain:     {entry.affected_domain}")
            print(f"    severity:   {entry.severity}")
            print(f"    source:     {entry.source}")
            if entry.affected_components:
                print(f"    components: {', '.join(entry.affected_components)}")
                for comp in entry.affected_components:
                    print(f"    → CAUSED_BY relationship: {entry.name} → {comp}")
        print(f"\n[postmortem] Dry-run complete. {len(entries)} entries would be written.")
        sys.exit(0)

    # Write to graph
    stats = write_to_graph(entries, args.namespace, db_path=args.db_path)
    print(f"\n[postmortem] === Ingestion Results ===")
    print(f"  Nodes created:  {stats['nodes_created']}")
    print(f"  Nodes skipped:  {stats['nodes_skipped']} (already exist)")
    print(f"  Rels created:   {stats['rels_created']}")
    print(f"  Rels skipped:   {stats['rels_skipped']} (missing endpoint or duplicate)")
    print(f"[postmortem] Done.")


if __name__ == "__main__":
    main()
