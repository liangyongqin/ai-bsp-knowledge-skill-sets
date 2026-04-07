"""
ARM RAS (Reliability, Availability, Serviceability) extensions seed.

Adds ARM RAS architecture components relevant to BSP error handling:
  - RASv1 (mandatory from Armv8.2+)
  - RASv2 (Armv8.8+, FEAT_RASv2)
  - Error record registers and error types
  - Linux EDAC and rasdaemon integration
  - Firmware-first error handling (TF-A RAS)

Sources:
  - ARM RAS Extension Specification DDI0587 — developer.arm.com/documentation/ddi0587
  - ARM Architecture Reference Manual — RAS Extension chapters
  - TF-A RAS documentation — trustedfirmware-a.readthedocs.io
  - Linux Documentation/admin-guide/ras.rst
  - Linux Documentation/arch/arm64/ras.rst

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
# Components — RAS Architecture
# ---------------------------------------------------------------------------

_RAS_ARCH_COMPONENTS = [
    ("ARM-RAS-Extension", "isa-extension", "ARM",
     "ARM RAS Extension — Reliability, Availability, Serviceability; "
     "mandatory from Armv8.2+; system and memory-mapped error record registers; "
     "defines SEA, SError, fault handling, and error recovery interrupts; "
     "foundation for hardware error reporting in SoC BSP",
     "base"),
    ("ARM-RASv2", "isa-extension", "ARM",
     "ARM RASv2 (FEAT_RASv2, Armv8.8+) — enhanced error records with additional "
     "fields; improved error syndrome encoding; better deferred error handling; "
     "extended error record address range for complex SoCs",
     "base"),
    ("ARM-ESB", "isa-extension", "ARM",
     "Error Synchronization Barrier (ESB) — instruction that synchronizes "
     "asynchronous errors; makes pending SErrors synchronous at ESB boundary; "
     "critical for isolating error sources in kernel context switches",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Error Record System
# ---------------------------------------------------------------------------

_ERROR_RECORD_COMPONENTS = [
    ("RAS-Error-Record", "error-handling", "ARM",
     "ARM RAS Error Record — per-node error recording with status, address, "
     "and miscellaneous syndrome registers (ERR<n>STATUS, ERR<n>ADDR, ERR<n>MISC); "
     "each RAS node (CPU, cache, interconnect, memory controller) has "
     "one or more error records; system-mapped or memory-mapped access",
     "base"),
    ("RAS-SEA", "error-handling", "ARM",
     "Synchronous External Abort (SEA) — synchronous error delivered to the PE "
     "that caused it; typically from uncorrectable cache/memory errors on load/store; "
     "kernel handles via SIGBUS to user space or kernel panic for kernel accesses",
     "base"),
    ("RAS-SError", "error-handling", "ARM",
     "System Error (SError) — asynchronous error interrupt; may arrive delayed "
     "after the causing instruction; ESB instruction forces synchronization; "
     "typically from uncorrectable errors in write buffers or TLB walks; "
     "firmware-first handling routes through EL3 for classification",
     "base"),
    ("RAS-FHIR", "error-handling", "ARM",
     "Fault Handling Interrupt Request (FHIR) — interrupt for recoverable errors "
     "that require OS/firmware intervention but are not immediately fatal; "
     "allows graceful degradation (e.g., marking memory page as poisoned)",
     "base"),
    ("RAS-ERIR", "error-handling", "ARM",
     "Error Recovery Interrupt Request (ERIR) — interrupt for errors where "
     "hardware has already recovered (correctable ECC) but software needs to log "
     "and potentially take preventive action (e.g., page offline)",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Linux RAS Integration
# ---------------------------------------------------------------------------

_LINUX_RAS_COMPONENTS = [
    ("linux-edac-arm", "framework", "Linux",
     "Linux EDAC (Error Detection and Correction) for ARM — reports correctable "
     "and uncorrectable memory errors via /sys/devices/system/edac/; "
     "ARM-specific EDAC driver reads RAS error records from memory controllers; "
     "integrates with rasdaemon for persistent error logging",
     "base"),
    ("linux-rasdaemon", "tool", "Linux",
     "rasdaemon — user-space daemon that reads kernel trace events for hardware "
     "errors (MCE, EDAC, ARM processor errors, PCIe AER); stores error history "
     "in SQLite database; critical for field reliability analysis in BSP deployments",
     "base"),
    ("linux-arm64-ras-driver", "driver", "Linux",
     "ARM64 RAS driver (drivers/ras/arm64_ras.c) — handles ARM error records; "
     "registers with GHES (Generic Hardware Error Source) via ACPI/APEI or "
     "device tree; populates trace events for rasdaemon consumption",
     "base"),
    ("linux-ghes", "framework", "Linux",
     "Generic Hardware Error Source (GHES) — ACPI-based framework for firmware-first "
     "error reporting; firmware (TF-A) fills CPER (Common Platform Error Record) "
     "in shared memory; OS reads and processes the error; "
     "standard path for ARM RAS errors in ACPI-based platforms",
     "base"),
    ("linux-memory-poison", "framework", "Linux",
     "Memory Poisoning / HWPoison — kernel marks pages with uncorrectable errors "
     "as poisoned; prevents future allocation; processes accessing poisoned pages "
     "receive SIGBUS (BUS_MCEERR_AO / BUS_MCEERR_AR); "
     "integrates with RAS FHIR for graceful degradation",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Firmware-First RAS (TF-A)
# ---------------------------------------------------------------------------

_FW_RAS_COMPONENTS = [
    ("tfa-ras-handler", "firmware", "ARM",
     "TF-A RAS Error Handler — EL3 firmware-first handling of RAS errors; "
     "intercepts SError/SEA at highest privilege, classifies severity, "
     "populates CPER records for OS consumption via GHES; "
     "decides between: (1) recover, (2) report to OS, (3) system reset",
     "base"),
    ("tfa-sdei", "firmware", "ARM",
     "Software Delegated Exception Interface (SDEI) — firmware-to-OS notification "
     "mechanism for RAS events; TF-A uses SDEI to deliver error notifications "
     "to Linux kernel handler without requiring NMI; "
     "registered via SDEI_EVENT_REGISTER HVC call",
     "base"),
]

# ---------------------------------------------------------------------------
# Interrupts
# ---------------------------------------------------------------------------

_RAS_INTERRUPTS = [
    ("IRQ-RAS-FHIR", "FIQ", 0, "level-high", "base"),
    ("IRQ-RAS-ERIR", "SPI", 0, "level-high", "base"),
    ("IRQ-SDEI-RAS", "SPI", 0, "level-high", "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_RAS_FAILURES = [
    ("FM-RAS-Uncorrectable-Cache",
     "Kernel panic or SIGBUS after uncorrectable L2/L3 cache ECC error; "
     "RAS error record shows UE (Uncorrectable Error) status",
     "Hardware cache ECC failure; may indicate voltage droop, aging, or "
     "manufacturing defect; for L3: verify VDD_CPU rail stability; "
     "for correctable-to-uncorrectable escalation: check error count thresholds "
     "and consider page offlining before UE occurs",
     "memory",
     "ARM RAS Extension DDI0587 / Linux Documentation/admin-guide/ras.rst",
     "base"),
    ("FM-RAS-SError-Storm",
     "Continuous SError interrupts; system becomes unresponsive or resets; "
     "firmware RAS handler overwhelmed",
     "Persistent hardware error source generating repeated asynchronous errors; "
     "common causes: failed memory DIMM, interconnect link error, or stuck "
     "peripheral DMA; firmware-first handler should blacklist error source "
     "after threshold; check TF-A RAS policy configuration",
     "cpu",
     "ARM Architecture Reference Manual — SError handling",
     "base"),
    ("FM-RAS-GHES-Missing",
     "Linux kernel does not report hardware errors despite RAS-capable SoC; "
     "EDAC shows no controllers; rasdaemon has no events",
     "ACPI HEST (Hardware Error Source Table) not populated by firmware; "
     "or platform uses device tree without GHES alternative; "
     "check ACPI table presence and TF-A GHES configuration; "
     "for DT platforms: use ARM64 RAS driver instead of GHES",
     "boot",
     "TF-A RAS documentation / ACPI APEI specification",
     "base"),
    ("FM-RAS-Memory-Poison-Leak",
     "Application crashes with SIGBUS on previously-working memory; "
     "HWPoison page count increasing over time",
     "Progressive memory degradation; correctable errors escalating to "
     "uncorrectable; check rasdaemon error history for specific DIMM/rank; "
     "may need physical memory replacement in field; "
     "kernel can migrate pages proactively with CONFIG_MEMORY_FAILURE",
     "memory",
     "Linux Documentation/vm/hwpoison.rst",
     "base"),
    ("FM-SDEI-Delivery-Failure",
     "RAS error detected by firmware but Linux kernel never receives notification; "
     "errors silently dropped",
     "SDEI event not registered by kernel; or SDEI handler interrupted by higher "
     "priority exception; verify kernel CONFIG_ARM_SDE_INTERFACE enabled; "
     "check that TF-A SDEI dispatch table is correctly configured for the platform",
     "cpu",
     "ARM SDEI Specification DEN0054 / TF-A SDEI documentation",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    all_components = (
        _RAS_ARCH_COMPONENTS + _ERROR_RECORD_COMPONENTS +
        _LINUX_RAS_COMPONENTS + _FW_RAS_COMPONENTS
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    for name, irq_type, irq_id, trigger, ns in _RAS_INTERRUPTS:
        if upsert_node(conn, "Interrupt", {
            "name": name, "irq_type": irq_type, "irq_id": irq_id,
            "trigger": trigger, "namespace": ns,
        }):
            inserted += 1

    for name, symptom, root_cause, affected_domain, source, ns in _RAS_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # RASv2 extends RAS
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-RASv2", dst_name="ARM-RAS-Extension")

    # Error types → RAS extension
    for err_type in ("RAS-SEA", "RAS-SError", "RAS-FHIR", "RAS-ERIR"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=err_type, dst_name="ARM-RAS-Extension")

    # Error record → error types
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="RAS-Error-Record", dst_name="RAS-SEA")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="RAS-Error-Record", dst_name="RAS-SError")

    # ESB → SError synchronization
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="ARM-ESB", dst_name="RAS-SError")

    # Linux EDAC → error records
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-edac-arm", dst_name="RAS-Error-Record")

    # rasdaemon → EDAC
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-rasdaemon", dst_name="linux-edac-arm")

    # ARM64 RAS driver → GHES or direct
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-arm64-ras-driver", dst_name="linux-ghes")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-arm64-ras-driver", dst_name="RAS-Error-Record")

    # GHES → firmware handler
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-ghes", dst_name="tfa-ras-handler")

    # Memory poison → FHIR
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-memory-poison", dst_name="RAS-FHIR")

    # TF-A RAS → SDEI delivery
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="tfa-ras-handler", dst_name="tfa-sdei")

    # SDEI → existing ARM-SDEI if present, or standalone
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="tfa-sdei", dst_name="linux-arm64-ras-driver")

    # Failure → root component
    for fm_name, comp_name in [
        ("FM-RAS-Uncorrectable-Cache", "RAS-Error-Record"),
        ("FM-RAS-SError-Storm", "RAS-SError"),
        ("FM-RAS-GHES-Missing", "linux-ghes"),
        ("FM-RAS-Memory-Poison-Leak", "linux-memory-poison"),
        ("FM-SDEI-Delivery-Failure", "tfa-sdei"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    # Connect RAS to existing GIC (error interrupts route through GIC)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="RAS-FHIR", dst_name="GIC-600")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="RAS-ERIR", dst_name="GIC-600")

    print(f"[arm-ras-extensions] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
