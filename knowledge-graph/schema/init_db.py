"""
BSP Knowledge Graph — database initialisation script.

Creates (or opens) the Kuzu DB at knowledge-graph/base/bsp_base.db and
applies the full schema.  Safe to re-run — all DDL uses IF NOT EXISTS.

Usage::

    python knowledge-graph/schema/init_db.py [--db-path PATH]
"""

import argparse
import os
import sys

# Allow running as a standalone script from any working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..")
sys.path.insert(0, _HERE)

import kuzu
import schema as _schema


DEFAULT_DB_PATH = os.path.join(_HERE, "..", "base", "bsp_base.db")


def init_db(db_path: str = DEFAULT_DB_PATH) -> kuzu.Connection:
    """Initialise (or open) the Kuzu database and apply the schema.

    Parameters
    ----------
    db_path:
        Filesystem path to the Kuzu database directory.

    Returns
    -------
    kuzu.Connection
        An open connection to the initialised database.
    """
    db_path = os.path.abspath(db_path)
    # Ensure parent directory exists; Kuzu manages the DB file itself.
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    already_existed = os.path.isfile(db_path)

    if already_existed:
        print(f"[init_db] Opening existing database at: {db_path}")
    else:
        print(f"[init_db] Creating new database at:    {db_path}")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    print("[init_db] Applying schema …")
    _schema.create_schema(conn)

    print("[init_db] Schema applied successfully.")
    return conn


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise the BSP Kuzu knowledge graph.")
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to Kuzu database directory (default: knowledge-graph/base/bsp_base.db)",
    )
    args = parser.parse_args()
    init_db(args.db_path)
    print("[init_db] Done.")


if __name__ == "__main__":
    main()
