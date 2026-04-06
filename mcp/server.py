"""
BSP Knowledge MCP Server — local tool server for BSP Knowledge Skill Sets.

Binds to localhost (127.0.0.1) only and exposes graph query tools via the
MCP (Model Context Protocol) stdio transport.

Registered tools (graph query):
  - query_power_chain          — trace PMIC → PowerDomain → Component supply path
  - query_cross_domain_failure — multi-hop failure mode analysis
  - query_interrupt_path       — IRQ source → GIC-600 → ITS → CPU routing
  - query_isp_pipeline         — Sensor → ISP → DMA-BUF → GPU/NPU data path

Registered tools (log parsers — power/thermal domain):
  - parse_ftrace               — C-state residency, suspend/resume timing, DVFS transitions
  - parse_suspend_resume_log   — pm_debug dmesg, wakeup_sources, pm_wakeup_irq
  - parse_thermal_log          — thermal throttling events, trip crossings
  - parse_pmic_log             — regulator events, OCP, power sequence violations
  - parse_irq_stats            — /proc/interrupts rate, storm detection, CPU imbalance
  - parse_perf_stat            — perf stat IPC, cache miss, branch misprediction
  - compute_dvfs_efficiency    — OPP table Perf/Watt frontier
  - parse_pll_log              — PLL lock ordering, premature clock consumer access
  - scan_power_islands         — zombie power domain detection from genpd summary

Registered tools (log parsers — multimedia/camera domain):
  - parse_v4l2_log             — V4L2 buffer queue depth, overflow, media link errors
  - parse_emmc_io_log          — F2FS GC stalls, checkpoint latency, eMMC iostat
  - parse_camera_hal_errors    — Android Camera HAL3 error code decoding

Registered tools (log parsers — GPU domain):
  - parse_perfetto_gpu         — GPU slice timeline from Perfetto JSON trace
  - parse_agp_report           — Android GPU Inspector frame capture analysis

Registered tools (log parsers — interrupt/virtualization domain):
  - parse_vm_exit_stats        — KVM VM Exit frequency by reason
  - validate_its_table         — GIC-600 ITS EventID→IntID→CPU consistency

Registered tools (business impact translation — CONFIG):
  - translate_to_business_impact — convert BSP metric delta to PM/management language
  - generate_business_impact_report — batch-translate findings into a structured report

All read-only tools are enforced by the safety gate at READ_ONLY level.
translate_to_business_impact and generate_business_impact_report are CONFIG level
(output communicated externally).

Environment variables:
  MCP_HOST   — bind host (default: 127.0.0.1)
  MCP_PORT   — bind port (default: 3000)

Usage::

    python mcp/server.py

    # With explicit env overrides:
    MCP_HOST=127.0.0.1 MCP_PORT=3001 python mcp/server.py
"""

import os
import sys
import logging
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup — must come before local package imports
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_QUERIES_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "queries")
_TOOLS_DIR = os.path.join(_HERE, "tools")
_GRAPH_QUERY_DIR = os.path.join(_TOOLS_DIR, "graph_query")
_LOG_PARSERS_DIR = os.path.join(_TOOLS_DIR, "log_parsers")
_IMPACT_TRANSLATOR_DIR = os.path.join(_TOOLS_DIR, "impact_translator")

sys.path.insert(0, _QUERIES_DIR)
sys.path.insert(0, _TOOLS_DIR)
sys.path.insert(0, _GRAPH_QUERY_DIR)
sys.path.insert(0, _LOG_PARSERS_DIR)
sys.path.insert(0, _IMPACT_TRANSLATOR_DIR)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety gate import (from local tools directory)
# ---------------------------------------------------------------------------

from safety_gate import check_approval  # noqa: E402

# ---------------------------------------------------------------------------
# Import FastMCP from the installed mcp SDK.
# NOTE: This file must be run as ``python mcp/server.py`` from the repo root
# (or as a module entry point), NOT imported from within the repo root as a
# package, to avoid the local mcp/ directory shadowing the installed SDK.
# ---------------------------------------------------------------------------

from mcp.server.fastmcp import FastMCP  # noqa: E402

_MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
_MCP_PORT = int(os.environ.get("MCP_PORT", "3000"))

# Enforce localhost-only: refuse to bind to 0.0.0.0 or external addresses
if _MCP_HOST not in ("127.0.0.1", "localhost", "::1"):
    logger.error(
        "MCP_HOST is set to '%s'. The MCP server MUST only bind to localhost "
        "(127.0.0.1). Overriding to 127.0.0.1 for security.",
        _MCP_HOST,
    )
    _MCP_HOST = "127.0.0.1"

mcp = FastMCP(
    "bsp-knowledge-tools",
)


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------

@mcp.tool()
def query_power_chain(component_name: str) -> dict:
    """Trace the power supply chain (PMIC → PowerDomain → Component).

    Parameters
    ----------
    component_name:
        Name of the target component in the knowledge graph
        (e.g. ``"Cortex-A55-Cluster"``).
    """
    check_approval("query_power_chain")
    import query_tools  # lazy import to keep server startup fast
    return query_tools.query_power_chain(component_name)


@mcp.tool()
def query_cross_domain_failure(symptom_keywords: list[str]) -> dict:
    """Find failure modes matching symptom keywords and trace cross-domain impact.

    Parameters
    ----------
    symptom_keywords:
        List of natural-language keywords describing the observed symptom
        (e.g. ``["IRQ", "storm", "100%"]``).
    """
    check_approval("query_cross_domain_failure")
    import query_tools
    return query_tools.query_cross_domain_failure(symptom_keywords)


@mcp.tool()
def query_interrupt_path(irq_source: str) -> dict:
    """Trace the interrupt routing path from an IRQ source to target CPU.

    Parameters
    ----------
    irq_source:
        Interrupt node name as stored in the graph
        (e.g. ``"SPI-PMIC"``, ``"LPI-PCIe-MSI"``).
    """
    check_approval("query_interrupt_path")
    import query_tools
    return query_tools.query_interrupt_path(irq_source)


@mcp.tool()
def query_isp_pipeline(sensor_name: Optional[str] = None) -> dict:
    """Trace the ISP multimedia data path: Sensor → ISP → DMA-BUF → GPU/NPU.

    Parameters
    ----------
    sensor_name:
        Optional sensor component name.  Defaults to ``"MIPI-CSI2-RX"``.
    """
    check_approval("query_isp_pipeline")
    import query_tools
    return query_tools.query_isp_pipeline(sensor_name)


# ---------------------------------------------------------------------------
# Log parser tool registrations — Power / Thermal domain
# ---------------------------------------------------------------------------

@mcp.tool()
def parse_ftrace(log_path: str) -> dict:
    """Parse ftrace/trace-cmd log for C-state residency, suspend/resume timing, and DVFS transitions.

    Parameters
    ----------
    log_path:
        Path to trace-cmd text report or raw /sys/kernel/debug/tracing/trace snapshot.
    """
    check_approval("parse_ftrace")
    from ftrace_parser import parse_ftrace as _parse
    return _parse(log_path)


@mcp.tool()
def parse_suspend_resume_log(
    log_path: str,
    wakeup_sources_path: Optional[str] = None,
    pm_wakeup_irq_path: Optional[str] = None,
) -> dict:
    """Parse pm_debug dmesg for STR/STD suspend/resume driver failures and wakeup sources.

    Parameters
    ----------
    log_path:
        Path to dmesg log (with pm_debug=1 preferred).
    wakeup_sources_path:
        Optional path to /sys/kernel/debug/wakeup_sources snapshot.
    pm_wakeup_irq_path:
        Optional path to /sys/power/pm_wakeup_irq snapshot.
    """
    check_approval("parse_suspend_resume_log")
    from suspend_resume_parser import parse_suspend_resume_log as _parse
    return _parse(log_path, wakeup_sources_path, pm_wakeup_irq_path)


@mcp.tool()
def parse_thermal_log(log_path: str) -> dict:
    """Parse dmesg for thermal throttling events, trip point crossings, and cooling device states.

    Parameters
    ----------
    log_path:
        Path to dmesg output file.
    """
    check_approval("parse_thermal_log")
    from thermal_parser import parse_thermal_log as _parse
    return _parse(log_path)


@mcp.tool()
def parse_pmic_log(log_path: str) -> dict:
    """Parse dmesg for PMIC regulator events, OCP events, and power sequence violations.

    Parameters
    ----------
    log_path:
        Path to dmesg output file.
    """
    check_approval("parse_pmic_log")
    from pmic_log_parser import parse_pmic_log as _parse
    return _parse(log_path)


@mcp.tool()
def parse_irq_stats(
    snapshot_path: str,
    snapshot_path_after: Optional[str] = None,
    elapsed_sec: float = 1.0,
) -> dict:
    """Analyse /proc/interrupts snapshot(s) for interrupt rate, storms, and CPU imbalance.

    Parameters
    ----------
    snapshot_path:
        Path to first /proc/interrupts snapshot.
    snapshot_path_after:
        Optional second snapshot for rate calculation.
    elapsed_sec:
        Time between snapshots in seconds.
    """
    check_approval("parse_irq_stats")
    from irq_stat_parser import parse_irq_stats as _parse
    return _parse(snapshot_path, snapshot_path_after, elapsed_sec)


@mcp.tool()
def parse_perf_stat(log_path: str) -> dict:
    """Parse `perf stat` output for IPC, cache miss rate, and branch misprediction.

    Parameters
    ----------
    log_path:
        Path to perf stat text output (stderr redirected to file).
    """
    check_approval("parse_perf_stat")
    from perf_parser import parse_perf_stat as _parse
    return _parse(log_path)


@mcp.tool()
def compute_dvfs_efficiency(opp_table_path: str) -> dict:
    """Compute Perf/Watt efficiency frontier from a DVFS OPP table (CSV or JSON).

    Parameters
    ----------
    opp_table_path:
        Path to OPP table file. Required fields: freq_mhz, voltage_mv.
        Optional: power_mw (measured), perf_score.
    """
    check_approval("compute_dvfs_efficiency")
    from dvfs_opp_calc import compute_dvfs_efficiency as _compute
    return _compute(opp_table_path)


@mcp.tool()
def parse_pll_log(log_path: str) -> dict:
    """Parse dmesg for PLL lock events and premature clock consumer access ordering violations.

    Parameters
    ----------
    log_path:
        Path to kernel dmesg file (boot log with CCF debug preferred).
    """
    check_approval("parse_pll_log")
    from pll_checker import parse_pll_log as _parse
    return _parse(log_path)


@mcp.tool()
def scan_power_islands(
    genpd_summary_path: str,
    dmesg_path: Optional[str] = None,
) -> dict:
    """Detect zombie power island states from pm_genpd summary and optional dmesg.

    Parameters
    ----------
    genpd_summary_path:
        Path to /sys/kernel/debug/pm_genpd/pm_genpd_summary snapshot.
    dmesg_path:
        Optional dmesg for genpd transition events.
    """
    check_approval("scan_power_islands")
    from power_island_scanner import scan_power_islands as _scan
    return _scan(genpd_summary_path, dmesg_path)


# ---------------------------------------------------------------------------
# Log parser tool registrations — Multimedia / Camera domain
# ---------------------------------------------------------------------------

@mcp.tool()
def parse_v4l2_log(log_path: str) -> dict:
    """Parse V4L2 buffer queue log for pipeline stalls, buffer underruns, and media link errors.

    Parameters
    ----------
    log_path:
        Path to v4l2-ctl verbose output or kernel dmesg with V4L2 messages.
    """
    check_approval("parse_v4l2_log")
    from v4l2_stats_parser import parse_v4l2_log as _parse
    return _parse(log_path)


@mcp.tool()
def parse_emmc_io_log(log_path: str) -> dict:
    """Parse eMMC I/O and F2FS log for GC stalls, checkpoint latency, and throughput.

    Parameters
    ----------
    log_path:
        Path to iostat output or dmesg with F2FS messages.
    """
    check_approval("parse_emmc_io_log")
    from emmc_io_parser import parse_emmc_io_log as _parse
    return _parse(log_path)


@mcp.tool()
def parse_camera_hal_errors(log_path: str) -> dict:
    """Decode Android Camera HAL3 error codes from logcat output.

    Parameters
    ----------
    log_path:
        Path to logcat output file (adb logcat -v threadtime > file.txt).
    """
    check_approval("parse_camera_hal_errors")
    from camera_hal_error_decoder import parse_camera_hal_errors as _parse
    return _parse(log_path)


# ---------------------------------------------------------------------------
# Log parser tool registrations — GPU / Rendering domain
# ---------------------------------------------------------------------------

@mcp.tool()
def parse_perfetto_gpu(trace_path: str) -> dict:
    """Parse Perfetto JSON trace for GPU slice timeline, jank frames, and submission latency.

    Parameters
    ----------
    trace_path:
        Path to Perfetto JSON trace file (File → Export in Perfetto UI).
    """
    check_approval("parse_perfetto_gpu")
    from perfetto_gpu_parser import parse_perfetto_gpu as _parse
    return _parse(trace_path)


@mcp.tool()
def parse_agp_report(trace_path: str) -> dict:
    """Parse Android GPU Inspector JSON frame capture for pipeline breakdown and bottleneck.

    Parameters
    ----------
    trace_path:
        Path to AGI JSON export file (File → Export Capture in AGI).
    """
    check_approval("parse_agp_report")
    from agp_parser import parse_agp_report as _parse
    return _parse(trace_path)


# ---------------------------------------------------------------------------
# Log parser tool registrations — Interrupt / Virtualization domain
# ---------------------------------------------------------------------------

@mcp.tool()
def parse_vm_exit_stats(log_path: str, elapsed_sec: float = 1.0) -> dict:
    """Parse perf kvm stat report for VM Exit frequency and overhead by reason.

    Parameters
    ----------
    log_path:
        Path to `perf kvm stat report` output file.
    elapsed_sec:
        Measurement window in seconds (for rate calculation).
    """
    check_approval("parse_vm_exit_stats")
    from vm_exit_counter import parse_vm_exit_stats as _parse
    return _parse(log_path, elapsed_sec)


@mcp.tool()
def validate_its_table(log_path: str) -> dict:
    """Validate GIC-600 ITS EventID→IntID→CPU mapping table consistency from dmesg.

    Parameters
    ----------
    log_path:
        Path to dmesg log with ITS debug output.
    """
    check_approval("validate_its_table")
    from its_validator import validate_its_table as _validate
    return _validate(log_path)


# ---------------------------------------------------------------------------
# Business impact translator tool registration
# ---------------------------------------------------------------------------

@mcp.tool()
def translate_to_business_impact(
    component: str,
    metric: str,
    delta: float,
    unit: str,
    product_type: str = "smartphone",
) -> dict:
    """Translate a BSP physical metric change into business-language impact for PM / management communication.

    Parameters
    ----------
    component:
        BSP component name, e.g. ``"LPDDR5"``, ``"GPU"``, ``"ISP"``,
        ``"CPUFreq"``, ``"eMMC"``, ``"GIC"``, ``"PMIC"``, ``"thermal"``,
        ``"DVFS"``, ``"NPU"``.
    metric:
        The physical metric being changed, e.g. ``"leakage_current_ma"``,
        ``"dvfs_opp_step"``, ``"frame_time_ms"``, ``"isp_latency_ms"``,
        ``"irq_latency_us"``, ``"throttle_duration_ms"``.
    delta:
        The numeric change in the metric. Positive = increase / worsening.
        Negative = decrease / improvement.
    unit:
        Unit string for *delta*, e.g. ``"mA"``, ``"ms"``, ``"µs"``, ``"%"``.
    product_type:
        One of ``"smartphone"``, ``"tablet"``, ``"wearable"``,
        ``"automotive"``, ``"iot"``. Defaults to ``"smartphone"``.
    """
    check_approval("translate_to_business_impact")
    from bsp_to_business import translate_to_business_impact as _translate
    return _translate(
        component=component,
        metric=metric,
        delta=delta,
        unit=unit,
        product_type=product_type,
    )


@mcp.tool()
def generate_business_impact_report(
    findings: list[dict],
    metadata: dict | None = None,
) -> dict:
    """Generate a structured business impact report from multiple BSP metric findings.

    Takes a list of BSP metric deltas and produces a full report with executive
    summary, per-finding business impact, KPI summary, and overall severity.

    Parameters
    ----------
    findings:
        List of dicts, each with keys: ``component``, ``metric``, ``delta``,
        ``unit``, and optionally ``product_type``.
    metadata:
        Optional report context: ``soc_platform``, ``product_type``,
        ``author``, ``symptom_description``, ``primary_root_cause``,
        ``fix_description``.
    """
    check_approval("generate_business_impact_report")
    from report_generator import generate_report
    return generate_report(findings=findings, metadata=metadata)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting BSP Knowledge MCP server (stdio transport). "
        "Host=%s Port=%s (port used for SSE only if configured).",
        _MCP_HOST,
        _MCP_PORT,
    )
    # FastMCP uses stdio transport by default — no outbound network calls.
    mcp.run()
