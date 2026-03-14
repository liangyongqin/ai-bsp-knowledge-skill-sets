"""
Power Chain Query — GraphRAG template for tracing PMIC supply paths.

Traces the supply chain from PMIC through PowerDomain nodes to a target
Component using multi-hop SUPPLIES/POWERS relationships in Kuzu.

All queries target knowledge-graph/base/bsp_base.db by default,
with optional override for custom namespace databases.
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
_BASE_DB = os.path.join(_HERE, "..", "base", "bsp_base.db")

sys.path.insert(0, _SCHEMA_DIR)


def _open_db(db_path: str):
    """Open Kuzu DB; returns (db, conn) tuple."""
    import kuzu
    db_path = os.path.abspath(db_path)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return db, conn


def _result_to_list(result) -> list:
    """Convert a Kuzu QueryResult to a list of rows."""
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    return rows


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_power_chain(
    component_name: str,
    db_path: str = None,
) -> list[dict]:
    """Trace the power supply chain leading to *component_name*.

    Walks SUPPLIES and POWERS relationships up to 5 hops from any Component
    or PowerDomain to find every supply path reaching *component_name*.

    Parameters
    ----------
    component_name:
        Name of the target component (e.g. ``"Cortex-A55-Cluster"``).
    db_path:
        Path to Kuzu DB directory. Defaults to
        ``knowledge-graph/base/bsp_base.db``.

    Returns
    -------
    list[dict]
        Each entry has keys: ``path_nodes``, ``relationships``,
        ``supply_levels``, ``hops``.
    """
    if db_path is None:
        db_path = _BASE_DB

    t0 = time.perf_counter()
    _, conn = _open_db(db_path)

    results: list[dict] = []

    # Direct SUPPLIES chain: Component → Component
    try:
        q = conn.execute(
            "MATCH (src:Component)-[r:SUPPLIES*1..5]->(target:Component {name: $name}) "
            "RETURN src.name AS source, src.type AS source_type, "
            "target.name AS target_name, length(r) AS hops",
            {"name": component_name},
        )
        for row in _result_to_list(q):
            results.append({
                "path_nodes": [row[0], row[2]],
                "relationships": ["SUPPLIES"],
                "supply_levels": {"source_type": row[1]},
                "hops": row[3],
                "query_ms": round((time.perf_counter() - t0) * 1000, 2),
            })
    except Exception as e:
        results.append({"error": f"SUPPLIES query failed: {e}"})

    # POWERS chain: PowerDomain → Component
    try:
        q = conn.execute(
            "MATCH (pd:PowerDomain)-[r:POWERS]->(c:Component {name: $name}) "
            "RETURN pd.name AS domain, pd.voltage_mv AS voltage, "
            "pd.type AS domain_type, c.name AS component",
            {"name": component_name},
        )
        for row in _result_to_list(q):
            results.append({
                "path_nodes": [row[0], row[3]],
                "relationships": ["POWERS"],
                "supply_levels": {
                    "power_domain": row[0],
                    "voltage_mv": row[1],
                    "domain_type": row[2],
                },
                "hops": 1,
                "query_ms": round((time.perf_counter() - t0) * 1000, 2),
            })
    except Exception as e:
        results.append({"error": f"POWERS query failed: {e}"})

    # Two-hop: Component→SUPPLIES→Component→POWERS→PowerDomain
    try:
        q = conn.execute(
            "MATCH (pmic:Component)-[:SUPPLIES]->(comp:Component)-[:POWERS|SUPPLIES*0..3]->(target:Component {name: $name}) "
            "RETURN pmic.name AS pmic, comp.name AS intermediate, target.name AS target",
            {"name": component_name},
        )
        for row in _result_to_list(q):
            results.append({
                "path_nodes": [row[0], row[1], row[2]],
                "relationships": ["SUPPLIES", "SUPPLIES/POWERS"],
                "supply_levels": {"pmic": row[0], "intermediate": row[1]},
                "hops": 2,
                "query_ms": round((time.perf_counter() - t0) * 1000, 2),
            })
    except Exception as e:
        pass  # three-hop query may fail on small graphs

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    for r in results:
        r.setdefault("query_ms", elapsed_ms)

    return results


def find_all_power_domains(db_path: str = None) -> list[dict]:
    """Return all PowerDomain nodes in the graph.

    Parameters
    ----------
    db_path:
        Path to Kuzu DB directory.

    Returns
    -------
    list[dict]
        Each entry has keys: ``name``, ``type``, ``voltage_mv``,
        ``current_ma``, ``description``.
    """
    if db_path is None:
        db_path = _BASE_DB

    t0 = time.perf_counter()
    _, conn = _open_db(db_path)

    results = []
    try:
        q = conn.execute(
            "MATCH (p:PowerDomain) "
            "RETURN p.name, p.type, p.voltage_mv, p.current_ma, p.description, p.namespace "
            "ORDER BY p.name"
        )
        for row in _result_to_list(q):
            results.append({
                "name": row[0],
                "type": row[1],
                "voltage_mv": row[2],
                "current_ma": row[3],
                "description": row[4],
                "namespace": row[5],
                "query_ms": round((time.perf_counter() - t0) * 1000, 2),
            })
    except Exception as e:
        results.append({"error": str(e)})

    return results


def find_components_powered_by(domain_name: str, db_path: str = None) -> list[dict]:
    """Return all Components powered by a given PowerDomain.

    Parameters
    ----------
    domain_name:
        Name of the PowerDomain node (e.g. ``"PD-CPU-LITTLE"``).
    db_path:
        Optional Kuzu DB path override.

    Returns
    -------
    list[dict]
    """
    if db_path is None:
        db_path = _BASE_DB

    _, conn = _open_db(db_path)
    results = []
    try:
        q = conn.execute(
            "MATCH (pd:PowerDomain {name: $name})-[:POWERS]->(c:Component) "
            "RETURN c.name, c.type, c.description",
            {"name": domain_name},
        )
        for row in _result_to_list(q):
            results.append({"name": row[0], "type": row[1], "description": row[2]})
    except Exception as e:
        results.append({"error": str(e)})
    return results


if __name__ == "__main__":
    print("=== Power Domains ===")
    for pd in find_all_power_domains():
        print(f"  {pd.get('name')} ({pd.get('voltage_mv')} mV) — {pd.get('description', '')[:60]}")

    print("\n=== Power chain for Cortex-A55-Cluster ===")
    for entry in query_power_chain("Cortex-A55-Cluster"):
        print(f"  {entry}")
