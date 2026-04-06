"""
Safety Gate — risk classification and approval enforcement for MCP tools.

All tool calls from skills are classified into three risk levels:
  - READ_ONLY:   reads logs, files, graph queries — always permitted
  - CONFIG:      writes to knowledge-graph/custom/ — always permitted
  - DESTRUCTIVE: modifies hardware state or triggers external builds — requires human approval

Reference: CLAUDE.md — MCP Tool Server section
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Enumeration of tool call risk levels."""

    READ_ONLY = auto()
    """Read-only operations: graph queries, log parsing, file reads."""

    CONFIG = auto()
    """Configuration writes: updates to knowledge-graph/custom/ only."""

    DESTRUCTIVE = auto()
    """Operations that modify hardware state or trigger external side effects."""


# ---------------------------------------------------------------------------
# Tool risk registry
# ---------------------------------------------------------------------------

TOOL_RISK_LEVELS: dict[str, RiskLevel] = {
    # Graph query tools — all read-only
    "query_power_chain": RiskLevel.READ_ONLY,
    "query_cross_domain_failure": RiskLevel.READ_ONLY,
    "query_interrupt_path": RiskLevel.READ_ONLY,
    "query_isp_pipeline": RiskLevel.READ_ONLY,
    "list_all_interrupts": RiskLevel.READ_ONLY,
    "find_all_power_domains": RiskLevel.READ_ONLY,
    "find_components_powered_by": RiskLevel.READ_ONLY,
    "query_failures_by_domain": RiskLevel.READ_ONLY,
    "query_multimedia_components": RiskLevel.READ_ONLY,
    # Log parser tools — read-only
    "parse_ftrace": RiskLevel.READ_ONLY,
    "parse_dmesg": RiskLevel.READ_ONLY,
    "parse_perf_stat": RiskLevel.READ_ONLY,
    "compute_dvfs_efficiency": RiskLevel.READ_ONLY,
    "parse_pll_log": RiskLevel.READ_ONLY,
    "scan_power_islands": RiskLevel.READ_ONLY,
    "parse_thermal_log": RiskLevel.READ_ONLY,
    "parse_pmic_log": RiskLevel.READ_ONLY,
    "parse_irq_stats": RiskLevel.READ_ONLY,
    "parse_suspend_resume_log": RiskLevel.READ_ONLY,
    "parse_v4l2_log": RiskLevel.READ_ONLY,
    "parse_emmc_io_log": RiskLevel.READ_ONLY,
    "parse_camera_hal_errors": RiskLevel.READ_ONLY,
    "parse_perfetto_gpu": RiskLevel.READ_ONLY,
    "parse_agp_report": RiskLevel.READ_ONLY,
    "parse_vm_exit_stats": RiskLevel.READ_ONLY,
    "validate_its_table": RiskLevel.READ_ONLY,
    # Spec extractor — read-only (reads files)
    "ingest_pdf": RiskLevel.READ_ONLY,
    "parse_ipxact": RiskLevel.READ_ONLY,
    "extract_registers": RiskLevel.READ_ONLY,
    "validate_registers": RiskLevel.READ_ONLY,
    # Custom knowledge ingestion — config writes to custom/ namespace
    "ingest_custom_pdf": RiskLevel.CONFIG,
    "ingest_custom_ipxact": RiskLevel.CONFIG,
    "update_custom_graph": RiskLevel.CONFIG,
    # Business impact translator — CONFIG because output is communicated externally
    "translate_to_business_impact": RiskLevel.CONFIG,
    "generate_business_impact_report": RiskLevel.CONFIG,
    # Destructive / hardware-state-modifying operations
    "flash_firmware": RiskLevel.DESTRUCTIVE,
    "set_register_value": RiskLevel.DESTRUCTIVE,
    "trigger_hardware_reset": RiskLevel.DESTRUCTIVE,
    "run_external_build": RiskLevel.DESTRUCTIVE,
    "modify_dtb": RiskLevel.DESTRUCTIVE,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_risk_level(tool_name: str) -> RiskLevel:
    """Return the risk level for *tool_name*.

    Unknown tools default to ``RiskLevel.READ_ONLY`` (safe assumption for
    purely informational operations), but a warning is logged.

    Parameters
    ----------
    tool_name:
        The registered name of the MCP tool.

    Returns
    -------
    RiskLevel
    """
    level = TOOL_RISK_LEVELS.get(tool_name)
    if level is None:
        logger.warning(
            "Unknown tool '%s' — defaulting to READ_ONLY. "
            "Add it to TOOL_RISK_LEVELS in safety_gate.py.",
            tool_name,
        )
        return RiskLevel.READ_ONLY
    return level


def check_approval(
    tool_name: str,
    requires_human_approval: bool = False,
) -> bool:
    """Check whether *tool_name* is permitted to execute.

    Permission rules:
    - ``READ_ONLY``: always permitted.
    - ``CONFIG``: always permitted.
    - ``DESTRUCTIVE``: permitted only when *requires_human_approval* is ``True``.

    Parameters
    ----------
    tool_name:
        The registered MCP tool name.
    requires_human_approval:
        Set to ``True`` when the calling context has confirmed explicit
        human approval for destructive operations.

    Returns
    -------
    bool
        ``True`` if the tool may execute.

    Raises
    ------
    PermissionError
        If *tool_name* is ``DESTRUCTIVE`` and *requires_human_approval* is
        ``False``.
    """
    level = get_risk_level(tool_name)

    if level in (RiskLevel.READ_ONLY, RiskLevel.CONFIG):
        return True

    # DESTRUCTIVE
    if not requires_human_approval:
        raise PermissionError(
            f"Tool '{tool_name}' is classified as DESTRUCTIVE and requires explicit "
            "human approval (pass requires_human_approval=True)."
        )

    logger.warning("DESTRUCTIVE tool '%s' approved by human operator.", tool_name)
    return True
