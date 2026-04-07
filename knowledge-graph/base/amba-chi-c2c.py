"""
AMBA CHI C2C (Chip-to-Chip) seed — open-source knowledge ingestion.

Adds the CHI C2C specification (IHI0098) for chiplet interconnect,
plus CHI Issue G updates not covered by amba-chi-interconnect.py.

Sources:
  - AMBA CHI C2C Specification IHI0098 — developer.arm.com/documentation/IHI0098
  - AMBA CHI Architecture Spec IHI0050G — developer.arm.com/documentation/ihi0050
  - ARM CHI C2C announcement — newsroom.arm.com
  - ARM AMBA 5 overview — arm.com/architecture/system-architectures/amba/amba-5

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
# Components — CHI C2C (IHI0098)
# ---------------------------------------------------------------------------

_CHI_C2C_COMPONENTS = [
    ("CHI-C2C-Link", "interconnect", "ARM",
     "AMBA CHI C2C Link Layer — packetizes CHI protocol messages for chip-to-chip "
     "transport over UCIe or proprietary PHY; maintains CHI coherency semantics "
     "across die boundaries without complex protocol translation",
     "base"),
    ("CHI-C2C-Bridge", "interconnect", "ARM",
     "CHI C2C Bridge — translates on-chip CHI transactions to C2C link format; "
     "handles credit-based flow control, link-layer retransmission, and "
     "packet ordering across chiplet boundaries",
     "base"),
    ("CHI-C2C-Realm-Mgmt", "security", "ARM",
     "CHI C2C Realm Management — extends ARM CCA/RME across chiplet boundaries; "
     "Granule Protection Table (GPT) checks enforced at C2C bridge; "
     "confidential compute maintained across multi-chip SMP",
     "base"),
    ("CHI-C2C-UCIe-Adapter", "interconnect", "ARM",
     "CHI C2C UCIe Adapter — maps CHI C2C packets to UCIe streaming interface; "
     "UCIe provides physical die-to-die connectivity while CHI C2C provides "
     "the coherent protocol layer; complementary standards",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — CHI Issue G updates
# ---------------------------------------------------------------------------

_CHI_G_COMPONENTS = [
    ("CHI-IssueG-Atomic-Ops", "interconnect", "ARM",
     "CHI Issue G Atomic Operations — enhanced atomic transaction support; "
     "near-data atomics at HN-F reduce round-trip latency for lock-contended "
     "workloads in multi-cluster SoCs",
     "base"),
    ("CHI-IssueG-MPAM-QoS", "qos", "ARM",
     "CHI Issue G MPAM QoS Integration — PARTID/PMG fields carried in CHI "
     "request/snoop/data flits; enables end-to-end QoS from CPU through "
     "interconnect to memory controller",
     "base"),
    ("CHI-IssueG-DMT", "interconnect", "ARM",
     "CHI Issue G Direct Memory Transfer (DMT) — allows memory controller to "
     "send data directly to requester bypassing HN-F; reduces read latency "
     "for non-cached accesses",
     "base"),
    ("CHI-IssueG-DWT", "interconnect", "ARM",
     "CHI Issue G Direct Write Transfer (DWT) — combined write that sends "
     "data directly to memory controller and HN-F simultaneously; "
     "reduces write-back latency for evictions",
     "base"),
    ("CHI-IssueG-PrefetchTgt", "interconnect", "ARM",
     "CHI Issue G PrefetchTgt — targeted prefetch requests that traverse "
     "interconnect to pre-fill HN-F or SN-F caches; reduces compulsory "
     "misses for predictable access patterns",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Multi-chip topology
# ---------------------------------------------------------------------------

_MULTICHIP_COMPONENTS = [
    ("Multi-Chip-SMP", "platform", "ARM",
     "Multi-Chip SMP via CHI C2C — hardware-coherent symmetric multiprocessing "
     "across multiple chiplets; OS sees single SMP domain; NUMA-aware scheduling "
     "recommended for cross-chip latency; uses CHI C2C for inter-die coherency",
     "base"),
    ("Coherent-Accelerator-Attach", "platform", "ARM",
     "Coherent Accelerator Attach via CHI C2C — GPU/NPU/custom accelerator on "
     "separate die connected via CHI C2C; shares virtual address space with CPUs; "
     "enables zero-copy data sharing between CPU and accelerator chiplets",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_C2C_FAILURES = [
    ("FM-CHI-C2C-Link-CRC-Error",
     "CHI C2C link CRC errors; interconnect reports packet corruption; "
     "cross-chip transactions fail or retry excessively",
     "Physical interconnect signal integrity issue between chiplets; "
     "check UCIe/PHY training status, die-to-die voltage levels, "
     "and silicon interposer/bridge quality; may indicate aging or thermal stress",
     "interconnect",
     "AMBA CHI C2C Specification IHI0098",
     "base"),
    ("FM-CHI-C2C-Credit-Deadlock",
     "Cross-chip CHI transactions stall; both sides waiting for credits; "
     "system hangs or watchdog fires",
     "CHI C2C credit pool exhaustion; circular dependency between request and "
     "snoop channels across chiplet boundary; increase credit pool depth or "
     "enable link-layer timeout/recovery mechanism",
     "interconnect",
     "AMBA CHI C2C Specification IHI0098 — Flow Control",
     "base"),
    ("FM-CHI-C2C-Realm-GPT-Mismatch",
     "CCA Realm access to cross-chip memory fails with GPT fault; "
     "confidential VM cannot access memory on remote chiplet",
     "GPT tables not synchronized across chiplets; each chip's GPC must reflect "
     "the same granule ownership for shared physical address ranges; "
     "verify GPT programming in TF-A for multi-chip topology",
     "security",
     "AMBA CHI C2C IHI0098 — Realm Management Extension",
     "base"),
    ("FM-CHI-DMT-Ordering-Violation",
     "Memory ordering violation in multi-chip config; observer on remote chip "
     "sees stale data despite barrier execution",
     "Direct Memory Transfer (DMT) bypasses HN-F ordering point; ensure DMB/DSB "
     "barriers are used and CHI ordering rules are met for cross-chip accesses; "
     "may need to disable DMT for strict ordering workloads",
     "interconnect",
     "AMBA CHI Architecture Spec IHI0050G — Ordering",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = _CHI_C2C_COMPONENTS + _CHI_G_COMPONENTS + _MULTICHIP_COMPONENTS
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _C2C_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # C2C Link → Bridge
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-C2C-Bridge", dst_name="CHI-C2C-Link")

    # C2C Link → UCIe adapter
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-C2C-Link", dst_name="CHI-C2C-UCIe-Adapter")

    # Realm management → CCA (from arm-trustzone-tfa.py)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-C2C-Realm-Mgmt", dst_name="ARM-CCA-RMM")

    # CHI C2C Bridge → existing CHI interconnect nodes
    for node in ("CHI-RN-F", "CHI-HN-F", "CHI-SN-F"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="CHI-C2C-Bridge", dst_name=node)

    # Issue G features → HN-F
    for feat in ("CHI-IssueG-Atomic-Ops", "CHI-IssueG-DMT",
                 "CHI-IssueG-DWT", "CHI-IssueG-PrefetchTgt"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=feat, dst_name="CHI-HN-F")

    # MPAM QoS → existing MPAM
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CHI-IssueG-MPAM-QoS", dst_name="ARMv9-MPAM")

    # Multi-chip platform → C2C link
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Multi-Chip-SMP", dst_name="CHI-C2C-Link")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="Coherent-Accelerator-Attach", dst_name="CHI-C2C-Link")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-CHI-C2C-Link-CRC-Error", "CHI-C2C-Link"),
        ("FM-CHI-C2C-Credit-Deadlock", "CHI-C2C-Bridge"),
        ("FM-CHI-C2C-Realm-GPT-Mismatch", "CHI-C2C-Realm-Mgmt"),
        ("FM-CHI-DMT-Ordering-Violation", "CHI-IssueG-DMT"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[amba-chi-c2c] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
