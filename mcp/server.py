"""
BSP Knowledge MCP Server — local tool server for BSP Knowledge Skill Sets.

Binds to localhost (127.0.0.1) only and exposes graph query tools via the
MCP (Model Context Protocol) stdio transport.

Registered tools:
  - query_power_chain        — trace PMIC → PowerDomain → Component supply path
  - query_cross_domain_failure — multi-hop failure mode analysis
  - query_interrupt_path     — IRQ source → GIC-600 → ITS → CPU routing
  - query_isp_pipeline       — Sensor → ISP → DMA-BUF → GPU/NPU data path

All tools are READ_ONLY and enforced by the safety gate.

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

sys.path.insert(0, _QUERIES_DIR)
sys.path.insert(0, _TOOLS_DIR)
sys.path.insert(0, _GRAPH_QUERY_DIR)

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
