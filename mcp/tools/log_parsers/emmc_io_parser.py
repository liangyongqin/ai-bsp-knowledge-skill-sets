"""
eMMC / F2FS I/O parser — GC stalls, checkpoint latency, and I/O throughput analysis.

Parses:
  - `iostat -x` output: utilization, await, service time per block device
  - dmesg F2FS messages: GC (garbage collection) events, checkpoint stalls
  - /proc/fs/f2fs/<dev>/segment_info (optional, F2FS segment statistics)

Detects:
  - High I/O await (>50ms) indicating eMMC queue saturation
  - F2FS GC storms (frequent background GC, foreground GC stalls)
  - Checkpoint latency (flush + fsync contention)
  - eMMC half-duplex bottleneck (read interrupted by write)
"""

from __future__ import annotations

import re
import os
from typing import Any

# iostat -x line:
# Device   r/s   w/s   rkB/s   wkB/s  rrqm/s  wrqm/s  %rrqm  %wrqm  r_await  w_await  aqu-sz  rareq-sz  wareq-sz  svctm  %util
_IOSTAT_RE = re.compile(
    r"^(?P<dev>\S+)\s+"
    r"(?P<rs>[\d.]+)\s+(?P<ws>[\d.]+)\s+"
    r"(?P<rkb>[\d.]+)\s+(?P<wkb>[\d.]+)\s+"
    r"[\d.]+\s+[\d.]+\s+"         # rrqm/s wrqm/s
    r"[\d.]+\s+[\d.]+\s+"         # %rrqm %wrqm
    r"(?P<r_await>[\d.]+)\s+(?P<w_await>[\d.]+)\s+"
    r"[\d.]+\s+"                  # aqu-sz
    r"[\d.]+\s+[\d.]+\s+"         # rareq-sz wareq-sz
    r"(?P<svctm>[\d.]+)\s+(?P<util>[\d.]+)"
)

# Simpler iostat format (older util): "mmcblk0  0.00  12.34  ..."
_IOSTAT_SIMPLE_RE = re.compile(
    r"^(?P<dev>mmcblk\d+\w*|sda|nvme\d+n\d+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+(?P<await>[\d.]+)\s+\S+\s+(?P<util>[\d.]+)"
)

# F2FS GC event: "[f2fs] f2fs_gc: victim seg=N type=BG/FG"
_F2FS_GC_RE = re.compile(
    r"(?P<ts>[\d.]+).*?f2fs.*?gc[:\s].*?(?P<type>BG|FG|background|foreground)",
    re.IGNORECASE,
)

# F2FS checkpoint: "f2fs_write_checkpoint" or "checkpoint latency"
_F2FS_CKPT_RE = re.compile(
    r"(?P<ts>[\d.]+).*?(?:f2fs_write_checkpoint|checkpoint.*?latency|f2fs.*?checkpoint)",
    re.IGNORECASE,
)

# F2FS error: "f2fs: ... failed" or "f2fs_bug_on"
_F2FS_ERR_RE = re.compile(
    r"(?P<ts>[\d.]+).*?f2fs.*?(?:failed|error|bug_on|corruption)",
    re.IGNORECASE,
)

AWAIT_WARN_MS = 50.0
UTIL_WARN_PCT = 80.0


def parse_emmc_io_log(log_path: str) -> dict[str, Any]:
    """Parse eMMC I/O and F2FS log for performance issues.

    Parameters
    ----------
    log_path:
        Path to iostat output file or dmesg with F2FS messages (or combined).

    Returns
    -------
    dict with keys:
        ``devices``           — per-device I/O statistics from iostat
        ``f2fs_gc_events``    — GC event count by type (BG/FG)
        ``f2fs_checkpoints``  — checkpoint event count
        ``f2fs_errors``       — F2FS error lines
        ``diagnosis``         — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    devices: dict[str, dict] = {}
    gc_bg = 0
    gc_fg = 0
    checkpoint_count = 0
    f2fs_errors: list[str] = []

    for line in lines:
        # iostat extended
        m = _IOSTAT_RE.match(line)
        if m:
            dev = m.group("dev")
            devices[dev] = {
                "dev": dev,
                "reads_per_s": float(m.group("rs")),
                "writes_per_s": float(m.group("ws")),
                "read_kb_s": float(m.group("rkb")),
                "write_kb_s": float(m.group("wkb")),
                "r_await_ms": float(m.group("r_await")),
                "w_await_ms": float(m.group("w_await")),
                "util_pct": float(m.group("util")),
            }
            continue

        # iostat simple
        m = _IOSTAT_SIMPLE_RE.match(line)
        if m and m.group("dev") not in devices:
            devices[m.group("dev")] = {
                "dev": m.group("dev"),
                "await_ms": float(m.group("await")),
                "util_pct": float(m.group("util")),
            }
            continue

        # F2FS GC
        m = _F2FS_GC_RE.search(line)
        if m:
            gc_type = m.group("type").upper()
            if "FG" in gc_type or "FORE" in gc_type:
                gc_fg += 1
            else:
                gc_bg += 1
            continue

        # F2FS checkpoint
        if _F2FS_CKPT_RE.search(line):
            checkpoint_count += 1

        # F2FS error
        if _F2FS_ERR_RE.search(line):
            f2fs_errors.append(line.strip())

    # Find worst device
    worst_dev = None
    worst_await = 0.0
    for dev, stats in devices.items():
        await_val = stats.get("w_await_ms") or stats.get("await_ms") or 0
        if await_val > worst_await:
            worst_await = await_val
            worst_dev = dev

    # Diagnosis
    issues = []
    if gc_fg > 0:
        issues.append(
            f"F2FS foreground GC triggered {gc_fg} time(s) — this causes synchronous stalls! "
            "Increase free segment threshold: mount with gc_min_sleep_time and gc_max_sleep_time tuning. "
            "Alternatively, reduce write amplification by using F2FS_IOC_ABORT_VOLATILE_WRITE."
        )
    if worst_dev and worst_await > AWAIT_WARN_MS:
        issues.append(
            f"eMMC device '{worst_dev}' write await={worst_await:.1f}ms (threshold {AWAIT_WARN_MS}ms). "
            "eMMC half-duplex: simultaneous R+W causes read interruption. "
            "Separate read/write streams using blkdev_issue_flush() barriers and nomerge mount option."
        )
    if f2fs_errors:
        issues.append(f"F2FS filesystem error(s): {f2fs_errors[0][:100]}")

    if issues:
        diagnosis = " | ".join(issues)
    elif gc_bg > 10:
        diagnosis = (
            f"F2FS background GC active ({gc_bg} events) — normal for aging filesystem. "
            "Monitor free_segments via /proc/fs/f2fs/<dev>/segment_info. "
            "If latency spikes correlate with GC, consider discard=async mount option."
        )
    else:
        diagnosis = "No significant eMMC I/O or F2FS stall issues detected."

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "devices": list(devices.values()),
        "f2fs_gc_events": {"background": gc_bg, "foreground": gc_fg},
        "f2fs_checkpoints": checkpoint_count,
        "f2fs_errors": f2fs_errors[:10],
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python emmc_io_parser.py <iostat_or_dmesg_log>")
        sys.exit(1)
    print(json.dumps(parse_emmc_io_log(sys.argv[1]), indent=2))
