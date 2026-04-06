"""
Report Generator — auto-fill BSP optimization reports with business impact data.

Takes a list of BSP metric findings (component / metric / delta / unit) and
produces a structured report dict that maps onto the Mustache-style placeholders
in ``templates/optimization-report.md``.

Usage as library::

    from mcp.tools.impact_translator.report_generator import generate_report

    report = generate_report(
        findings=[
            {"component": "LPDDR5", "metric": "leakage_current_ma",
             "delta": 4.0, "unit": "mA"},
            {"component": "ISP", "metric": "dma_stall_ms",
             "delta": 200, "unit": "ms"},
        ],
        metadata={
            "soc_platform": "MT6989",
            "product_type": "smartphone",
            "author": "BSP Team",
            "symptom_description": "Standby drain increased 8% between builds.",
        },
    )

CLI usage::

    python3 -m mcp.tools.impact_translator.report_generator \\
        --findings findings.json \\
        --metadata metadata.json \\
        --format markdown

    python3 -m mcp.tools.impact_translator.report_generator \\
        --findings findings.json \\
        --format json
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Optional

from mcp.tools.impact_translator.bsp_to_business import (
    translate_batch,
    translate_to_business_impact,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity aggregation
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}


def _aggregate_severity(impact_results: list[dict]) -> str:
    """Return the highest severity across all impact results."""
    worst = 0
    for r in impact_results:
        score = _SEVERITY_ORDER.get(r.get("severity", "unknown"), 0)
        if score > worst:
            worst = score
    for label, val in _SEVERITY_ORDER.items():
        if val == worst:
            return label
    return "unknown"


# ---------------------------------------------------------------------------
# KPI summary builder
# ---------------------------------------------------------------------------

def _build_kpi_summary(impact_results: list[dict]) -> list[dict]:
    """Collapse impact results into a de-duplicated KPI summary table."""
    kpi_map: dict[str, dict] = {}
    for r in impact_results:
        for kpi in r.get("affected_kpis", []):
            if kpi not in kpi_map:
                kpi_map[kpi] = {
                    "kpi_name": kpi,
                    "before": "baseline",
                    "after": "regressed" if r.get("delta", 0) > 0 else "improved",
                    "delta": f"{r['delta']:+.2f} {r['unit']}",
                    "business_meaning": r.get("business_impact", ""),
                }
    return list(kpi_map.values())


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_markdown(report: dict) -> str:
    """Render a report dict into filled-in Markdown matching the template structure."""
    meta = report.get("metadata", {})
    lines: list[str] = []

    lines.append("# BSP Optimization Report")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(f"**Date:** {report.get('date', '')}")
    lines.append(f"**Author:** {meta.get('author', 'N/A')}")
    lines.append(f"**SoC / Platform:** {meta.get('soc_platform', 'N/A')}")
    lines.append(f"**Product type:** {meta.get('product_type', 'smartphone')}")
    lines.append(f"**Report scope:** {meta.get('scope_one_liner', meta.get('symptom_description', 'N/A'))}")
    lines.append("")

    # KPI summary table
    lines.append("### Business Impact at a Glance")
    lines.append("")
    lines.append("| KPI | Before | After | Delta | Business Meaning |")
    lines.append("|-----|--------|-------|-------|------------------|")
    for kpi in report.get("kpi_summary", []):
        meaning = kpi["business_meaning"][:80] + "..." if len(kpi["business_meaning"]) > 80 else kpi["business_meaning"]
        lines.append(f"| {kpi['kpi_name']} | {kpi['before']} | {kpi['after']} | {kpi['delta']} | {meaning} |")
    lines.append("")

    lines.append(f"**Overall severity:** {report.get('overall_severity', 'unknown')}")
    lines.append("")

    # Section 2: Root cause
    lines.append("---")
    lines.append("")
    lines.append("## 2. Technical Root Cause")
    lines.append("")
    lines.append(f"**Symptom:** {meta.get('symptom_description', 'N/A')}")
    lines.append("")
    if meta.get("primary_root_cause"):
        lines.append(f"**Primary root cause:** {meta['primary_root_cause']}")
        lines.append("")

    # Section 3: Business impact details
    lines.append("---")
    lines.append("")
    lines.append("## 3. Business Impact Assessment")
    lines.append("")
    for item in report.get("impact_items", []):
        lines.append(f"### {item['component']} / {item['metric']}")
        lines.append("")
        direction = "increase" if item["delta"] > 0 else "decrease"
        lines.append(f"- **Physical change:** {item['delta']:+.2f} {item['unit']} ({direction})")
        lines.append(f"- **Severity:** {item['severity']}")
        lines.append(f"- **Business impact:** {item['business_impact']}")
        lines.append(f"- **Magnitude estimate:** {item.get('magnitude_estimate', 'N/A')}")
        kpis = ", ".join(item.get("affected_kpis", []))
        lines.append(f"- **Affected KPIs:** {kpis}")
        lines.append(f"- **Recommended framing for PM:** {item.get('recommended_framing', 'N/A')}")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>BSP physics explanation</summary>")
        lines.append("")
        lines.append(item.get("raw_reasoning", ""))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Section 4: Fix (placeholder)
    lines.append("---")
    lines.append("")
    lines.append("## 4. Fix / Optimization Applied")
    lines.append("")
    if meta.get("fix_description"):
        lines.append(meta["fix_description"])
    else:
        lines.append("*Fill in after the fix is implemented.*")
    lines.append("")

    # Section 5: Timeline (placeholder)
    lines.append("---")
    lines.append("")
    lines.append("## 5. Mitigation Timeline")
    lines.append("")
    lines.append("*Fill in project milestones and owners.*")
    lines.append("")

    # Section 6: Lessons (placeholder)
    lines.append("---")
    lines.append("")
    lines.append("## 6. Lessons Learned")
    lines.append("")
    lines.append("*Fill in after post-mortem review.*")
    lines.append("")

    lines.append("---")
    lines.append(f"*Generated by report_generator.py on {report.get('date', '')}*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    findings: list[dict],
    metadata: Optional[dict] = None,
) -> dict:
    """Generate a structured business impact report from BSP metric findings.

    Parameters
    ----------
    findings:
        List of dicts, each with keys: ``component``, ``metric``, ``delta``,
        ``unit``, and optionally ``product_type``.
    metadata:
        Optional report metadata: ``soc_platform``, ``product_type``,
        ``author``, ``symptom_description``, ``primary_root_cause``,
        ``fix_description``, ``scope_one_liner``.

    Returns
    -------
    dict
        Keys: ``date``, ``metadata``, ``impact_items``, ``kpi_summary``,
        ``overall_severity``, ``findings_count``, ``markdown``.
    """
    metadata = metadata or {}
    product_type = metadata.get("product_type", "smartphone")

    # Apply product_type default to findings that don't specify it
    for f in findings:
        f.setdefault("product_type", product_type)

    impact_items = translate_batch(findings)

    # Filter out error items for aggregation
    valid_items = [i for i in impact_items if "error" not in i]

    kpi_summary = _build_kpi_summary(valid_items)
    overall_severity = _aggregate_severity(valid_items)

    report = {
        "date": datetime.date.today().isoformat(),
        "metadata": metadata,
        "impact_items": impact_items,
        "kpi_summary": kpi_summary,
        "overall_severity": overall_severity,
        "findings_count": len(findings),
        "valid_findings_count": len(valid_items),
    }

    report["markdown"] = _render_markdown(report)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "Generate a BSP optimization report with auto-populated business "
            "impact sections. Reads findings from a JSON file."
        )
    )
    parser.add_argument(
        "--findings",
        required=True,
        help=(
            "Path to JSON file containing a list of finding dicts. "
            "Each dict: {component, metric, delta, unit, [product_type]}"
        ),
    )
    parser.add_argument(
        "--metadata",
        default=None,
        help=(
            "Path to JSON file with report metadata: "
            "{soc_platform, product_type, author, symptom_description, ...}"
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    with open(args.findings) as f:
        findings_data = json.load(f)

    metadata_data = {}
    if args.metadata:
        with open(args.metadata) as f:
            metadata_data = json.load(f)

    report = generate_report(findings=findings_data, metadata=metadata_data)

    if args.format == "markdown":
        output_text = report["markdown"]
    else:
        # Remove the markdown key for clean JSON output
        report_copy = {k: v for k, v in report.items() if k != "markdown"}
        output_text = json.dumps(report_copy, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_text)
            f.write("\n")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output_text)
