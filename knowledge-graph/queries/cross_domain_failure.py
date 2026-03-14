"""
Cross-Domain Failure Query — GraphRAG template for multi-hop failure analysis.

Traverses FailureMode → CAUSED_BY → Component paths and follows
POWERS/CLOCKS/ROUTES_TO relationships to surface cross-domain impact.

Uses fuzzy keyword matching on FailureMode.symptom and FailureMode.root_cause
fields so callers can supply natural-language symptom keywords.
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
_BASE_DB = os.path.join(_HERE, "..", "base", "bsp_base.db")

sys.path.insert(0, _SCHEMA_DIR)

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

SYMPTOM_WEIGHT = 0.6
ROOT_CAUSE_WEIGHT = 0.4
MAX_RESULTS = 10


def _open_db(db_path: str):
    import kuzu
    db_path = os.path.abspath(db_path)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return db, conn


def _result_to_list(result) -> list:
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    return rows


def _keyword_score(text: str, keywords: list[str]) -> float:
    """Simple keyword overlap score in [0.0, 1.0]."""
    if not text or not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_cross_domain_failure(
    symptom_keywords: list[str],
    db_path: str = None,
) -> list[dict]:
    """Find failure modes matching *symptom_keywords* and trace cross-domain impact.

    Performs fuzzy keyword matching against FailureMode.symptom and
    FailureMode.root_cause, then for each match follows CAUSED_BY relationships
    to identify the root component, then queries onward via POWERS/CLOCKS/ROUTES_TO
    to surface downstream affected components.

    Parameters
    ----------
    symptom_keywords:
        List of natural-language keywords describing the symptom (e.g.
        ``["IRQ", "storm", "100%"]``).
    db_path:
        Path to Kuzu DB directory.

    Returns
    -------
    list[dict]
        Sorted by confidence_score descending.  Each entry has:
        ``failure_modes``, ``affected_components``, ``confidence_score``.
    """
    if db_path is None:
        db_path = _BASE_DB

    t0 = time.perf_counter()
    _, conn = _open_db(db_path)

    # Step 1 — retrieve all failure modes
    all_fms: list[dict] = []
    try:
        q = conn.execute(
            "MATCH (f:FailureMode) "
            "RETURN f.name, f.symptom, f.root_cause, f.affected_domain, "
            "f.source, f.severity, f.namespace"
        )
        for row in _result_to_list(q):
            score = _keyword_score(str(row[1]), symptom_keywords) * SYMPTOM_WEIGHT + \
                    _keyword_score(str(row[2]), symptom_keywords) * ROOT_CAUSE_WEIGHT
            all_fms.append({
                "name": row[0],
                "symptom": row[1],
                "root_cause": row[2],
                "affected_domain": row[3],
                "source": row[4],
                "severity": row[5],
                "namespace": row[6],
                "confidence_score": round(score, 3),
            })
    except Exception as e:
        return [{"error": f"FailureMode query failed: {e}"}]

    # Step 2 — filter to matches with confidence > 0
    matches = sorted(
        [fm for fm in all_fms if fm["confidence_score"] > 0],
        key=lambda x: x["confidence_score"],
        reverse=True,
    )

    if not matches:
        return [{
            "failure_modes": [],
            "affected_components": [],
            "confidence_score": 0.0,
            "message": "No failure modes matched the provided keywords.",
            "query_ms": round((time.perf_counter() - t0) * 1000, 2),
        }]

    results = []
    for fm in matches[:MAX_RESULTS]:  # top results capped by MAX_RESULTS
        affected: list[dict] = []

        # Step 3 — find root components via CAUSED_BY
        root_components: list[str] = []
        try:
            q = conn.execute(
                "MATCH (f:FailureMode {name: $name})-[:CAUSED_BY]->(c:Component) "
                "RETURN c.name, c.type, c.description",
                {"name": fm["name"]},
            )
            for row in _result_to_list(q):
                root_components.append(row[0])
                affected.append({
                    "component": row[0],
                    "type": row[1],
                    "description": row[2],
                    "relationship": "CAUSED_BY",
                })
        except Exception:
            pass

        # Step 4 — multi-hop: find downstream components via POWERS/CLOCKS
        for comp_name in root_components[:3]:
            try:
                q = conn.execute(
                    "MATCH (c:Component {name: $name})-[:SUPPLIES|POWERS|ROUTES_TO*1..2]->(downstream:Component) "
                    "RETURN downstream.name, downstream.type",
                    {"name": comp_name},
                )
                for row in _result_to_list(q):
                    if not any(a["component"] == row[0] for a in affected):
                        affected.append({
                            "component": row[0],
                            "type": row[1],
                            "description": "",
                            "relationship": "downstream",
                        })
            except Exception:
                pass

            # Power domain upstream
            try:
                q = conn.execute(
                    "MATCH (pd:PowerDomain)-[:POWERS]->(c:Component {name: $name}) "
                    "RETURN pd.name, pd.type, pd.voltage_mv",
                    {"name": comp_name},
                )
                for row in _result_to_list(q):
                    affected.append({
                        "component": row[0],
                        "type": row[1],
                        "description": f"Powers {comp_name} at {row[2]} mV",
                        "relationship": "POWERS",
                    })
            except Exception:
                pass

        results.append({
            "failure_modes": [fm],
            "affected_components": affected,
            "confidence_score": fm["confidence_score"],
            "query_ms": round((time.perf_counter() - t0) * 1000, 2),
        })

    return results


def query_failures_by_domain(
    domain: str,
    db_path: str = None,
) -> list[dict]:
    """Return all failure modes for a specific affected domain.

    Parameters
    ----------
    domain:
        Affected domain name (e.g. ``"power"``, ``"interrupt"``, ``"multimedia"``).
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
            "MATCH (f:FailureMode {affected_domain: $domain}) "
            "RETURN f.name, f.symptom, f.root_cause, f.severity, f.source "
            "ORDER BY f.severity",
            {"domain": domain},
        )
        for row in _result_to_list(q):
            results.append({
                "name": row[0],
                "symptom": row[1],
                "root_cause": row[2],
                "severity": row[3],
                "source": row[4],
            })
    except Exception as e:
        results.append({"error": str(e)})
    return results


if __name__ == "__main__":
    print("=== Cross-domain failure query: 'IRQ storm interrupt' ===")
    for r in query_cross_domain_failure(["IRQ", "storm", "interrupt"]):
        fm = r.get("failure_modes", [{}])[0]
        print(f"  [{r['confidence_score']:.2f}] {fm.get('name')} — {fm.get('symptom', '')[:60]}")
        for c in r.get("affected_components", []):
            print(f"      → {c['component']} ({c['relationship']})")

    print("\n=== Power domain failures ===")
    for r in query_failures_by_domain("power"):
        print(f"  [{r.get('severity')}] {r.get('name')}")
