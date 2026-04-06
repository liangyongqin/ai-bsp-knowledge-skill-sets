"""
AMBA 5 CHI (Coherent Hub Interface) interconnect seed — open-source knowledge ingestion.

Adds AMBA CHI protocol components and ARM CoreLink mesh interconnect nodes
that connect CPU clusters, GPU, memory controllers, and I/O in modern SoCs.

Sources:
  - AMBA 5 CHI Architecture Specification (ARM IHI0050)
  - ARM CoreLink CMN-600 TRM (ARM DDI 0588)
  - ARM CoreLink CMN-700 TRM (ARM DDI 0616)
  - ARM developer.arm.com/documentation/102407 (CHI introduction)
  - gem5 CHI documentation (gem5.org)

Namespace: base (open-source only)
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "schema")
sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _HERE)

import kuzu
import schema as _schema
from _ingest_helpers import upsert_node, create_rel

# ---------------------------------------------------------------------------
# Components — CHI protocol layers
# ---------------------------------------------------------------------------

_CHI_PROTOCOL = [
    ("CHI-Protocol-Layer",    "protocol",     "ARM",
     "AMBA 5 CHI Protocol Layer — defines transaction types (ReadNoSnp, ReadShared, WriteBack, "
     "WriteClean, etc.), coherency states (I/SC/UC/SD/UD), and ordering rules; "
     "layered on top of network and link layers",
     "base"),
    ("CHI-Network-Layer",     "protocol",     "ARM",
     "AMBA 5 CHI Network Layer — packet routing between Request/Home/Subordinate nodes, "
     "supports ring, mesh, crossbar topologies; NodeID-based addressing",
     "base"),
    ("CHI-Link-Layer",        "protocol",     "ARM",
     "AMBA 5 CHI Link Layer — flow control (L-credit), channel management "
     "(REQ, RSP, SNP, DAT channels), error detection (poison/data check)",
     "base"),
    ("CHI-SNP-Filter",        "protocol",     "ARM",
     "CHI Snoop Filter — tracks cacheline state across RN-F nodes, "
     "reduces snoop traffic by filtering unnecessary coherency probes; "
     "critical for multi-cluster SoC performance",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — CHI node types
# ---------------------------------------------------------------------------

_CHI_NODES = [
    ("CHI-RN-F",              "interconnect", "ARM",
     "CHI Request Node Fully-coherent (RN-F) — CPU cluster or GPU with full cache coherency, "
     "participates in snooping protocol; connects DSU-110/DSU-120 to mesh",
     "base"),
    ("CHI-RN-I",              "interconnect", "ARM",
     "CHI Request Node I/O-coherent (RN-I) — I/O master with I/O coherency but no snooping, "
     "used for PCIe root complex, USB, and peripheral DMA masters",
     "base"),
    ("CHI-RN-D",              "interconnect", "ARM",
     "CHI Request Node DVM-only (RN-D) — distributes DVM (Distributed Virtual Memory) "
     "maintenance operations; used for SMMU TLB invalidation broadcast",
     "base"),
    ("CHI-HN-F",              "interconnect", "ARM",
     "CHI Home Node Fully-coherent (HN-F) — point of coherency (PoC) for a memory region, "
     "includes snoop filter and directory; serialises conflicting requests",
     "base"),
    ("CHI-HN-I",              "interconnect", "ARM",
     "CHI Home Node I/O (HN-I) — routes non-cacheable I/O transactions to peripheral ports; "
     "no coherency tracking",
     "base"),
    ("CHI-SN-F",              "interconnect", "ARM",
     "CHI Subordinate Node Full (SN-F) — memory controller interface, accepts read/write "
     "from HN-F for DRAM access; typically connects to DDR/LPDDR controller",
     "base"),
    ("CHI-MN",                "interconnect", "ARM",
     "CHI Miscellaneous Node (MN) — handles DVM operations, barrier synchronisation, "
     "and system-level maintenance across the mesh",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — ARM CoreLink CMN implementations
# ---------------------------------------------------------------------------

_CMN_COMPONENTS = [
    ("CMN-600",               "interconnect", "ARM",
     "ARM CoreLink CMN-600 — first-gen CHI mesh interconnect, "
     "up to 64 cross-points (8x8 mesh), 32 CPU clusters, integrated L3/system cache (SLC); "
     "supports CHI Issue B",
     "base"),
    ("CMN-700",               "interconnect", "ARM",
     "ARM CoreLink CMN-700 — second-gen CHI mesh interconnect, "
     "up to 144 cross-points (12x12 mesh), 256 CPUs, CHI Issue C/D support, "
     "MPAM QoS, hardware coherent accelerator (HCA) ports for CXL/CCIX; "
     "used in Neoverse and high-end mobile SoCs",
     "base"),
    ("CMN-SLC",               "cache",        "ARM",
     "CMN System Level Cache (SLC) — distributed L3/last-level cache slices across mesh nodes, "
     "capacity 1–256MB aggregate; tag directory at HN-F; MOESI coherency",
     "base"),
    ("CMN-PMU",               "pmu",          "ARM",
     "CMN Performance Monitoring Unit — mesh-level events: cache hit/miss per HN-F, "
     "cross-point utilisation, snoop filter efficiency, CHI channel occupancy; "
     "exposed to Linux perf via arm-cmn driver",
     "base"),
    ("CMN-Debug-Trace",       "trace",        "ARM",
     "CMN Debug and Trace — CHI transaction trace via DTC (Debug Trace Controller), "
     "watchpoint triggers on address/NodeID/opcode patterns; "
     "feeds into CoreSight infrastructure",
     "base"),
    ("linux-arm-cmn",         "driver",       "linux",
     "Linux arm-cmn PMU driver (drivers/perf/arm-cmn.c) — "
     "exposes CMN-600/700 mesh performance counters to perf tool; "
     "event groups: hnf (home node), rnf (request node), xp (cross-point)",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_CHI_FAILURES = [
    ("FM-CHI-Deadlock",
     "System hang; all CPU cores stalled; no progress on memory transactions",
     "CHI protocol deadlock due to circular dependency between HN-F snoop responses "
     "and RN-F retry requests; typically caused by misconfigured QoS credits or "
     "snoop filter capacity overflow",
     "interconnect",
     "ARM CHI spec IHI0050 §3.14 (Deadlock Avoidance)",
     "base"),
    ("FM-CMN-SLC-Thrash",
     "Last-level cache (SLC) hit rate drops below 30%; memory bandwidth saturated",
     "SLC capacity insufficient for working set; competing workloads evict each other's lines; "
     "consider MPAM cache partitioning or increasing SLC allocation per HN-F",
     "interconnect",
     "ARM CMN-700 TRM §7 (Performance Tuning)",
     "base"),
    ("FM-CHI-Poison-Data",
     "Data poisoning detected at HN-F; RAS error event; potential silent data corruption",
     "ECC error in SLC or DRAM detected and propagated as CHI poison bit; "
     "consumer must check poison flag; source is upstream memory subsystem fault",
     "memory",
     "ARM CHI spec IHI0050 §9 (RAS)",
     "base"),
    ("FM-CMN-XP-Congestion",
     "Latency spikes on specific memory regions; CMN PMU shows high XP utilisation",
     "Cross-point (XP) node saturated due to traffic hotspot; address interleaving "
     "not distributing load across HN-F nodes evenly; review SLC hashing scheme",
     "interconnect",
     "ARM CMN-700 TRM §5 (Mesh Topology Design)",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = _CHI_PROTOCOL + _CHI_NODES + _CMN_COMPONENTS
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _CHI_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Protocol layers
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-Protocol-Layer", dst_name="CHI-Network-Layer")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-Network-Layer", dst_name="CHI-Link-Layer")

    # RN-F → HN-F (coherent request path)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-RN-F", dst_name="CHI-HN-F")
    # RN-I → HN-I (I/O path)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-RN-I", dst_name="CHI-HN-I")
    # HN-F → SN-F (memory access)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-HN-F", dst_name="CHI-SN-F")
    # HN-F includes snoop filter
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-HN-F", dst_name="CHI-SNP-Filter")
    # SN-F → DDR controller
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-SN-F", dst_name="DDR-Controller")

    # DSU clusters → RN-F (CPU coherency path)
    for dsu in ("DSU-110", "DSU-120"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=dsu, dst_name="CHI-RN-F")

    # CMN implementations contain HN-F, SLC, PMU
    for cmn in ("CMN-600", "CMN-700"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=cmn, dst_name="CHI-HN-F")
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=cmn, dst_name="CMN-SLC")

    # CMN PMU → perf
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CMN-PMU", dst_name="linux-arm-cmn")

    # CMN debug → CoreSight
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CMN-Debug-Trace", dst_name="CoreSight-funnel")

    # PCIe → RN-I (I/O coherent master)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="PCIe-Controller", dst_name="CHI-RN-I")

    # SMMU → RN-D (DVM broadcast for TLB invalidation)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="SMMU-v3", dst_name="CHI-RN-D")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-RN-D", dst_name="CHI-MN")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-CHI-Deadlock",       "CHI-HN-F"),
        ("FM-CMN-SLC-Thrash",     "CMN-SLC"),
        ("FM-CHI-Poison-Data",    "CHI-HN-F"),
        ("FM-CMN-XP-Congestion",  "CMN-700"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[amba-chi-interconnect] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
