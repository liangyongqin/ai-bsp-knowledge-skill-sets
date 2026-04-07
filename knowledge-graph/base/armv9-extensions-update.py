"""
ARMv9 architecture extensions update — v9.5 through v9.7.

Adds newer ARMv9 extension features not covered by arm-cortex-v9.py:
  - ARMv9.5-A: FEAT_CPA, FEAT_FAMINMAX, FEAT_LUT
  - ARMv9.6-A: FEAT_SVE2p2, FEAT_SME2p2, FEAT_SVE_AES2, FEAT_PoPS
  - ARMv9.7-A: MPAMv2, domain-based TLB invalidation, MXFP6, video codec insns

Sources:
  - ARM A-Profile Architecture Developments 2025 blog — developer.arm.com
  - ARM Architecture Reference Manual Supplement — Armv9.6-A, Armv9.7-A
  - GCC 16 Armv9.6-A support patches — Phoronix (2025)

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
# Components — ARMv9.5-A extensions
# ---------------------------------------------------------------------------

_V95_FEATURES = [
    ("ARMv9.5-CPA", "isa-extension", "ARM",
     "FEAT_CPA — Checked Pointer Arithmetic; hardware-checked pointer ops "
     "to detect pointer corruption; complements MTE for memory safety",
     "base"),
    ("ARMv9.5-FAMINMAX", "isa-extension", "ARM",
     "FEAT_FAMINMAX — Floating-point Absolute Min/Max for Advanced SIMD and SVE; "
     "single-instruction min/max of absolute values; useful for neural network activation normalization",
     "base"),
    ("ARMv9.5-LUT", "isa-extension", "ARM",
     "FEAT_LUT — Lookup Table instructions for Advanced SIMD and SVE; "
     "hardware-accelerated table lookups; enables efficient quantized neural network inference",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — ARMv9.6-A extensions
# ---------------------------------------------------------------------------

_V96_FEATURES = [
    ("ARMv9.6-SVE2p2", "isa-extension", "ARM",
     "FEAT_SVE2p2 — SVE2 enhancements in Armv9.6; additional predicated operations, "
     "improved gather/scatter performance, mandatory for ARMv9.6-A implementations",
     "base"),
    ("ARMv9.6-SME2p2", "isa-extension", "ARM",
     "FEAT_SME2p2 — SME2 enhancements in Armv9.6; additional matrix tile ops, "
     "FEAT_SME_MOP4 for 4-way outer product, FEAT_TMOP for table MOPs",
     "base"),
    ("ARMv9.6-SVE-AES2", "isa-extension", "ARM",
     "FEAT_SVE_AES2 — Wider SVE AES instructions; 256-bit+ AES processing, "
     "significant crypto throughput improvement for storage/network encryption",
     "base"),
    ("ARMv9.6-PoPS", "isa-extension", "ARM",
     "FEAT_PoPS — Point-of-Physical-Storage clean/invalidate; cache maintenance "
     "operations to PoPS instead of PoC; critical for persistent memory and CXL devices",
     "base"),
    ("ARMv9.6-CMPBR", "isa-extension", "ARM",
     "FEAT_CMPBR — Compare-and-Branch instructions; fused compare+branch for "
     "integer/pointer comparisons; reduces branch misprediction overhead",
     "base"),
    ("ARMv9.6-LSUI", "isa-extension", "ARM",
     "FEAT_LSUI — Load/Store unprivileged immediate; new addressing modes for "
     "unprivileged access with immediate offsets; simplifies kernel→user data copy",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — ARMv9.7-A extensions
# ---------------------------------------------------------------------------

_V97_FEATURES = [
    ("ARMv9.7-MPAMv2", "qos", "ARM",
     "MPAMv2 (Memory Partitioning and Monitoring v2) — independent PARTIDs and PMGs, "
     "16-bit PMGs (up from 8-bit); finer-grained cache/memory partitioning; "
     "critical for SoC QoS in multi-tenant/multi-VM configurations",
     "base"),
    ("ARMv9.7-Domain-TLB-Inv", "isa-extension", "ARM",
     "Domain-based TLB Invalidation — ARMv9.7-A; invalidate TLB entries by domain "
     "rather than address range; reduces TLB maintenance overhead in multi-cluster SoCs",
     "base"),
    ("ARMv9.7-MXFP6", "isa-extension", "ARM",
     "OCP MXFP6 (6-bit Microscaling Floating Point) — SVE/SME instructions for "
     "6-bit data types per OCP Microscaling specification; "
     "enables sub-8-bit inference on CPU for edge AI workloads",
     "base"),
    ("ARMv9.7-Video-Codec", "isa-extension", "ARM",
     "ARMv9.7 Video Codec Instructions — SABAL, UABAL, SQRSHRN, UQRSHRN, ADDQP; "
     "accelerate video encode/decode SAD and quantization operations on CPU; "
     "reduces reliance on dedicated VPU for lightweight codec tasks",
     "base"),
    ("ARMv9.7-LOR-Realms", "isa-extension", "ARM",
     "Limited Ordering Regions for Realms — ARMv9.7-A extends LOR to Realm world; "
     "enables performance-optimized memory ordering for confidential VMs",
     "base"),
    ("ARMv9.7-Split-PAC", "isa-extension", "ARM",
     "Separate Kernel/User PAC Controls — ARMv9.7-A; independent Pointer Authentication "
     "configuration for kernel and user mode; reduces PAC overhead when only one mode needs it",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_EXT_FAILURES = [
    ("FM-MPAMv2-PARTID-Exhaustion",
     "MPAMv2 PARTID space exhausted; new VMs cannot get dedicated partitions",
     "Too many concurrent partitions requested; MPAMv2 allows 16-bit PMGs but PARTID "
     "count is implementation-defined; consolidate partitions or use hierarchical grouping",
     "qos",
     "ARM Architecture Reference Manual — MPAM Extension",
     "base"),
    ("FM-MXFP6-Precision-Loss",
     "AI inference accuracy degraded when using MXFP6 quantization on C1 cores",
     "MXFP6 (6-bit) quantization too aggressive for model; not all layers tolerate "
     "sub-8-bit precision; use mixed precision with FP16 for sensitive layers",
     "cpu",
     "OCP Microscaling Formats specification / ARM SME Programmer's Guide",
     "base"),
    ("FM-SVE-AES2-Unsupported",
     "AES throughput not improved despite SVE2; falls back to 128-bit AES",
     "FEAT_SVE_AES2 not implemented on target SoC (optional in ARMv9.6); "
     "check ID_AA64ZFR0_EL1.AES field; fallback to NEON AES or hardware crypto engine",
     "cpu",
     "ARM Architecture Reference Manual — SVE2 Crypto Extensions",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = _V95_FEATURES + _V96_FEATURES + _V97_FEATURES
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _EXT_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # MPAMv2 → existing MPAM node (evolution)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9.7-MPAMv2", dst_name="DSU-120-L3")

    # MXFP6 → SME2 (uses SME tile operations)
    create_rel(conn, "DEPENDS_ON_CLOCK", "Component", "Component",
               src_name="ARMv9.7-MXFP6", dst_name="ARMv9.3-SME2")

    # Video codec → multimedia pipeline (relates to ISP/codec)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9.7-Video-Codec", dst_name="ISP-pipeline")

    # SVE2p2 → SVE2 base
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9.6-SVE2p2", dst_name="ARMv9-SVE2")

    # SME2p2 → SME2
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARMv9.6-SME2p2", dst_name="ARMv9.3-SME2")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-MPAMv2-PARTID-Exhaustion", "ARMv9.7-MPAMv2"),
        ("FM-MXFP6-Precision-Loss", "ARMv9.7-MXFP6"),
        ("FM-SVE-AES2-Unsupported", "ARMv9.6-SVE-AES2"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[armv9-extensions-update] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
