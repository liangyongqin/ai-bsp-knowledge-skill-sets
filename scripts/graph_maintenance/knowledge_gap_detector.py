"""
Knowledge Gap Detector — identify under-connected topology regions.

Queries the BSP knowledge graph for areas with sparse FailureMode coverage,
low relationship density, and domain blind spots. Outputs a prioritized
list of gaps to guide future seed script development.

Usage::

    python3 scripts/graph_maintenance/knowledge_gap_detector.py [--db-path PATH] [--json]

Sources of gap signals:
  1. Components with zero FailureMode (CAUSED_BY) links
  2. Components with zero or one relationship (low connectivity)
  3. Node types with below-average representation
  4. Domains (affected_domain) with few FailureModes
  5. Relationship types with very few instances (< 5)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")

sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _BASE_DIR)

DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "bsp_base.db")


def detect_gaps(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Analyze the knowledge graph and return a structured gap report.

    Returns
    -------
    dict
        Keys: components_no_failures, low_connectivity_components,
              underrepresented_node_types, domain_failure_coverage,
              sparse_relationship_types, summary.
    """
    import kuzu

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    report: dict = {}

    # -----------------------------------------------------------------------
    # 1. Components with no FailureMode links (CAUSED_BY points FROM FM TO Component)
    # -----------------------------------------------------------------------
    try:
        result = conn.execute("""
            MATCH (c:Component)
            WHERE NOT EXISTS {
                MATCH (f:FailureMode)-[:CAUSED_BY]->(c)
            }
            RETURN c.name AS name, c.type AS type
            ORDER BY c.name
        """)
        no_fm = []
        while result.has_next():
            row = result.get_next()
            no_fm.append({"name": row[0], "type": row[1]})
        report["components_no_failures"] = {
            "count": len(no_fm),
            "items": no_fm[:50],  # cap output
            "note": "Components with no FailureMode → CAUSED_BY link. Priority targets for failure-mode research."
        }
    except Exception as e:
        report["components_no_failures"] = {"error": str(e)}

    # -----------------------------------------------------------------------
    # 2. Low-connectivity components (0 or 1 total relationships)
    # -----------------------------------------------------------------------
    try:
        result = conn.execute("""
            MATCH (c:Component)
            OPTIONAL MATCH (c)-[r]-()
            WITH c.name AS name, c.type AS type, count(r) AS rel_count
            WHERE rel_count <= 1
            RETURN name, type, rel_count
            ORDER BY rel_count ASC, name ASC
        """)
        low_conn = []
        while result.has_next():
            row = result.get_next()
            low_conn.append({"name": row[0], "type": row[1], "relationships": row[2]})
        report["low_connectivity_components"] = {
            "count": len(low_conn),
            "items": low_conn[:50],
            "note": "Components with 0-1 relationships. May need ROUTES_TO, POWERS, CLOCKS, or STREAMS_TO links."
        }
    except Exception as e:
        report["low_connectivity_components"] = {"error": str(e)}

    # -----------------------------------------------------------------------
    # 3. Node type representation check
    # -----------------------------------------------------------------------
    node_tables = ["Component", "PowerDomain", "ClockSource", "Register", "Interrupt", "FailureMode"]
    counts = {}
    for table in node_tables:
        try:
            result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
            if result.has_next():
                counts[table] = result.get_next()[0]
            else:
                counts[table] = 0
        except Exception:
            counts[table] = 0

    total = sum(counts.values())
    avg = total / len(node_tables) if node_tables else 0
    underrep = {k: v for k, v in counts.items() if v < avg * 0.3}
    report["underrepresented_node_types"] = {
        "counts": counts,
        "total_nodes": total,
        "average_per_type": round(avg, 1),
        "below_30pct_average": underrep,
        "note": "Node types with < 30% of the average count. Consider expanding these categories."
    }

    # -----------------------------------------------------------------------
    # 4. FailureMode domain coverage
    # -----------------------------------------------------------------------
    try:
        result = conn.execute("""
            MATCH (f:FailureMode)
            RETURN f.affected_domain AS domain, count(f) AS cnt
            ORDER BY cnt ASC
        """)
        domain_coverage = {}
        while result.has_next():
            row = result.get_next()
            domain_coverage[row[0]] = row[1]

        expected_domains = [
            "power-thermal", "boot-debug", "multimedia",
            "gpu-rendering", "interrupt-virt", "hardware-spec"
        ]
        missing = [d for d in expected_domains if d not in domain_coverage]
        report["domain_failure_coverage"] = {
            "per_domain": domain_coverage,
            "missing_domains": missing,
            "note": "FailureMode count by affected_domain. Missing or low-count domains need failure mode research."
        }
    except Exception as e:
        report["domain_failure_coverage"] = {"error": str(e)}

    # -----------------------------------------------------------------------
    # 5. Sparse relationship types
    # -----------------------------------------------------------------------
    rel_types = [
        "SUPPLIES", "POWERS", "CLOCKS", "DEPENDS_ON_CLOCK", "TRIGGERS",
        "ROUTES_TO", "TRANSLATES", "STREAMS_TO", "DMA_TO",
        "SHARED_WITH", "CAUSED_BY", "AFFECTS_IF_REMOVED"
    ]
    rel_counts = {}
    for rt in rel_types:
        try:
            # Use table function to count relationships
            result = conn.execute(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")
            if result.has_next():
                rel_counts[rt] = result.get_next()[0]
            else:
                rel_counts[rt] = 0
        except Exception:
            rel_counts[rt] = 0

    sparse = {k: v for k, v in rel_counts.items() if v < 10}
    report["sparse_relationship_types"] = {
        "counts": rel_counts,
        "below_10": sparse,
        "note": "Relationship types with < 10 instances. These represent weak connections in the knowledge graph."
    }

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    report["summary"] = {
        "total_nodes": total,
        "total_gaps_found": (
            report.get("components_no_failures", {}).get("count", 0) +
            report.get("low_connectivity_components", {}).get("count", 0) +
            len(underrep) +
            len(report.get("domain_failure_coverage", {}).get("missing_domains", [])) +
            len(sparse)
        ),
        "priority_actions": []
    }

    # Generate priority actions
    actions = report["summary"]["priority_actions"]
    no_fm_count = report.get("components_no_failures", {}).get("count", 0)
    if no_fm_count > 50:
        actions.append(f"HIGH: {no_fm_count} Components lack FailureMode links — add CAUSED_BY relationships")
    elif no_fm_count > 0:
        actions.append(f"MEDIUM: {no_fm_count} Components lack FailureMode links")

    low_count = report.get("low_connectivity_components", {}).get("count", 0)
    if low_count > 20:
        actions.append(f"HIGH: {low_count} Components have ≤1 relationship — improve graph connectivity")
    elif low_count > 0:
        actions.append(f"LOW: {low_count} Components have ≤1 relationship")

    if underrep:
        actions.append(f"MEDIUM: Underrepresented types: {', '.join(underrep.keys())} — add more nodes")

    missing_domains = report.get("domain_failure_coverage", {}).get("missing_domains", [])
    if missing_domains:
        actions.append(f"HIGH: No FailureModes for domains: {', '.join(missing_domains)}")

    if sparse:
        actions.append(f"LOW: Sparse relationship types: {', '.join(sparse.keys())}")

    if not actions:
        actions.append("No critical gaps detected — graph is well-connected.")

    return report


def print_report(report: dict) -> None:
    """Pretty-print the gap report to stdout."""
    print("=" * 60)
    print("  BSP Knowledge Graph — Gap Analysis")
    print("=" * 60)

    # Summary
    s = report.get("summary", {})
    print(f"\n  Total nodes:      {s.get('total_nodes', '?')}")
    print(f"  Total gaps found: {s.get('total_gaps_found', '?')}")
    print(f"\n  Priority Actions:")
    for action in s.get("priority_actions", []):
        print(f"    • {action}")

    # Components without failure modes
    cfm = report.get("components_no_failures", {})
    print(f"\n  Components without FailureMode links: {cfm.get('count', '?')}")
    items = cfm.get("items", [])
    if items:
        for item in items[:10]:
            print(f"    - {item['name']} ({item['type']})")
        if len(items) > 10:
            print(f"    ... and {cfm['count'] - 10} more")

    # Low connectivity
    lc = report.get("low_connectivity_components", {})
    print(f"\n  Low-connectivity Components (≤1 rel): {lc.get('count', '?')}")
    items = lc.get("items", [])
    if items:
        for item in items[:10]:
            print(f"    - {item['name']} ({item['type']}) — {item['relationships']} rels")
        if len(items) > 10:
            print(f"    ... and {lc['count'] - 10} more")

    # Node type representation
    nt = report.get("underrepresented_node_types", {})
    print(f"\n  Node type counts (avg {nt.get('average_per_type', '?')} per type):")
    for k, v in nt.get("counts", {}).items():
        marker = " ← LOW" if k in nt.get("below_30pct_average", {}) else ""
        print(f"    {k:25s} {v:>5d}{marker}")

    # Domain failure coverage
    dc = report.get("domain_failure_coverage", {})
    print(f"\n  FailureMode coverage by domain:")
    for domain, cnt in sorted(dc.get("per_domain", {}).items(), key=lambda x: x[1]):
        print(f"    {domain:30s} {cnt:>5d}")
    if dc.get("missing_domains"):
        print(f"  Missing domains: {', '.join(dc['missing_domains'])}")

    # Sparse relationships
    sr = report.get("sparse_relationship_types", {})
    if sr.get("below_10"):
        print(f"\n  Sparse relationship types (< 10 instances):")
        for k, v in sorted(sr["below_10"].items(), key=lambda x: x[1]):
            print(f"    {k:25s} {v:>5d}")

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect knowledge gaps in the BSP knowledge graph."
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to Kuzu database directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    report = detect_gaps(db_path=args.db_path)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
