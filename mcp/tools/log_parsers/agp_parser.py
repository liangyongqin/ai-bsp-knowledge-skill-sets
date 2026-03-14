"""
Android GPU Inspector (AGI) export parser.

Parses JSON exports from Android GPU Inspector (AGI) frame captures.
AGI exports frame profiling data including:
  - GPU pipeline stage breakdown (vertex, primitive, rasterization, fragment, output)
  - GPU counter values (occupancy, cache hit rate, memory bandwidth)
  - Render pass summary
  - Draw call statistics

AGI JSON export format: File → Export Capture in AGI desktop application.
Reference: https://gpuinspector.dev/docs/
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

# Known AGI counter groups
BANDWIDTH_COUNTERS = {
    "gpu_external_read_bytes", "gpu_external_write_bytes",
    "l2_read_bytes", "l2_write_bytes",
    "texture_read_bytes", "vertex_read_bytes",
}

OCCUPANCY_COUNTERS = {
    "gpu_occupancy", "shader_occupancy", "warp_occupancy",
    "warps_in_flight", "active_warps",
}

CACHE_HIT_COUNTERS = {
    "l1_cache_hit_rate", "l2_cache_hit_rate",
    "texture_cache_hit_rate", "l1_tex_hit",
}


def _flatten_counters(obj: Any, prefix: str = "") -> dict[str, float]:
    """Recursively flatten nested counter dicts to {key: value}."""
    result = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            result.update(_flatten_counters(v, full_key))
    elif isinstance(obj, (int, float)):
        result[prefix] = float(obj)
    return result


def parse_agp_report(trace_path: str) -> dict[str, Any]:
    """Parse an Android GPU Inspector JSON frame capture export.

    Parameters
    ----------
    trace_path:
        Path to AGI JSON export file.

    Returns
    -------
    dict with keys:
        ``frame_count``        — number of frames in capture
        ``draw_call_count``    — total draw calls
        ``render_passes``      — render pass summary
        ``pipeline_breakdown`` — avg time per pipeline stage (ms)
        ``bandwidth_mb_s``     — memory bandwidth counters (MB/s)
        ``occupancy``          — shader occupancy metrics
        ``cache_hit_rates``    — cache efficiency metrics
        ``bottleneck``         — identified bottleneck stage
        ``diagnosis``          — human-readable summary
    """
    path = os.path.abspath(trace_path)
    if not os.path.isfile(path):
        return {"error": f"File not found: {path}"}

    try:
        with open(path, "r", errors="replace") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}

    if not isinstance(data, dict):
        return {"error": "Unexpected AGI export format — expected JSON object at root"}

    # Navigate AGI export structure (may vary by AGI version)
    frames = data.get("frames", data.get("frame_captures", [data]))
    if not isinstance(frames, list):
        frames = [frames]

    total_draw_calls = 0
    render_passes: list[dict] = []
    pipeline_times: dict[str, list[float]] = defaultdict(list)
    all_counters: dict[str, list[float]] = defaultdict(list)

    for frame in frames:
        if not isinstance(frame, dict):
            continue

        # Draw calls
        draw_calls = frame.get("draw_calls", frame.get("drawCalls", []))
        if isinstance(draw_calls, list):
            total_draw_calls += len(draw_calls)
        elif isinstance(draw_calls, int):
            total_draw_calls += draw_calls

        # Render passes
        passes = frame.get("render_passes", frame.get("renderPasses", []))
        if isinstance(passes, list):
            for rp in passes:
                if isinstance(rp, dict):
                    render_passes.append({
                        "name": rp.get("name", rp.get("label", "unknown")),
                        "draw_count": rp.get("draw_count", rp.get("drawCount", 0)),
                        "duration_ms": rp.get("duration_ms", rp.get("durationMs", None)),
                    })

        # Pipeline stage breakdown
        stages = frame.get("pipeline_stages", frame.get("pipelineStages", {}))
        if isinstance(stages, dict):
            for stage, val in stages.items():
                if isinstance(val, (int, float)):
                    pipeline_times[stage].append(float(val))

        # GPU counters
        counters = frame.get("counters", frame.get("gpu_counters", {}))
        if isinstance(counters, dict):
            flat = _flatten_counters(counters)
            for k, v in flat.items():
                all_counters[k.lower()].append(v)

    # Average pipeline times
    avg_pipeline = {
        stage: round(sum(vals) / len(vals), 3)
        for stage, vals in pipeline_times.items()
        if vals
    }

    # Bandwidth (MB/s)
    bandwidth = {}
    for key in BANDWIDTH_COUNTERS:
        matches = {k: v for k, v in all_counters.items() if key in k}
        for k, v in matches.items():
            avg = sum(v) / len(v) if v else 0
            bandwidth[k] = round(avg / 1e6, 2)  # bytes → MB

    # Occupancy
    occupancy = {}
    for key in OCCUPANCY_COUNTERS:
        matches = {k: v for k, v in all_counters.items() if key in k}
        for k, v in matches.items():
            occupancy[k] = round(sum(v) / len(v), 2) if v else 0

    # Cache hit rates
    cache_hits = {}
    for key in CACHE_HIT_COUNTERS:
        matches = {k: v for k, v in all_counters.items() if key in k}
        for k, v in matches.items():
            cache_hits[k] = round(sum(v) / len(v), 2) if v else 0

    # Bottleneck identification
    bottleneck = "unknown"
    if avg_pipeline:
        bottleneck = max(avg_pipeline, key=lambda k: avg_pipeline[k])

    # Diagnosis
    issues = []
    if occupancy and any(v < 50 for v in occupancy.values()):
        low_occ = {k: v for k, v in occupancy.items() if v < 50}
        issues.append(
            f"Low shader occupancy: {low_occ}. "
            "Increase thread block size or reduce register pressure per thread."
        )
    if cache_hits and any(v < 70 for v in cache_hits.values()):
        low_cache = {k: v for k, v in cache_hits.items() if v < 70}
        issues.append(
            f"Low cache hit rate: {low_cache}. "
            "Review texture sampling patterns and improve spatial locality."
        )
    if bottleneck != "unknown":
        issues.append(f"Pipeline bottleneck: '{bottleneck}' stage dominates frame time.")

    if not frames or total_draw_calls == 0:
        diagnosis = "No frame data found. Verify this is a valid AGI JSON export (File → Export Capture)."
    elif issues:
        diagnosis = " | ".join(issues)
    else:
        diagnosis = (
            f"AGI report: {len(frames)} frame(s), {total_draw_calls} draw calls. "
            f"No critical GPU bottleneck detected. Bottleneck stage: '{bottleneck}'."
        )

    return {
        "file": path,
        "frame_count": len(frames),
        "draw_call_count": total_draw_calls,
        "render_passes": render_passes[:15],
        "pipeline_breakdown_ms": avg_pipeline,
        "bandwidth_mb_s": bandwidth,
        "occupancy": occupancy,
        "cache_hit_rates": cache_hits,
        "bottleneck": bottleneck,
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python agp_parser.py <agi_export.json>")
        sys.exit(1)
    import json as _json
    print(_json.dumps(parse_agp_report(sys.argv[1]), indent=2))
