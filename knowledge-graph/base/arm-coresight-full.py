"""
ARM CoreSight trace subsystem — full component coverage.

Adds detailed CoreSight architecture components not covered by the basic
arm-cpu-cluster.py seed:
  - ETF (Embedded Trace FIFO) — on-chip trace buffer for low-latency capture
  - ETR (Embedded Trace Router) — routes trace to system DRAM
  - ETS (Embedded Trace Streamer) — stream-oriented trace, low buffering
  - STM (System Trace Macrocell) — software instrumentation trace via STP
  - TPIU (Trace Port Interface Unit) — off-chip export to trace probe
  - CTI (Cross Trigger Interface) — debug/trace cross-trigger fabric
  - CTM (Cross Trigger Matrix) — global CTI coordination
  - ROM Table — CoreSight component discovery mechanism
  - Dynamic configuration and failure modes

Sources:
  - ARM CoreSight Architecture Specification v3.0 (IHI0029F) — developer.arm.com
  - ARM CoreSight SoC-600 TRM (ADIv6) — developer.arm.com
  - Linux Documentation/trace/coresight/coresight.rst
  - Linux Documentation/trace/coresight/coresight-etm4x-reference.rst
  - Linux kernel drivers/hwtracing/coresight/

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
# Components — CoreSight trace sources
# ---------------------------------------------------------------------------

_TRACE_SOURCES = [
    ("CoreSight-ETM4",       "trace",    "ARM",
     "CoreSight Embedded Trace Macrocell v4 (ETM4) — instruction and data trace "
     "for ARM CPUs; encodes executed instructions, data addresses, timestamps; "
     "configured via TRCPRGCTLR, TRCSYNCPR, TRCSSCCRn registers; "
     "per-CPU instance, accessed via ARM ADI debug port",
     "base"),
    ("CoreSight-STM",        "trace",    "ARM",
     "CoreSight System Trace Macrocell (STM) — software-instrumented trace via "
     "MIPI STP (System Trace Protocol); 64K stimulus ports per STM; "
     "used for OS/hypervisor software events alongside ETM hardware trace; "
     "Linux driver: drivers/hwtracing/stm/",
     "base"),
    ("CoreSight-ETE",        "trace",    "ARM",
     "CoreSight Embedded Trace Extension (ETE) — ARMv9 successor to ETMv4; "
     "mandatory for ARMv9 cores; supports TRBE (self-hosted trace to memory); "
     "adds explicit SME trace, improved timestamp granularity",
     "base"),
    ("CoreSight-PTM",        "trace",    "ARM",
     "CoreSight Program Trace Macrocell (PTM) — legacy ETM for ARMv7/v8; "
     "still present in some SoCs alongside ETM4 for older CPU cores",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — CoreSight trace sinks
# ---------------------------------------------------------------------------

_TRACE_SINKS = [
    ("CoreSight-ETF",        "trace-sink",    "ARM",
     "CoreSight Embedded Trace FIFO (ETF) — on-chip SRAM trace buffer, 1–8 KB; "
     "two modes: FIFO (circular, lose oldest data on full) and "
     "CIRCULAR-BUFFER (stop-on-full for post-mortem); "
     "TMC_MODE register selects ETF vs ETR vs ETS mode; "
     "accessible via APB; intermediate sink before ETR",
     "base"),
    ("CoreSight-ETR",        "trace-sink",    "ARM",
     "CoreSight Embedded Trace Router (ETR) — routes aggregated trace to "
     "system DRAM via AXI; configurable 4B–4GB ring buffer in DDR; "
     "TMC_RSIZ register sets buffer size; AXICTL configures burst type; "
     "primary sink for perf record --event cs_etm; "
     "Linux driver: drivers/hwtracing/coresight/coresight-tmc-etr.c",
     "base"),
    ("CoreSight-ETS",        "trace-sink",    "ARM",
     "CoreSight Embedded Trace Streamer (ETS) — stream-oriented TMC variant; "
     "minimal local buffering, designed for continuous streaming to host; "
     "lower latency than ETR at the cost of backpressure sensitivity; "
     "useful for real-time trace analysis with trc2txt",
     "base"),
    ("CoreSight-TPIU",       "trace-sink",    "ARM",
     "CoreSight Trace Port Interface Unit (TPIU) — exports trace off-chip "
     "via parallel/serial trace port to external logic analyzer or J-Trace; "
     "configurable port width (1/2/4 bytes); TPIU_FFCR formatter control; "
     "requires dedicated trace connector on PCB",
     "base"),
    ("CoreSight-ETF-ETR",    "trace-sink",    "ARM",
     "CoreSight ETF+ETR combined topology — ETF acts as on-chip capture buffer "
     "to absorb bursts; ETR drains ETF to DRAM; common in large SoCs to "
     "avoid ETR AXI stalls during DDR refresh; Linux CoreSight automatically "
     "discovers and links this topology via ROM table",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — CoreSight trace links (aggregation)
# ---------------------------------------------------------------------------

_TRACE_LINKS = [
    ("CoreSight-funnel-SoC", "trace-link",   "ARM",
     "CoreSight Trace Funnel (multiple per SoC) — multiplexes up to 8 ETM "
     "trace streams into a single ATB output; priority arbitration; "
     "FUNCTL register enables per-input port; SoC typically has one funnel "
     "per CPU cluster and one top-level funnel",
     "base"),
    ("CoreSight-replicator", "trace-link",   "ARM",
     "CoreSight Trace Replicator — duplicates ATB trace stream to two outputs; "
     "enables simultaneous ETF capture and TPIU export; "
     "or sending different trace slices to ETR vs STM",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — CoreSight cross-trigger
# ---------------------------------------------------------------------------

_CTI_COMPONENTS = [
    ("CoreSight-CTI",        "debug",    "ARM",
     "CoreSight Cross Trigger Interface (CTI) — maps trigger events between "
     "debug/trace components; halts CPUs on trace buffer full event; "
     "triggers ETM start/stop from external event; "
     "CTIOUTEN/CTIINEN registers; per-CPU instance, per-ETM instance",
     "base"),
    ("CoreSight-CTM",        "debug",    "ARM",
     "CoreSight Cross Trigger Matrix (CTM) — global interconnect for CTI signals; "
     "routes triggers across CPU clusters; enables coordinated halt of all CPUs; "
     "used by JTAG debugger for multi-core synchronized halt",
     "base"),
    ("CoreSight-ROMTable",   "debug",    "ARM",
     "CoreSight ROM Table — memory-mapped table of CoreSight component base addresses; "
     "ADIv5/ADIv6 debug access point enumerates all trace components by walking ROM table; "
     "Linux CoreSight driver auto-discovers topology via coresight-core.c",
     "base"),
]

# ---------------------------------------------------------------------------
# Components — Linux CoreSight drivers
# ---------------------------------------------------------------------------

_LINUX_CORESIGHT = [
    ("linux-coresight-core",        "driver",   "linux",
     "Linux CoreSight core driver (drivers/hwtracing/coresight/coresight-core.c) — "
     "topology discovery via ROM table walk; dynamic path construction "
     "between source (ETM) and sink (ETR/ETF/TPIU); "
     "perf integration via cs_etm PMU event; OpenCSD for instruction decode",
     "base"),
    ("linux-coresight-etm4x",       "driver",   "linux",
     "Linux ETMv4 driver (coresight-etm4x.c) — configures ETM4/ETE per-CPU; "
     "enables instruction trace, branch filtering, timestamp; "
     "perf --event cs_etm/@ syntax selects ETM parameters; "
     "Linux Documentation/trace/coresight/coresight-etm4x-reference.rst",
     "base"),
    ("linux-coresight-tmc",         "driver",   "linux",
     "Linux TMC driver (coresight-tmc-*.c) — manages ETF/ETR/ETS sinks; "
     "ETF: sysfs/dev interface for reading trace bytes; "
     "ETR: allocates DMA-contiguous buffer in system RAM; "
     "ETS: streaming path to /dev/ttyCS* or trc2txt pipeline",
     "base"),
    ("linux-coresight-stm",         "driver",   "linux",
     "Linux STM driver (stm/core.c) — software trace framework; "
     "generic STM API for drivers to write trace data; "
     "p_sys-t policy for MIPI SyS-T formatted messages; "
     "useful for boot/PM event tracing alongside hardware ETM",
     "base"),
    ("linux-perf-cs-etm",           "driver",   "linux",
     "Linux perf cs_etm PMU — integrates CoreSight with perf record/report; "
     "command: perf record -e cs_etm// --snapshot -C 0 -o trace.data; "
     "perf report uses OpenCSD library to decode instruction trace; "
     "branch misprediction and cache miss correlation in perf report --itrace",
     "base"),
]

# ---------------------------------------------------------------------------
# Registers — key ETM4 trace control registers
# ---------------------------------------------------------------------------

_ETM_REGISTERS = [
    ("TRCPRGCTLR",   "0x004",  "WO",  "0x00000000", "CoreSight-ETM4",
     "ETM4 Programming Control Register — bit 0: enable trace; "
     "must write 0 before configuring other ETM registers",
     "base"),
    ("TRCSYNCPR",    "0x034",  "RW",  "0x0000000C", "CoreSight-ETM4",
     "ETM4 Synchronization Period Register — controls periodic synchronization packets; "
     "period = 2^PERIOD bytes (default 4096B); larger periods reduce overhead",
     "base"),
    ("TRCVICTLR",    "0x080",  "RW",  "0x00000201", "CoreSight-ETM4",
     "ETM4 ViewInst Main Control Register — selects which instructions to trace; "
     "bits[19:16]: exception levels; bits[7:0]: address comparator enable",
     "base"),
    ("TMC_CTL",      "0x020",  "RW",  "0x00000000", "CoreSight-ETF",
     "TMC Control Register — bit 0: TraceCaptEn; "
     "set to 1 to enable trace capture; clear to flush and stop",
     "base"),
    ("TMC_MODE",     "0x028",  "RW",  "0x00000000", "CoreSight-ETF",
     "TMC Mode Register — 0: Circular buffer (ETF mode); "
     "1: Software FIFO; 2: Hardware FIFO (ETR forwarding mode)",
     "base"),
    ("TMC_RSIZ",     "0x004",  "RW",  "0x00000800", "CoreSight-ETR",
     "TMC RAM Size Register — size of trace buffer in 32-bit words; "
     "ETR: this is the DDR buffer size; default 0x800 = 8KB words = 32KB",
     "base"),
]

# ---------------------------------------------------------------------------
# FailureModes
# ---------------------------------------------------------------------------

_CS_FAILURES = [
    ("FM-ETR-Buffer-Overflow",
     "ETR trace buffer overflows; perf cs_etm reports 'LOST_EVENTS'; partial trace",
     "ETR ring buffer too small for trace bandwidth; increase buffer via "
     "TMC_RSIZ or reduce ETM filter scope; check /sys/bus/coresight/devices/tmc_etr0/mgmt/rsz; "
     "use ETF+ETR topology to absorb bursts",
     "debug",
     "Linux Documentation/trace/coresight/coresight.rst",
     "base"),
    ("FM-CTI-CPU-Unexpected-Halt",
     "All CPUs halt unexpectedly during debug session; system appears frozen",
     "CTI cross-trigger misconfiguration; halt trigger from one CPU propagated to all via CTM; "
     "disable unwanted CTIOUTEN channels or disconnect CTI before running production code",
     "debug",
     "ARM CoreSight Architecture Spec IHI0029 §9 CTI",
     "base"),
    ("FM-ETM-NoTrace-Config-Error",
     "perf cs_etm collects zero bytes; trace buffer always empty after record",
     "ETM4 TRCPRGCTLR.EN not set (=0) or ETM in abort state; "
     "TRCVICTLR address comparator misconfigured; "
     "verify TRCSTATR.IDLE=1 before enabling; check kernel ETM configuration via sysfs",
     "debug",
     "Linux Documentation/trace/coresight/coresight-etm4x-reference.rst",
     "base"),
    ("FM-STM-Stimulus-Overflow",
     "STM software trace events silently dropped; trace log has gaps",
     "STM FIFO backpressure: downstream trace sink (ETF/ETR) cannot drain fast enough; "
     "STM stimulus port writes stall if blocking mode enabled; "
     "increase ETF/ETR bandwidth or use non-blocking STM port (TRIG bit = 0)",
     "debug",
     "ARM CoreSight STM Architecture Specification IHI0051",
     "base"),
    ("FM-CoreSight-ROM-Discovery-Fail",
     "Linux CoreSight driver fails to discover trace components; dmesg shows no coresight devices",
     "ROM table base address incorrect in device tree (coresight-tpda DT node); "
     "ADIv5 access port not enabled; CoreSight clock not enabled before driver probe; "
     "check AMBA bus clock gating and ETM device-tree nodes",
     "debug",
     "Linux Documentation/trace/coresight/coresight.rst §Device Tree Bindings",
     "base"),
    ("FM-TRBE-Synchronization-Loss",
     "TRBE (self-hosted) trace loses sync; perf itrace decode fails with 'no synchronization found'",
     "TRBE buffer wrapped before perf snapshot was taken; "
     "no periodic sync packet (TRCSYNCPR period too large); "
     "reduce TRCSYNCPR or increase TRBE buffer; use '--snapshot' in perf record",
     "debug",
     "Linux Documentation/trace/coresight/trbe.rst",
     "base"),
]


def ingest(db_path: str = None) -> int:
    if db_path is None:
        db_path = os.path.join(_HERE, "bsp_base.db")

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    _schema.create_schema(conn)
    inserted = 0

    # Ingest components
    all_components = (
        _TRACE_SOURCES + _TRACE_SINKS + _TRACE_LINKS +
        _CTI_COMPONENTS + _LINUX_CORESIGHT
    )
    for name, ctype, vendor, desc, ns in all_components:
        if upsert_node(conn, "Component", {
            "name": name, "type": ctype, "namespace": ns,
            "vendor": vendor, "version": "", "description": desc,
        }):
            inserted += 1

    # Ingest registers
    for name, addr, access, reset, component, desc, ns in _ETM_REGISTERS:
        if upsert_node(conn, "Register", {
            "name": name, "address": addr, "access_type": access,
            "reset_value": reset, "component": component,
            "namespace": ns,
        }):
            inserted += 1

    # Ingest failure modes
    for name, symptom, root_cause, affected_domain, source, ns in _CS_FAILURES:
        if upsert_node(conn, "FailureMode", {
            "name": name, "symptom": symptom, "root_cause": root_cause,
            "affected_domain": affected_domain, "source": source, "namespace": ns,
        }):
            inserted += 1

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # ETM sources → funnels
    for src in ("CoreSight-ETM4", "CoreSight-ETE", "CoreSight-STM", "CoreSight-PTM"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name=src, dst_name="CoreSight-funnel-SoC")

    # Funnel → replicator (optional split)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-funnel-SoC", dst_name="CoreSight-replicator")

    # Replicator → sinks
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-replicator", dst_name="CoreSight-ETF")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-replicator", dst_name="CoreSight-TPIU")

    # ETF → ETR (ETF+ETR topology)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-ETF", dst_name="CoreSight-ETR")

    # Direct funnel → ETF (simpler topology)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-funnel-SoC", dst_name="CoreSight-ETF-ETR")

    # ETS is an alternative to ETR
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-funnel-SoC", dst_name="CoreSight-ETS")

    # CTI → CTM cross-trigger fabric
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-CTI", dst_name="CoreSight-CTM")

    # CTM ↔ ETM (start/stop triggers)
    create_rel(conn, "TRIGGERS", "Component", "Component",
               src_name="CoreSight-CTM", dst_name="CoreSight-ETM4")
    create_rel(conn, "TRIGGERS", "Component", "Component",
               src_name="CoreSight-CTM", dst_name="CoreSight-ETE")

    # ROM Table → all trace components (discovery)
    for comp in ("CoreSight-ETM4", "CoreSight-ETF", "CoreSight-ETR",
                 "CoreSight-TPIU", "CoreSight-CTI", "CoreSight-STM"):
        create_rel(conn, "ROUTES_TO", "Component", "Component",
                   src_name="CoreSight-ROMTable", dst_name=comp)

    # Linux drivers → hardware
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-coresight-core", dst_name="CoreSight-ROMTable")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-coresight-etm4x", dst_name="CoreSight-ETM4")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-coresight-etm4x", dst_name="CoreSight-ETE")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-coresight-tmc", dst_name="CoreSight-ETF")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-coresight-tmc", dst_name="CoreSight-ETR")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-coresight-stm", dst_name="CoreSight-STM")
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="linux-perf-cs-etm", dst_name="linux-coresight-core")

    # Link to existing CoreSight-funnel (from arm-cpu-cluster.py)
    create_rel(conn, "ROUTES_TO", "Component", "Component",
               src_name="CoreSight-funnel-SoC", dst_name="CoreSight-funnel")

    # FailureMode → root component
    for fm_name, comp_name in [
        ("FM-ETR-Buffer-Overflow",        "CoreSight-ETR"),
        ("FM-CTI-CPU-Unexpected-Halt",    "CoreSight-CTI"),
        ("FM-ETM-NoTrace-Config-Error",   "CoreSight-ETM4"),
        ("FM-STM-Stimulus-Overflow",      "CoreSight-STM"),
        ("FM-CoreSight-ROM-Discovery-Fail", "CoreSight-ROMTable"),
        ("FM-TRBE-Synchronization-Loss",  "CoreSight-ETE"),
    ]:
        create_rel(conn, "CAUSED_BY", "FailureMode", "Component",
                   src_name=fm_name, dst_name=comp_name)

    print(f"[arm-coresight-full] Inserted {inserted} nodes total.")
    return inserted


if __name__ == "__main__":
    ingest()
