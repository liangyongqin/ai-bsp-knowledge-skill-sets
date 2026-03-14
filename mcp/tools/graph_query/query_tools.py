"""
MCP Tool Wrappers for Graph Queries.

Wraps the GraphRAG query functions from knowledge-graph/queries/ with MCP
tool interface conventions, safety gate enforcement, and standardised
error handling.

All wrapped tools are classified READ_ONLY in the safety gate.
"""

import os
import sys
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root or as a package
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_HERE, "..", "..", "..")
_QUERIES_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "queries")
_TOOLS_DIR = os.path.join(_HERE, "..")

sys.path.insert(0, _QUERIES_DIR)
sys.path.insert(0, _TOOLS_DIR)

from safety_gate import check_approval, RiskLevel  # noqa: E402


def _load_query_module(module_name: str):
    """Lazily import a query module by name."""
    import importlib
    return importlib.import_module(module_name)


def _safe_call(tool_name: str, fn, *args, **kwargs) -> dict:
    """Execute *fn* after safety gate check, wrapping exceptions."""
    try:
        check_approval(tool_name, requires_human_approval=False)
    except PermissionError as e:
        return {"error": str(e), "tool": tool_name}

    try:
        result = fn(*args, **kwargs)
        return {"result": result, "tool": tool_name, "status": "ok"}
    except Exception as exc:
        logger.error("Tool '%s' raised: %s", tool_name, exc, exc_info=True)
        return {"error": str(exc), "tool": tool_name, "status": "error"}


# ---------------------------------------------------------------------------
# Public MCP tool wrappers
# ---------------------------------------------------------------------------

def query_power_chain(
    component_name: str,
    requires_human_approval: bool = False,
) -> dict[str, Any]:
    """Trace the power supply chain leading to *component_name*.

    Wraps :func:`knowledge_graph.queries.power_chain.query_power_chain`.

    Parameters
    ----------
    component_name:
        Target component name (e.g. ``"Cortex-A55-Cluster"``).
    requires_human_approval:
        Unused for READ_ONLY tools; kept for interface consistency.

    Returns
    -------
    dict
        ``{"result": [...], "tool": "query_power_chain", "status": "ok"}``
        or ``{"error": "...", ...}`` on failure.
    """
    mod = _load_query_module("power_chain")
    return _safe_call(
        "query_power_chain",
        mod.query_power_chain,
        component_name,
    )


def query_cross_domain_failure(
    symptom_keywords: list[str],
    requires_human_approval: bool = False,
) -> dict[str, Any]:
    """Find failure modes matching *symptom_keywords* and trace cross-domain impact.

    Wraps :func:`knowledge_graph.queries.cross_domain_failure.query_cross_domain_failure`.

    Parameters
    ----------
    symptom_keywords:
        Natural-language keywords (e.g. ``["IRQ", "storm"]``).
    requires_human_approval:
        Unused for READ_ONLY tools.

    Returns
    -------
    dict
    """
    mod = _load_query_module("cross_domain_failure")
    return _safe_call(
        "query_cross_domain_failure",
        mod.query_cross_domain_failure,
        symptom_keywords,
    )


def query_interrupt_path(
    irq_source: str,
    requires_human_approval: bool = False,
) -> dict[str, Any]:
    """Trace the interrupt routing path from *irq_source* to target CPU.

    Wraps :func:`knowledge_graph.queries.interrupt_path.query_interrupt_path`.

    Parameters
    ----------
    irq_source:
        Interrupt name (e.g. ``"SPI-PMIC"``, ``"LPI-PCIe-MSI"``).
    requires_human_approval:
        Unused for READ_ONLY tools.

    Returns
    -------
    dict
    """
    mod = _load_query_module("interrupt_path")
    return _safe_call(
        "query_interrupt_path",
        mod.query_interrupt_path,
        irq_source,
    )


def query_isp_pipeline(
    sensor_name: Optional[str] = None,
    requires_human_approval: bool = False,
) -> dict[str, Any]:
    """Trace the ISP multimedia pipeline from sensor to GPU/NPU.

    Wraps :func:`knowledge_graph.queries.isp_pipeline.query_isp_pipeline`.

    Parameters
    ----------
    sensor_name:
        Optional sensor component name.  Defaults to ``"MIPI-CSI2-RX"``.
    requires_human_approval:
        Unused for READ_ONLY tools.

    Returns
    -------
    dict
    """
    mod = _load_query_module("isp_pipeline")
    return _safe_call(
        "query_isp_pipeline",
        mod.query_isp_pipeline,
        sensor_name,
    )
