"""
DVFS OPP efficiency calculator — Perf/Watt frontier from OPP table and workload data.

Inputs:
  - OPP table: CSV or JSON with columns [freq_mhz, voltage_mv, power_mw]
  - Optional workload performance CSV: [freq_mhz, perf_score] (e.g. from Dhrystone)

Computes:
  - Power at each OPP (P ∝ CV²f if power_mw not provided, uses C=1 normalised)
  - Performance/Watt at each OPP
  - Pareto-optimal (efficient frontier) OPPs
  - Recommended operating point for balanced performance
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any


def _load_opp_csv(path: str) -> list[dict]:
    """Load OPP table from CSV. Required columns: freq_mhz, voltage_mv.
    Optional: power_mw, perf_score."""
    rows = []
    with open(path, newline="", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            entry: dict[str, Any] = {}
            try:
                entry["freq_mhz"] = float(row.get("freq_mhz") or row.get("freq") or 0)
                entry["voltage_mv"] = float(row.get("voltage_mv") or row.get("voltage") or 0)
                if "power_mw" in row and row["power_mw"]:
                    entry["power_mw"] = float(row["power_mw"])
                if "perf_score" in row and row["perf_score"]:
                    entry["perf_score"] = float(row["perf_score"])
            except (ValueError, KeyError):
                continue
            if entry["freq_mhz"] > 0 and entry["voltage_mv"] > 0:
                rows.append(entry)
    return rows


def _load_opp_json(path: str) -> list[dict]:
    """Load OPP table from JSON array of {freq_mhz, voltage_mv, [power_mw], [perf_score]}."""
    with open(path, errors="replace") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    # Maybe nested: {"opps": [...]}
    for key in ("opps", "opp_table", "entries"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return []


def _estimate_power(freq_mhz: float, voltage_mv: float, cap_norm: float = 1.0) -> float:
    """P = C * V² * f  (normalised, C=cap_norm)."""
    v = voltage_mv / 1000.0  # V
    f = freq_mhz * 1e6       # Hz
    return cap_norm * v * v * f * 1e-9  # normalised mW-equivalent


def _pareto_frontier(opps: list[dict]) -> list[dict]:
    """Return Pareto-optimal OPPs (higher perf/watt is not dominated by any other)."""
    # Sort by perf_score ascending
    sorted_opps = sorted(opps, key=lambda x: x.get("perf_score", x["freq_mhz"]))
    frontier = []
    best_eff = -1.0
    for opp in sorted_opps:
        eff = opp.get("perf_per_watt", 0.0)
        if eff >= best_eff:
            frontier.append(opp)
            best_eff = eff
    return frontier


def compute_dvfs_efficiency(opp_table_path: str) -> dict[str, Any]:
    """Analyse DVFS OPP table for Perf/Watt efficiency frontier.

    Parameters
    ----------
    opp_table_path:
        Path to OPP table file (CSV or JSON).
        Required fields: freq_mhz, voltage_mv
        Optional fields: power_mw (measured), perf_score (benchmark score at each OPP)

    Returns
    -------
    dict with keys:
        ``opps``              — all OPPs with computed efficiency
        ``pareto_frontier``   — Pareto-optimal OPPs (best Perf/Watt per perf level)
        ``sweet_spot``        — recommended balanced OPP
        ``peak_perf_opp``     — highest frequency OPP
        ``max_efficiency_opp``— OPP with highest Perf/Watt
        ``diagnosis``         — human-readable summary
    """
    path = os.path.abspath(opp_table_path)
    if not os.path.isfile(path):
        return {"error": f"File not found: {path}"}

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".json":
            raw_opps = _load_opp_json(path)
        else:
            raw_opps = _load_opp_csv(path)
    except Exception as e:
        return {"error": f"Failed to parse OPP table: {e}"}

    if not raw_opps:
        return {"error": "No valid OPP entries found in file"}

    # Compute power and efficiency for each OPP
    opps: list[dict] = []
    for raw in raw_opps:
        opp: dict[str, Any] = {
            "freq_mhz": raw.get("freq_mhz", 0),
            "voltage_mv": raw.get("voltage_mv", 0),
        }
        # Use measured power if available, else estimate
        if "power_mw" in raw and raw["power_mw"] > 0:
            opp["power_mw"] = raw["power_mw"]
            opp["power_source"] = "measured"
        else:
            opp["power_mw"] = round(_estimate_power(opp["freq_mhz"], opp["voltage_mv"]) * 1000, 3)
            opp["power_source"] = "estimated (P∝CV²f)"

        # Use provided perf_score or use freq as proxy
        opp["perf_score"] = raw.get("perf_score", opp["freq_mhz"])

        if opp["power_mw"] > 0:
            opp["perf_per_watt"] = round(opp["perf_score"] / opp["power_mw"] * 1000, 3)
        else:
            opp["perf_per_watt"] = None

        opps.append(opp)

    # Sort by freq ascending
    opps.sort(key=lambda x: x["freq_mhz"])

    # Pareto frontier
    frontier = _pareto_frontier(opps)

    # Max efficiency OPP
    eff_opps = [o for o in opps if o["perf_per_watt"] is not None]
    max_eff_opp = max(eff_opps, key=lambda x: x["perf_per_watt"]) if eff_opps else None

    # Peak performance OPP
    peak_opp = max(opps, key=lambda x: x["freq_mhz"])

    # Sweet spot: OPP on Pareto frontier closest to 70th percentile of performance
    sweet_spot = None
    if frontier:
        perf_vals = [o["perf_score"] for o in frontier]
        target = min(perf_vals) + 0.7 * (max(perf_vals) - min(perf_vals))
        sweet_spot = min(frontier, key=lambda x: abs(x["perf_score"] - target))

    # Diagnosis
    if max_eff_opp and peak_opp and max_eff_opp["freq_mhz"] < peak_opp["freq_mhz"]:
        v_peak = peak_opp["voltage_mv"]
        v_eff = max_eff_opp["voltage_mv"]
        diagnosis = (
            f"Most efficient OPP: {max_eff_opp['freq_mhz']:.0f} MHz @ {v_eff} mV "
            f"({max_eff_opp['perf_per_watt']:.1f} score/W). "
            f"Peak OPP ({peak_opp['freq_mhz']:.0f} MHz @ {v_peak} mV) consumes "
            f"{((v_peak/v_eff)**2 * peak_opp['freq_mhz']/max_eff_opp['freq_mhz'] - 1)*100:.0f}% "
            "more power for marginal performance gain. "
            "Consider DVFS governor tuning to cap at sweet-spot OPP for battery-sensitive workloads."
        )
    else:
        diagnosis = (
            "Peak OPP is also most efficient — voltage scaling appears well-optimised. "
            "Verify measured power_mw values against lab power rail measurement."
        )

    return {
        "file": path,
        "opp_count": len(opps),
        "opps": opps,
        "pareto_frontier": frontier,
        "sweet_spot": sweet_spot,
        "peak_perf_opp": peak_opp,
        "max_efficiency_opp": max_eff_opp,
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json as _json
    if len(sys.argv) < 2:
        print("Usage: python dvfs_opp_calc.py <opp_table.csv|json>")
        sys.exit(1)
    print(_json.dumps(compute_dvfs_efficiency(sys.argv[1]), indent=2))
