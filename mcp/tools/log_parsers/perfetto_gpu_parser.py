"""
Perfetto GPU trace parser — GPU task timeline from Perfetto JSON trace.

Parses Perfetto JSON trace exports (File → Export → JSON in the Perfetto UI,
or `python traceconv --json trace.pb > trace.json`) for:
  - GPU work slice durations (vertex, fragment, compute)
  - GPU queue submission latency (CPU submit to GPU start)
  - GPU frequency samples (if gpu_frequency data source enabled)
  - Frame timeline events (SurfaceFlinger jank)

Reference: https://perfetto.dev/docs/data-sources/gpu
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

# GPU slice category names used by Perfetto drivers
GPU_SLICE_CATEGORIES = {
    "gpu", "gpu_work", "mali", "adreno", "gpu_command",
    "gpu_hw", "gpu_memory", "gfx",
}

JANK_THRESHOLD_MS = 16.67  # One frame at 60 FPS


def _ms(duration_ns: int | float) -> float:
    return round(duration_ns / 1_000_000, 3)


def parse_perfetto_gpu(trace_path: str) -> dict[str, Any]:
    """Parse a Perfetto JSON trace for GPU performance metrics.

    Parameters
    ----------
    trace_path:
        Path to Perfetto JSON trace file.

    Returns
    -------
    dict with keys:
        ``gpu_slices``         — summary of GPU work slices by name
        ``submission_latency`` — CPU-to-GPU submission latency stats (ms)
        ``gpu_freq_samples``   — GPU frequency histogram (MHz)
        ``jank_frames``        — frames exceeding 16.67ms
        ``total_gpu_work_ms``  — total GPU-active time in trace
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

    # Perfetto JSON may use traceEvents key (Chrome trace format)
    events = data if isinstance(data, list) else data.get("traceEvents", [])

    # {slice_name: {count, total_dur_us, max_dur_us}}
    gpu_slices: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_us": 0.0, "max_us": 0.0})
    freq_samples: dict[int, int] = defaultdict(int)  # {freq_mhz: count}
    jank_frames: list[dict] = []
    submission_latencies: list[float] = []  # ms

    # Track B (begin) events for duration computation
    open_events: dict[str, float] = {}  # {tid+name: ts_us}

    for ev in events:
        if not isinstance(ev, dict):
            continue

        ph = ev.get("ph", "")
        cat = ev.get("cat", "").lower()
        name = ev.get("name", "")
        ts = ev.get("ts", 0)        # microseconds
        dur = ev.get("dur", 0)      # microseconds
        tid = str(ev.get("tid", ""))
        args = ev.get("args", {})

        # GPU work slices (Complete events with duration)
        if ph == "X" and any(g in cat for g in GPU_SLICE_CATEGORIES):
            entry = gpu_slices[name]
            entry["count"] += 1
            entry["total_us"] += dur
            if dur > entry["max_us"]:
                entry["max_us"] = dur

        # GPU frequency counter
        if name in ("gpu_frequency", "GPU Frequency", "mali_gpu_clock") and ph == "C":
            freq_hz = args.get("value", 0) if isinstance(args, dict) else 0
            if freq_hz > 0:
                freq_mhz = int(freq_hz) // 1_000_000
                if freq_mhz == 0:
                    freq_mhz = int(freq_hz) // 1_000  # already kHz
                freq_samples[freq_mhz] += 1

        # Frame timeline jank detection
        if name in ("Choreographer#doFrame", "DrawFrame", "actual_timeline") and ph == "X":
            dur_ms = dur / 1000.0
            if dur_ms > JANK_THRESHOLD_MS:
                jank_frames.append({"name": name, "duration_ms": round(dur_ms, 2), "ts_us": ts})

        # GPU submission latency (B/E pair tracking for "gpu_command" or "QueueSubmit")
        if name in ("vkQueueSubmit", "glFlush", "eglSwapBuffers", "QueueSubmit"):
            key = f"{tid}_{name}"
            if ph == "B":
                open_events[key] = ts
            elif ph == "E" and key in open_events:
                lat_us = ts - open_events.pop(key)
                submission_latencies.append(lat_us / 1000.0)  # ms

    # Build output
    slice_summary = []
    for name, stats in sorted(gpu_slices.items(), key=lambda x: -x[1]["total_us"])[:20]:
        slice_summary.append({
            "name": name,
            "count": stats["count"],
            "total_ms": _ms(stats["total_us"] * 1000),
            "avg_ms": _ms(stats["total_us"] * 1000 / stats["count"]) if stats["count"] else 0,
            "max_ms": _ms(stats["max_us"] * 1000),
        })

    total_gpu_ms = sum(s["total_ms"] for s in slice_summary)

    avg_latency = sum(submission_latencies) / len(submission_latencies) if submission_latencies else None
    max_latency = max(submission_latencies) if submission_latencies else None

    # Diagnosis
    issues = []
    if jank_frames:
        worst = max(jank_frames, key=lambda x: x["duration_ms"])
        issues.append(
            f"{len(jank_frames)} janky frame(s) exceeding {JANK_THRESHOLD_MS:.1f}ms. "
            f"Worst: {worst['name']} at {worst['duration_ms']:.1f}ms. "
            "Reduce draw call count or shader complexity. "
            "Escalate to /gpu-rendering-expert for Depth Pre-pass and overdraw analysis."
        )
    if max_latency and max_latency > 5.0:
        issues.append(
            f"High GPU submission latency: max={max_latency:.1f}ms. "
            "CPU is stalling on vkQueueSubmit/eglSwapBuffers — check driver fence handling."
        )
    if not slice_summary:
        issues.append("No GPU slice data found. Ensure 'gpu.mali'/'gpu.adreno' data source is enabled in Perfetto config.")

    diagnosis = " | ".join(issues) if issues else (
        f"GPU trace parsed: {len(slice_summary)} unique GPU slice types, "
        f"total GPU work={total_gpu_ms:.1f}ms. No jank detected."
    )

    return {
        "file": path,
        "gpu_slices": slice_summary,
        "total_gpu_work_ms": round(total_gpu_ms, 2),
        "jank_frames": jank_frames[:10],
        "jank_count": len(jank_frames),
        "submission_latency_ms": {
            "avg": round(avg_latency, 2) if avg_latency else None,
            "max": round(max_latency, 2) if max_latency else None,
            "samples": len(submission_latencies),
        },
        "gpu_freq_histogram": {f"{k}MHz": v for k, v in sorted(freq_samples.items())},
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python perfetto_gpu_parser.py <trace.json>")
        sys.exit(1)
    import json as _json
    print(_json.dumps(parse_perfetto_gpu(sys.argv[1]), indent=2))
