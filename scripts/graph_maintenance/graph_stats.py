#!/usr/bin/env python3
"""
graph_stats.py — Report node/relationship counts by type and identify coverage gaps.

Usage::

    python3 scripts/graph_maintenance/graph_stats.py [--db-path PATH] [--json]

Prints a human-readable table of node counts per table and namespace,
relationship counts per type, and flags coverage gaps (node types with
fewer than 10 entries).
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
REL_TABLES = [
    "SUPPLIES", "POWERS", "CLOCKS", "DEPENDS_ON_CLOCK", "TRIGGERS",
    "ROUTES_TO", "TRANSLATES", "STREAMS_TO", "DMA_TO", "SHARED_WITH",
    "CAUSED_BY", "AFFECTS_IF_REMOVED",
]


def collect_stats(db_path: str) -> dict:
    """Collect node and relationship statistics from the Kuzu database."""
    import kuzu

    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    stats = {"nodes": {}, "relationships": {}, "namespaces": {}, "coverage_gaps": []}

    # Node counts per table
    total_nodes = 0
    for table in NODE_TABLES:
        try:
            result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
            count = result.get_next()[0] if result.has_next() else 0
        except Exception:
            count = 0
        stats["nodes"][table] = count
        total_nodes += count

        # Namespace breakdown
        try:
            result = conn.execute(
                f"MATCH (n:{table}) RETURN n.namespace AS ns, count(n) AS cnt ORDER BY cnt DESC"
            )
            ns_counts = {}
            while result.has_next():
                row = result.get_next()
                ns_counts[row[0] or "null"] = row[1]
            if ns_counts:
                stats["namespaces"][table] = ns_counts
        except Exception:
            pass

        if count < 10:
            stats["coverage_gaps"].append(
                f"{table}: only {count} nodes (target: >= 10)"
            )

    stats["total_nodes"] = total_nodes

    # Relationship counts per type
    total_rels = 0
    for rel in REL_TABLES:
        try:
            result = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt")
            count = result.get_next()[0] if result.has_next() else 0
        except Exception:
            count = 0
        stats["relationships"][rel] = count
        total_rels += count

    stats["total_relationships"] = total_rels

    return stats


def print_stats(stats: dict) -> None:
    """Print a human-readable statistics report."""
    print("=" * 60)
    print("  BSP Knowledge Graph Statistics")
    print("=" * 60)

    print(f"\n  Total nodes:         {stats['total_nodes']}")
    print(f"  Total relationships: {stats['total_relationships']}")

    print("\n  Node counts by table:")
    print("  " + "-" * 40)
    for table, count in stats["nodes"].items():
        print(f"    {table:<20s}  {count:>5d}")
        if table in stats.get("namespaces", {}):
            for ns, nc in stats["namespaces"][table].items():
                print(f"      [{ns}]  {nc}")

    print("\n  Relationship counts by type:")
    print("  " + "-" * 40)
    for rel, count in stats["relationships"].items():
        print(f"    {rel:<20s}  {count:>5d}")

    if stats["coverage_gaps"]:
        print("\n  Coverage gaps (< 10 nodes):")
        print("  " + "-" * 40)
        for gap in stats["coverage_gaps"]:
            print(f"    WARNING: {gap}")
    else:
        print("\n  No coverage gaps detected.")

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report BSP knowledge graph node/relationship counts and coverage gaps."
    )
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to Kuzu database directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")
    args = parser.parse_args()

    stats = collect_stats(args.db_path)

    if args.json:
        print(_json.dumps(stats, indent=2))
    else:
        print_stats(stats)


if __name__ == "__main__":
    main()
