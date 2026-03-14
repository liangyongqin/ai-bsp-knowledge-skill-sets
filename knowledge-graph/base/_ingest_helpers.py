"""
Shared helpers for BSP knowledge graph ingestion scripts.

Provides idempotent node/relationship creation utilities for Kuzu 0.11+,
which does not support MERGE ... ON CREATE SET.
"""

import logging

logger = logging.getLogger(__name__)


def upsert_node(conn, label: str, params: dict) -> bool:
    """CREATE a node; silently skip if primary key already exists.

    Parameters
    ----------
    conn:
        Open kuzu.Connection.
    label:
        Node table label (e.g. 'Component').
    params:
        Dict of property name → value to store on the node.

    Returns
    -------
    bool
        True if created, False if already existed.
    """
    placeholders = ", ".join(f"{k}: ${k}" for k in params)
    try:
        conn.execute(f"CREATE (:{label} {{{placeholders}}})", params)
        return True
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "primary key" in msg:
            return False
        logger.warning("[upsert_node] %s %s: %s", label, params.get("name"), e)
        return False


def create_rel(conn, rel_type: str, src_label: str, dst_label: str,
               src_name: str, dst_name: str, rel_props: dict = None) -> bool:
    """Create a relationship between two nodes by name, silently handling errors.

    Parameters
    ----------
    conn:
        Open kuzu.Connection.
    rel_type:
        Relationship type (e.g. 'ROUTES_TO').
    src_label / dst_label:
        Node table labels for source and destination.
    src_name / dst_name:
        Primary key ``name`` values for source and destination.
    rel_props:
        Optional dict of relationship properties.

    Returns
    -------
    bool
        True if created successfully.
    """
    if rel_props:
        prop_str = ", ".join(f"{k}: ${k}" for k in rel_props)
        params = {"_src": src_name, "_dst": dst_name, **rel_props}
        q = (
            f"MATCH (a:{src_label} {{name: $_src}}), (b:{dst_label} {{name: $_dst}}) "
            f"CREATE (a)-[:{rel_type} {{{prop_str}}}]->(b)"
        )
    else:
        params = {"_src": src_name, "_dst": dst_name}
        q = (
            f"MATCH (a:{src_label} {{name: $_src}}), (b:{dst_label} {{name: $_dst}}) "
            f"CREATE (a)-[:{rel_type}]->(b)"
        )
    try:
        conn.execute(q, params)
        return True
    except Exception as e:
        logger.debug("[create_rel] %s %s->%s: %s", rel_type, src_name, dst_name, e)
        return False
