#!/usr/bin/env python3
"""
diff_graph.py — Compare two graph database snapshots and report changes.

Usage::

    python3 scripts/graph_maintenance/diff_graph.py --old PATH_A --new PATH_B [--json]

Compares node counts, relationship counts, and node-level additions/removals
between two Kuzu database directories.
"""

import argparse
import json as _json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")

sys.path.insert(0, _SCHEMA_DIR)

NODE_TABLES = ["Component", "PowerDomain", "ClockSource", "Register", "Interrupt", "FailureMode"]
REL_TABLES = [
    "SUPPLIES", "POWERS", "CLOCKS", "DEPENDS_ON_CLOCK", "TRIGGERS",
    "ROUTES_TO", "TRANSLATES", "STREAMS_TO", "DMA_TO", "SHARED_WITH",
    "CAUSED_BY", "AFFECTS_IF_REMOVED",
]


def _get_node_names(conn, table: str) -> set[str]:
    """Return the set of primary key (name) values for a node table."""
    names = set()
    try:
        result = conn.execute(f"MATCH (n:{table}) RETURN n.name")
        while result.has_next():
            names.add(result.get_next()[0])
    except Exception:
        pass
    return names


def _get_rel_count(conn, rel: str) -> int:
    try:
        result = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
        return result.get_next()[0] if result.has_next() else 0
    except Exception:
        return 0


def diff_graphs(old_path: str, new_path: str) -> dict:
    """Compare two Kuzu databases and return a diff report."""
    import kuzu

    for label, path in [("old", old_path), ("new", new_path)]:
        if not os.path.exists(path):
            print(f"Error: {label} database not found at {path}", file=sys.stderr)
            sys.exit(1)

    old_db = kuzu.Database(old_path)
    old_conn = kuzu.Connection(old_db)
    new_db = kuzu.Database(new_path)
    new_conn = kuzu.Connection(new_db)

    report = {"old_path": old_path, "new_path": new_path, "node_diffs": {}, "rel_diffs": {}}

    total_added = 0
    total_removed = 0

    for table in NODE_TABLES:
        old_names = _get_node_names(old_conn, table)
        new_names = _get_node_names(new_conn, table)
        added = sorted(new_names - old_names)
        removed = sorted(old_names - new_names)
        total_added += len(added)
        total_removed += len(removed)
        if added or removed:
            report["node_diffs"][table] = {
                "old_count": len(old_names),
                "new_count": len(new_names),
                "added": added,
                "removed": removed,
            }

    for rel in REL_TABLES:
        old_count = _get_rel_count(old_conn, rel)
        new_count = _get_rel_count(new_conn, rel)
        if old_count != new_count:
            report["rel_diffs"][rel] = {
                "old_count": old_count,
                "new_count": new_count,
                "delta": new_count - old_count,
            }

    report["summary"] = {
        "nodes_added": total_added,
        "nodes_removed": total_removed,
        "node_tables_changed": len(report["node_diffs"]),
        "rel_tables_changed": len(report["rel_diffs"]),
    }

    return report


def print_diff(report: dict) -> None:
    """Print a human-readable diff report."""
    print("=" * 60)
    print("  BSP Knowledge Graph Diff")
    print("=" * 60)
    print(f"\n  Old: {report['old_path']}")
    print(f"  New: {report['new_path']}")

    s = report["summary"]
    print(f"\n  Nodes added:   {s['nodes_added']}")
    print(f"  Nodes removed: {s['nodes_removed']}")
    print(f"  Tables changed (nodes): {s['node_tables_changed']}")
    print(f"  Tables changed (rels):  {s['rel_tables_changed']}")

    if report["node_diffs"]:
        print("\n  Node changes:")
        print("  " + "-" * 50)
        for table, d in report["node_diffs"].items():
            print(f"    {table}: {d['old_count']} -> {d['new_count']}")
            if d["added"]:
                for name in d["added"][:20]:
                    print(f"      + {name}")
                if len(d["added"]) > 20:
                    print(f"      ... and {len(d['added']) - 20} more")
            if d["removed"]:
                for name in d["removed"][:20]:
                    print(f"      - {name}")
                if len(d["removed"]) > 20:
                    print(f"      ... and {len(d['removed']) - 20} more")

    if report["rel_diffs"]:
        print("\n  Relationship changes:")
        print("  " + "-" * 50)
        for rel, d in report["rel_diffs"].items():
            sign = "+" if d["delta"] > 0 else ""
            print(f"    {rel}: {d['old_count']} -> {d['new_count']} ({sign}{d['delta']})")

    if not report["node_diffs"] and not report["rel_diffs"]:
        print("\n  No differences found.")

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two BSP knowledge graph snapshots and report changes."
    )
    parser.add_argument("--old", required=True, help="Path to the old Kuzu database directory")
    parser.add_argument("--new", required=True, help="Path to the new Kuzu database directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    report = diff_graphs(args.old, args.new)

    if args.json:
        print(_json.dumps(report, indent=2))
    else:
        print_diff(report)


if __name__ == "__main__":
    main()
