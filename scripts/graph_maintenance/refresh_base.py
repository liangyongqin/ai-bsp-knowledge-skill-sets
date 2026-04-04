#!/usr/bin/env python3
"""
refresh_base.py — Re-run all seed scripts to rebuild the base graph from scratch.

Usage::

    python3 scripts/graph_maintenance/refresh_base.py [--db-path PATH] [--dry-run]

This is a thin wrapper around build_base_graph.py that always uses --clean.
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..")
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")

sys.path.insert(0, _SCRIPTS_DIR)

DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "bsp_base.db")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild the BSP base knowledge graph from scratch using all seed scripts."
    )
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to Kuzu database directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying the database",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("[refresh] DRY RUN — no changes will be made.")
        print(f"[refresh] Would delete and rebuild: {args.db_path}")

        # Import build script to show script list
        import build_base_graph
        print("[refresh] Seed scripts that would run:")
        for script in build_base_graph.INGEST_SCRIPTS:
            path = os.path.join(build_base_graph._BASE_DIR, script)
            exists = os.path.isfile(path)
            status = "OK" if exists else "MISSING"
            print(f"  [{status}] {script}")
        return

    print("[refresh] Rebuilding base graph from scratch (--clean mode)...")
    import build_base_graph
    build_base_graph.build(db_path=args.db_path, clean=True)
    print("[refresh] Done.")


if __name__ == "__main__":
    main()
