"""
Build Base Knowledge Graph — orchestration script.

Runs all seed ingestion scripts in the correct order to populate
knowledge-graph/base/bsp_base.db from open-source BSP knowledge.

Usage::

    python scripts/build_base_graph.py [--db-path PATH] [--clean]
"""

import argparse
import importlib.util
import os
import sys
import time

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")

sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _BASE_DIR)

DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "bsp_base.db")

# Ordered list of ingestion scripts relative to _BASE_DIR
INGEST_SCRIPTS = [
    "arm-gic-600.py",
    "arm-amba-axi.py",
    "arm-cpu-cluster.py",
    "arm-cortex-v9.py",
    "arm-c1-cpu-family.py",
    "arm-smmu-v3.py",
    "arm-gicv5.py",
    "arm-trustzone-tfa.py",
    "arm-ras-extensions.py",
    "amba-chi-interconnect.py",
    "amba-chi-c2c.py",
    "armv9-extensions-update.py",
    "linux-dvfs-eas.py",
    "linux-devfreq-qos.py",
    "linux-suspend-hibernate.py",
    "linux-platform-devices.py",
    "linux-clock-tree.py",
    "linux-thermal-framework.py",
    "linux-kernel-pm-updates.py",
    "mipi-camera-subsystem.py",
    "mipi-dsi-display.py",
    "gpu-subsystem.py",
    "common-failure-modes.py",
    "arm-registers-key.py",
    "linux-drm-panic-gpu-recovery.py",
    "mipi-evs-thermal-netlink.py",
    "linux-regulator-arm-memory.py",
    "linux-virt-cpufreq-acpm.py",
    "arm-css-v2-2024.py",
    "arm-gic-700.py",
    "linux-thermal-pcie-cooling.py",
    "mipi-csi2-v4-features.py",
    "linux-panthor-drm-csf.py",
    "arm-gic-nmi-v42.py",
    "arm-coresight-full.py",       # CoreSight trace: ETF/ETR/ETS/STM/TPIU/CTI
    "linux-lpddr5x-ufs4.py",       # LPDDR5X (JESD79-5B) + UFS 4.0 (JESD220F)
    "fix-orphan-connectivity.py",  # links orphan nodes from all prior scripts
    "fix-orphan-connectivity-2.py",  # remaining orphans + sparse rels + hw-spec FMs
    "fix-orphan-connectivity-3.py",  # must run last — final 2 orphan Components + 5 disconnected FMs
]


def _load_script(script_path: str):
    """Dynamically load a Python script as a module."""
    module_name = os.path.splitext(os.path.basename(script_path))[0]
    # Python module names cannot start with digits or contain hyphens.
    safe_name = "ingest_" + module_name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(safe_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _count_nodes(db_path: str) -> int:
    """Return the total node count across all node tables."""
    import kuzu
    import schema as _schema  # noqa: F401 -- ensure tables exist

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    tables = ["Component", "PowerDomain", "ClockSource", "Register", "Interrupt", "FailureMode"]
    total = 0
    for table in tables:
        try:
            result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
            if result.has_next():
                total += result.get_next()[0]
        except Exception:
            pass
    return total


def build(db_path: str = DEFAULT_DB_PATH, clean: bool = False) -> None:
    """Orchestrate the full base graph build.

    Parameters
    ----------
    db_path:
        Path to the Kuzu database directory.
    clean:
        If True, delete an existing database before rebuilding.
    """
    db_path = os.path.abspath(db_path)

    if clean and os.path.exists(db_path):
        import shutil
        print(f"[build] Removing existing database at {db_path} …")
        if os.path.isdir(db_path):
            shutil.rmtree(db_path)
        else:
            os.remove(db_path)
        # Also remove WAL file if present
        wal = db_path + ".wal"
        if os.path.exists(wal):
            os.remove(wal)

    # Ensure DB and schema exist; close connection after schema setup.
    import kuzu
    import schema as _schema

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _init_db = kuzu.Database(db_path)
    _init_conn = kuzu.Connection(_init_db)
    _schema.create_schema(_init_conn)
    # Release initial connection so ingestion scripts can open their own.
    del _init_conn, _init_db
    print(f"[build] Database ready at {db_path}")

    overall_start = time.perf_counter()
    total_inserted = 0

    for script_name in INGEST_SCRIPTS:
        script_path = os.path.join(_BASE_DIR, script_name)
        if not os.path.isfile(script_path):
            print(f"[build] WARNING: Script not found: {script_path} — skipping.")
            continue

        print(f"\n[build] ── Running {script_name} …")
        t0 = time.perf_counter()
        try:
            module = _load_script(script_path)
            n = module.ingest(db_path=db_path)
            elapsed = time.perf_counter() - t0
            total_inserted += n
            print(f"[build] ✓ {script_name}: {n} nodes inserted ({elapsed:.2f}s)")
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"[build] ✗ {script_name}: FAILED after {elapsed:.2f}s — {exc}")
            raise

    overall_elapsed = time.perf_counter() - overall_start
    final_count = _count_nodes(db_path)

    print(f"\n[build] ══════════════════════════════════════")
    print(f"[build]  Seed nodes inserted  : {total_inserted}")
    print(f"[build]  Total nodes in DB    : {final_count}")
    print(f"[build]  Total elapsed time   : {overall_elapsed:.2f}s")
    print(f"[build]  Database path        : {db_path}")
    print(f"[build] ══════════════════════════════════════")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the BSP base knowledge graph from open-source seed data."
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to Kuzu database directory",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing DB before rebuilding",
    )
    args = parser.parse_args()
    build(db_path=args.db_path, clean=args.clean)


if __name__ == "__main__":
    main()
