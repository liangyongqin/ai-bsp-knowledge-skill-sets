"""
Interrupt Path Query — GraphRAG template for tracing IRQ routing chains.

Traces the path from an IRQ source through GIC-600 distributor,
ITS (for LPIs/MSIs), redistributors, and to the target vCPU/CPU.

Supports SPI, PPI, SGI, and LPI interrupt types.
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
_BASE_DB = os.path.join(_HERE, "..", "base", "bsp_base.db")

sys.path.insert(0, _SCHEMA_DIR)


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


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_interrupt_path(
    irq_source: str,
    db_path: str = None,
) -> list[dict]:
    """Trace the interrupt routing path from *irq_source* to target CPU.

    Resolves the interrupt type (SPI/PPI/SGI/LPI) from the Interrupt node,
    then follows ROUTES_TO relationships through GIC-600 to the CPU interface.
    For LPIs, includes the ITS translation chain.

    Parameters
    ----------
    irq_source:
        Interrupt name as stored in the graph (e.g. ``"SPI-PMIC"``,
        ``"LPI-PCIe-MSI"``).
    db_path:
        Path to Kuzu DB directory.

    Returns
    -------
    list[dict]
        Each entry has: ``source``, ``gic_config``, ``its_table``,
        ``target_cpu``, ``irq_type``, ``irq_id``.
    """
    if db_path is None:
        db_path = _BASE_DB

    t0 = time.perf_counter()
    _, conn = _open_db(db_path)

    results: list[dict] = []

    # Step 1 — look up the Interrupt node
    irq_info: dict = {}
    try:
        q = conn.execute(
            "MATCH (i:Interrupt {name: $name}) "
            "RETURN i.name, i.irq_type, i.irq_id, i.description, i.trigger",
            {"name": irq_source},
        )
        rows = _result_to_list(q)
        if rows:
            r = rows[0]
            irq_info = {
                "name": r[0],
                "irq_type": r[1],
                "irq_id": r[2],
                "description": r[3],
                "trigger": r[4],
            }
    except Exception as e:
        irq_info = {"error": str(e)}

    # Step 2 — find which component TRIGGERS this interrupt
    trigger_comp: str = ""
    try:
        q = conn.execute(
            "MATCH (i:Interrupt {name: $name})-[:TRIGGERS]->(c:Component) "
            "RETURN c.name, c.type",
            {"name": irq_source},
        )
        rows = _result_to_list(q)
        if rows:
            trigger_comp = rows[0][0]
    except Exception:
        pass

    # Step 3 — trace ROUTES_TO from peripheral → GIC-600 → CPU
    routing_chain: list[dict] = []
    try:
        q = conn.execute(
            "MATCH (src:Component)-[r:ROUTES_TO*1..5]->(cpu:Component) "
            "WHERE (src.name = $comp OR src.name = 'GIC-600') "
            "AND (cpu.type = 'cpu_core' OR cpu.type = 'cpu_cluster') "
            "RETURN src.name, cpu.name, cpu.type, length(r) AS hops",
            {"comp": trigger_comp or "GIC-600"},
        )
        for row in _result_to_list(q):
            routing_chain.append({
                "from": row[0],
                "to": row[1],
                "cpu_type": row[2],
                "hops": row[3],
            })
    except Exception as e:
        routing_chain.append({"error": str(e)})

    # Step 4 — for LPIs, trace ITS translation
    its_info: dict = {}
    if irq_info.get("irq_type") == "LPI":
        try:
            q = conn.execute(
                "MATCH (its:Component {name: 'GIC-600-ITS'})-[:TRANSLATES]->(i:Interrupt {name: $name}) "
                "RETURN its.name, its.type, its.description",
                {"name": irq_source},
            )
            rows = _result_to_list(q)
            if rows:
                its_info = {
                    "its_name": rows[0][0],
                    "its_type": rows[0][1],
                    "description": "ITS translates MSI write to LPI INTID",
                    "tables": ["ITS-Device-Table", "ITS-Interrupt-Translation-Table", "ITS-Collection-Table"],
                }
        except Exception as e:
            its_info = {"error": str(e)}

    # Step 5 — GIC-600 config
    gic_config: dict = {}
    try:
        q = conn.execute(
            "MATCH (g:Component {name: 'GIC-600'}) "
            "RETURN g.name, g.type, g.description, g.version",
        )
        rows = _result_to_list(q)
        if rows:
            gic_config = {
                "name": rows[0][0],
                "type": rows[0][1],
                "description": rows[0][2],
                "version": rows[0][3],
                "architecture": "GICv4" if irq_info.get("irq_type") == "LPI" else "GICv3",
            }
    except Exception as e:
        gic_config = {"error": str(e)}

    # Determine target CPUs from routing chain
    target_cpus = list({r.get("to") for r in routing_chain if r.get("to")})

    results.append({
        "source": irq_info,
        "trigger_component": trigger_comp,
        "gic_config": gic_config,
        "its_table": its_info,
        "routing_chain": routing_chain,
        "target_cpu": target_cpus,
        "query_ms": round((time.perf_counter() - t0) * 1000, 2),
    })

    return results


def list_all_interrupts(
    irq_type: str = None,
    db_path: str = None,
) -> list[dict]:
    """List all Interrupt nodes, optionally filtered by type.

    Parameters
    ----------
    irq_type:
        Optional filter: ``"SPI"``, ``"PPI"``, ``"SGI"``, or ``"LPI"``.
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
        if irq_type:
            q = conn.execute(
                "MATCH (i:Interrupt {irq_type: $type}) "
                "RETURN i.name, i.irq_type, i.irq_id, i.description, i.trigger "
                "ORDER BY i.irq_id",
                {"type": irq_type},
            )
        else:
            q = conn.execute(
                "MATCH (i:Interrupt) "
                "RETURN i.name, i.irq_type, i.irq_id, i.description, i.trigger "
                "ORDER BY i.irq_id"
            )
        for row in _result_to_list(q):
            results.append({
                "name": row[0],
                "irq_type": row[1],
                "irq_id": row[2],
                "description": row[3],
                "trigger": row[4],
            })
    except Exception as e:
        results.append({"error": str(e)})
    return results


if __name__ == "__main__":
    print("=== Interrupt path: SPI-PMIC ===")
    for r in query_interrupt_path("SPI-PMIC"):
        print(f"  source   : {r['source']}")
        print(f"  gic      : {r['gic_config'].get('name')} ({r['gic_config'].get('architecture')})")
        print(f"  target   : {r['target_cpu']}")
        print(f"  query_ms : {r['query_ms']}")

    print("\n=== LPI interrupt path: LPI-PCIe-MSI ===")
    for r in query_interrupt_path("LPI-PCIe-MSI"):
        print(f"  source   : {r['source']}")
        print(f"  ITS      : {r['its_table']}")
        print(f"  target   : {r['target_cpu']}")

    print("\n=== All SPIs ===")
    for irq in list_all_interrupts("SPI"):
        print(f"  SPI-{irq['irq_id']:4d}  {irq['name']:25s}  {irq['description'][:50]}")
