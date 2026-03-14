"""
V4L2 stats parser — buffer queue depth, overflow events, and pipeline stalls.

Parses:
  - v4l2-ctl --stream-mmap --verbose output (buffer queue/dequeue events)
  - kernel dmesg V4L2 / media controller messages
  - /sys/class/video4linux/videoN/name and statistics

Detects:
  - Buffer underruns (queue depth → 0)
  - Buffer overflow (driver drops frames)
  - DQBUF timeout (consumer too slow)
  - Pipeline link errors (media controller topology issues)
"""

from __future__ import annotations

import re
import os
from typing import Any

# v4l2-ctl verbose QBUF: "<0> queued buffer"  or  "Buffer 0 queued"
_QBUF_RE = re.compile(
    r"(?P<ts>[\d.]+)?\s*(?:Buffer\s+(?P<idx>\d+)\s+queued|<(?P<idx2>\d+)>\s+queued buffer)",
    re.IGNORECASE,
)

# v4l2-ctl verbose DQBUF: "<0> dequeued buffer" or "Buffer 0 dequeued"
_DQBUF_RE = re.compile(
    r"(?P<ts>[\d.]+)?\s*(?:Buffer\s+(?P<idx>\d+)\s+dequeued|<(?P<idx2>\d+)>\s+dequeued buffer)",
    re.IGNORECASE,
)

# Frame interval / FPS: "fps: 29.97" or "30.00 frames/s"
_FPS_RE = re.compile(r"(?P<fps>[\d.]+)\s+(?:fps|frames?/s)", re.IGNORECASE)

# V4L2 error / overflow in dmesg
_V4L2_ERR_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?:v4l2|video|camera|isp|csi).*?(?:overflow|underrun|timeout|error|failed|dropped)",
    re.IGNORECASE,
)

# Media controller link error: "media: pipeline link failed"
_MEDIA_LINK_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?:media.*?link|pipeline).*?(?:error|failed|not enabled)",
    re.IGNORECASE,
)

# Timestamp-only for v4l2-ctl output (seconds since capture start)
_TS_ONLY_RE = re.compile(r"^(?P<ts>[\d]+\.[\d]+)\s")

UNDERRUN_QUEUE_DEPTH = 1  # queue depth at or below this triggers underrun warning


def parse_v4l2_log(log_path: str) -> dict[str, Any]:
    """Parse V4L2 buffer queue log for pipeline health.

    Parameters
    ----------
    log_path:
        Path to v4l2-ctl verbose output or kernel dmesg with V4L2 messages.

    Returns
    -------
    dict with keys:
        ``total_queued``      — total QBUF calls
        ``total_dequeued``    — total DQBUF calls
        ``queue_depth_min``   — minimum observed queue depth (underrun indicator)
        ``fps_samples``       — FPS values parsed from log
        ``errors``            — V4L2/media errors from dmesg
        ``media_link_errors`` — media controller pipeline link errors
        ``diagnosis``         — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    total_queued = 0
    total_dequeued = 0
    queue_depth = 0
    min_queue_depth = float("inf")
    fps_samples: list[float] = []
    errors: list[str] = []
    media_link_errors: list[str] = []

    for line in lines:
        # QBUF
        if _QBUF_RE.search(line):
            total_queued += 1
            queue_depth += 1
            min_queue_depth = min(min_queue_depth, queue_depth)

        # DQBUF
        if _DQBUF_RE.search(line):
            total_dequeued += 1
            queue_depth = max(0, queue_depth - 1)
            min_queue_depth = min(min_queue_depth, queue_depth)

        # FPS
        m = _FPS_RE.search(line)
        if m:
            fps_samples.append(float(m.group("fps")))

        # Errors
        if _V4L2_ERR_RE.search(line):
            errors.append(line.strip())

        # Media link errors
        if _MEDIA_LINK_RE.search(line):
            media_link_errors.append(line.strip())

    if min_queue_depth == float("inf"):
        min_queue_depth = None
    else:
        min_queue_depth = int(min_queue_depth)

    avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else None

    # Diagnosis
    if media_link_errors:
        diagnosis = (
            f"{len(media_link_errors)} media controller link error(s). "
            "Pipeline topology is broken — run: media-ctl -p to verify link state. "
            "Ensure all links are enabled with MEDIA_LNK_FL_ENABLED before STREAMON. "
            "Escalate to /multimedia-camera-expert for sensor-to-ISP link validation."
        )
    elif min_queue_depth == 0:
        diagnosis = (
            "Buffer queue reached depth=0 — pipeline stall detected (underrun). "
            f"Total queued: {total_queued}, dequeued: {total_dequeued}. "
            "The consumer (ISP/DMA) is faster than the producer (sensor/CPU). "
            "Increase REQBUFS count or reduce processing latency in DQBUF handler."
        )
    elif errors:
        diagnosis = (
            f"{len(errors)} V4L2 error(s). "
            f"First: {errors[0][:120]}. "
            "Check sensor I2C ACK, MIPI clock lane continuity, and ISP power domain."
        )
    else:
        fps_str = f", avg FPS={avg_fps:.1f}" if avg_fps else ""
        diagnosis = (
            f"V4L2 pipeline appears healthy. "
            f"Queued: {total_queued}, dequeued: {total_dequeued}{fps_str}. "
            f"Minimum queue depth: {min_queue_depth}."
        )

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "total_queued": total_queued,
        "total_dequeued": total_dequeued,
        "queue_depth_min": min_queue_depth,
        "fps_samples": fps_samples[:10],
        "avg_fps": round(avg_fps, 2) if avg_fps else None,
        "errors": errors[:10],
        "media_link_errors": media_link_errors[:10],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python v4l2_stats_parser.py <v4l2_log>")
        sys.exit(1)
    print(json.dumps(parse_v4l2_log(sys.argv[1]), indent=2))
