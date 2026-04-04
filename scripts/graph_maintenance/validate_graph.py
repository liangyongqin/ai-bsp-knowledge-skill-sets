#!/usr/bin/env python3
"""
validate_graph.py — Check graph integrity: orphan nodes, dangling relationships, schema compliance.

Usage::

    python3 scripts/graph_maintenance/validate_graph.py [--db-path PATH] [--json]

Exits 0 if no issues found, 1 if validation issues detected.
"""

import argparse
import json as _json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")

sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _BASE_DIR)

DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "bsp_base.db")

NODE_TABLES = ["Component", "PowerDomain", "ClockSource", "Register", "Interrupt", "FailureMode"]
VALID_NAMESPACES = {"base", "custom"}
VALID_ACCESS_TYPES = {"RO", "WO", "RW", "R/W", "RO/WO", "W1C", "UNKNOWN"}
VALID_IRQ_TYPES = {"SPI", "PPI", "SGI", "LPI", "MSI", "UNKNOWN"}


def validate(db_path: str) -> dict:
    """Run all validation checks and return a report dict."""
    import kuzu

    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    issues = []
    warnings = []

    # Check 1: Nodes with null or empty name
    for table in NODE_TABLES:
        try:
            result = conn.execute(
                f"MATCH (n:{table}) WHERE n.name IS NULL OR n.name = '' RETURN n.name"
            )
            count = 0
            while result.has_next():
                result.get_next()
                count += 1
            if count > 0:
                issues.append(f"{table}: {count} node(s) with null/empty name")
        except Exception as e:
            warnings.append(f"{table}: could not check name field — {e}")

    # Check 2: Invalid namespace values
    for table in NODE_TABLES:
        try:
            result = conn.execute(
                f"MATCH (n:{table}) WHERE n.namespace IS NOT NULL "
                f"RETURN DISTINCT n.namespace AS ns"
            )
            while result.has_next():
                ns = result.get_next()[0]
                if ns not in VALID_NAMESPACES:
                    issues.append(f"{table}: invalid namespace '{ns}' (expected: {VALID_NAMESPACES})")
        except Exception:
            pass

    # Check 3: Register access_type validation
    try:
        result = conn.execute(
            "MATCH (r:Register) WHERE r.access_type IS NOT NULL "
            "RETURN DISTINCT r.access_type AS at"
        )
        while result.has_next():
            at = result.get_next()[0]
            if at not in VALID_ACCESS_TYPES:
                warnings.append(f"Register: unusual access_type '{at}'")
    except Exception:
        pass

    # Check 4: Interrupt irq_type validation
    try:
        result = conn.execute(
            "MATCH (i:Interrupt) WHERE i.irq_type IS NOT NULL "
            "RETURN DISTINCT i.irq_type AS it"
        )
        while result.has_next():
            it = result.get_next()[0]
            if it not in VALID_IRQ_TYPES:
                warnings.append(f"Interrupt: unusual irq_type '{it}'")
    except Exception:
        pass

    # Check 5: Orphan Component nodes (no relationships at all)
    try:
        result = conn.execute(
            "MATCH (c:Component) "
            "WHERE NOT EXISTS { MATCH (c)-[]-() } "
            "RETURN c.name"
        )
        orphans = []
        while result.has_next():
            orphans.append(result.get_next()[0])
        if orphans:
            warnings.append(
                f"Component: {len(orphans)} orphan node(s) with no relationships: "
                + ", ".join(orphans[:10])
                + ("..." if len(orphans) > 10 else "")
            )
    except Exception as e:
        warnings.append(f"Could not check orphan Components — {e}")

    # Check 6: PowerDomain nodes not connected to any Component
    try:
        result = conn.execute(
            "MATCH (pd:PowerDomain) "
            "WHERE NOT EXISTS { MATCH (pd)-[:POWERS]->() } "
            "RETURN pd.name"
        )
        unconnected = []
        while result.has_next():
            unconnected.append(result.get_next()[0])
        if unconnected:
            warnings.append(
                f"PowerDomain: {len(unconnected)} domain(s) not powering any Component: "
                + ", ".join(unconnected[:10])
            )
    except Exception:
        pass

    # Check 7: ClockSource nodes not connected to any Component
    try:
        result = conn.execute(
            "MATCH (cs:ClockSource) "
            "WHERE NOT EXISTS { MATCH (cs)-[:CLOCKS]->() } "
            "RETURN cs.name"
        )
        unconnected = []
        while result.has_next():
            unconnected.append(result.get_next()[0])
        if unconnected:
            warnings.append(
                f"ClockSource: {len(unconnected)} source(s) not clocking any Component: "
                + ", ".join(unconnected[:10])
            )
    except Exception:
        pass

    # Check 8: FailureMode nodes without CAUSED_BY relationship
    try:
        result = conn.execute(
            "MATCH (fm:FailureMode) "
            "WHERE NOT EXISTS { MATCH (fm)-[:CAUSED_BY]->() } "
            "RETURN fm.name"
        )
        unlinked = []
        while result.has_next():
            unlinked.append(result.get_next()[0])
        if unlinked:
            warnings.append(
                f"FailureMode: {len(unlinked)} failure(s) without CAUSED_BY link: "
                + ", ".join(unlinked[:10])
                + ("..." if len(unlinked) > 10 else "")
            )
    except Exception:
        pass

    report = {
        "db_path": db_path,
        "issues": issues,
        "warnings": warnings,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "status": "FAIL" if issues else "PASS",
    }
    return report


def print_report(report: dict) -> None:
    """Print a human-readable validation report."""
    print("=" * 60)
    print("  BSP Knowledge Graph Validation Report")
    print("=" * 60)
    print(f"\n  Database: {report['db_path']}")
    print(f"  Status:   {report['status']}")

    if report["issues"]:
        print(f"\n  ISSUES ({report['issue_count']}):")
        for issue in report["issues"]:
            print(f"    ERROR: {issue}")

    if report["warnings"]:
        print(f"\n  WARNINGS ({report['warning_count']}):")
        for warning in report["warnings"]:
            print(f"    WARN:  {warning}")

    if not report["issues"] and not report["warnings"]:
        print("\n  No issues or warnings found.")

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate BSP knowledge graph integrity: orphan nodes, schema compliance."
    )
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to Kuzu database directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")
    args = parser.parse_args()

    report = validate(args.db_path)

    if args.json:
        print(_json.dumps(report, indent=2))
    else:
        print_report(report)

    sys.exit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
