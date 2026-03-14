"""
BSP Knowledge Graph Schema — Kuzu node and relationship table definitions.

Defines all node and relationship tables for the BSP knowledge graph using
the Kuzu Python API. All table creation uses IF NOT EXISTS for idempotency.

Reference: CLAUDE.md — Knowledge Graph Conventions
"""

import kuzu


# ---------------------------------------------------------------------------
# Node table DDL constants
# ---------------------------------------------------------------------------

NODE_TABLES: list[tuple[str, str]] = [
    (
        "Component",
        """CREATE NODE TABLE IF NOT EXISTS Component (
            name        STRING,
            type        STRING,
            description STRING,
            namespace   STRING,
            vendor      STRING,
            version     STRING,
            PRIMARY KEY (name)
        )""",
    ),
    (
        "PowerDomain",
        """CREATE NODE TABLE IF NOT EXISTS PowerDomain (
            name        STRING,
            type        STRING,
            description STRING,
            namespace   STRING,
            voltage_mv  DOUBLE,
            current_ma  DOUBLE,
            PRIMARY KEY (name)
        )""",
    ),
    (
        "ClockSource",
        """CREATE NODE TABLE IF NOT EXISTS ClockSource (
            name        STRING,
            type        STRING,
            description STRING,
            namespace   STRING,
            frequency_hz INT64,
            parent_clk  STRING,
            PRIMARY KEY (name)
        )""",
    ),
    (
        "Register",
        """CREATE NODE TABLE IF NOT EXISTS Register (
            name        STRING,
            address     STRING,
            size_bits   INT64,
            access_type STRING,
            reset_value STRING,
            description STRING,
            namespace   STRING,
            component   STRING,
            PRIMARY KEY (name)
        )""",
    ),
    (
        "Interrupt",
        """CREATE NODE TABLE IF NOT EXISTS Interrupt (
            name        STRING,
            irq_type    STRING,
            irq_id      INT64,
            description STRING,
            namespace   STRING,
            trigger     STRING,
            PRIMARY KEY (name)
        )""",
    ),
    (
        "FailureMode",
        """CREATE NODE TABLE IF NOT EXISTS FailureMode (
            name            STRING,
            symptom         STRING,
            root_cause      STRING,
            affected_domain STRING,
            source          STRING,
            namespace       STRING,
            severity        STRING,
            PRIMARY KEY (name)
        )""",
    ),
]

# ---------------------------------------------------------------------------
# Relationship table DDL constants
# ---------------------------------------------------------------------------

REL_TABLES: list[tuple[str, str]] = [
    (
        "SUPPLIES",
        """CREATE REL TABLE IF NOT EXISTS SUPPLIES (
            FROM Component TO Component,
            voltage_mv  DOUBLE,
            description STRING
        )""",
    ),
    (
        "POWERS",
        """CREATE REL TABLE IF NOT EXISTS POWERS (
            FROM PowerDomain TO Component,
            description STRING
        )""",
    ),
    (
        "CLOCKS",
        """CREATE REL TABLE IF NOT EXISTS CLOCKS (
            FROM ClockSource TO Component,
            description STRING
        )""",
    ),
    (
        "DEPENDS_ON_CLOCK",
        """CREATE REL TABLE IF NOT EXISTS DEPENDS_ON_CLOCK (
            FROM Component TO ClockSource,
            description STRING
        )""",
    ),
    (
        "TRIGGERS",
        """CREATE REL TABLE IF NOT EXISTS TRIGGERS (
            FROM Interrupt TO Component,
            description STRING
        )""",
    ),
    (
        "ROUTES_TO",
        """CREATE REL TABLE IF NOT EXISTS ROUTES_TO (
            FROM Component TO Component,
            description STRING
        )""",
    ),
    (
        "TRANSLATES",
        """CREATE REL TABLE IF NOT EXISTS TRANSLATES (
            FROM Component TO Interrupt,
            description STRING
        )""",
    ),
    (
        "STREAMS_TO",
        """CREATE REL TABLE IF NOT EXISTS STREAMS_TO (
            FROM Component TO Component,
            bandwidth_mbps DOUBLE,
            description    STRING
        )""",
    ),
    (
        "DMA_TO",
        """CREATE REL TABLE IF NOT EXISTS DMA_TO (
            FROM Component TO Component,
            channel     STRING,
            description STRING
        )""",
    ),
    (
        "SHARED_WITH",
        """CREATE REL TABLE IF NOT EXISTS SHARED_WITH (
            FROM Component TO Component,
            description STRING
        )""",
    ),
    (
        "CAUSED_BY",
        """CREATE REL TABLE IF NOT EXISTS CAUSED_BY (
            FROM FailureMode TO Component,
            description STRING
        )""",
    ),
    (
        "AFFECTS_IF_REMOVED",
        """CREATE REL TABLE IF NOT EXISTS AFFECTS_IF_REMOVED (
            FROM Component TO Component,
            description STRING
        )""",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_schema(conn: kuzu.Connection) -> None:
    """Create all node and relationship tables in *conn*.

    Safe to call multiple times — uses ``IF NOT EXISTS`` throughout.
    """
    for table_name, ddl in NODE_TABLES:
        conn.execute(ddl)
        print(f"  [schema] node table ready: {table_name}")

    for table_name, ddl in REL_TABLES:
        conn.execute(ddl)
        print(f"  [schema] rel  table ready: {table_name}")


def list_tables(conn: kuzu.Connection) -> dict[str, list[str]]:
    """Return a dict listing node and relationship table names that exist."""
    node_names = [n for n, _ in NODE_TABLES]
    rel_names = [n for n, _ in REL_TABLES]
    return {"node_tables": node_names, "rel_tables": rel_names}


if __name__ == "__main__":
    import os
    _here = os.path.dirname(os.path.abspath(__file__))
    _db_path = os.path.join(_here, "..", "base", "bsp_base.db")
    db = kuzu.Database(_db_path)
    conn = kuzu.Connection(db)
    create_schema(conn)
    print("Schema created successfully.")
