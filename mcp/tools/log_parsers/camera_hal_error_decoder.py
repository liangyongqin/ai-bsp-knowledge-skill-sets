"""
Camera HAL3 error decoder — Android Camera HAL3 error code analysis.

Parses Android logcat (or adb logcat) output for Camera HAL3 error notifications
and HAL3 state machine violations.

HAL3 error codes (from camera3.h):
  CAMERA3_MSG_ERROR_DEVICE  = 1  — fatal device error
  CAMERA3_MSG_ERROR_REQUEST = 2  — request processing error
  CAMERA3_MSG_ERROR_RESULT  = 3  — result metadata error
  CAMERA3_MSG_ERROR_BUFFER  = 4  — buffer error

Reference: Android Camera HAL3 spec, hardware/interfaces/camera/
"""

from __future__ import annotations

import re
import os
from typing import Any

# logcat prefix: "MM-DD HH:MM:SS.mmm  PID  TID  LEVEL TAG: message"
_LOGCAT_RE = re.compile(
    r"^(?:[\d\-]+\s+[\d:.]+\s+)?\s*(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<level>[VDIWEF])\s+(?P<tag>\S+)\s*:\s+(?P<msg>.*)"
)

# HAL3 error notification: "Camera HAL3 error: error_code=N frame=M stream=K"
_HAL3_ERROR_RE = re.compile(
    r"(?:camera3?|hal3?).*?error[_\s]*(?:code)?[=:\s]+(?P<code>\d+)"
    r"(?:.*?frame[=:\s]+(?P<frame>\d+))?"
    r"(?:.*?stream[=:\s]+(?P<stream>-?\d+))?",
    re.IGNORECASE,
)

# CameraService errors
_CAM_SVC_RE = re.compile(
    r"CameraService.*?(?P<err>error|failed|disconnect|timeout|permission)",
    re.IGNORECASE,
)

# HAL open failure
_HAL_OPEN_RE = re.compile(
    r"(?:openCamera|camera_device_open|hal.*?open).*?(?:failed|error|errno\s*=\s*(?P<errno>-?\d+))",
    re.IGNORECASE,
)

# Timeout patterns
_TIMEOUT_RE = re.compile(
    r"(?:capture|shutter|result|hal|request).*?timeout",
    re.IGNORECASE,
)

# HAL3 error code descriptions
HAL3_ERROR_CODES = {
    1: "CAMERA3_MSG_ERROR_DEVICE — Fatal device error; camera must be closed and reopened",
    2: "CAMERA3_MSG_ERROR_REQUEST — Request could not be processed; this frame is dropped",
    3: "CAMERA3_MSG_ERROR_RESULT — Result metadata missing/incomplete for this frame",
    4: "CAMERA3_MSG_ERROR_BUFFER — Stream buffer could not be filled for this request",
}

# Android camera error codes (CameraAccessException)
ANDROID_CAM_ERRORS = {
    "1": "CAMERA_IN_USE — Camera device is already in use by another app",
    "2": "MAX_CAMERAS_IN_USE — System-wide camera limit reached",
    "3": "CAMERA_DISABLED — Camera disabled by device policy (MDM)",
    "4": "CAMERA_DISCONNECTED — Camera device no longer available (physically disconnected)",
    "5": "CAMERA_ERROR — Camera device encountered a fatal error",
}


def parse_camera_hal_errors(log_path: str) -> dict[str, Any]:
    """Decode Camera HAL3 error codes from Android logcat.

    Parameters
    ----------
    log_path:
        Path to logcat output file (adb logcat -v threadtime > file.txt).

    Returns
    -------
    dict with keys:
        ``hal3_errors``       — list of decoded HAL3 error notifications
        ``open_failures``     — camera open failure lines
        ``timeouts``          — capture/result timeout events
        ``error_summary``     — count by error code
        ``diagnosis``         — human-readable summary
    """
    log_path = os.path.abspath(log_path)
    if not os.path.isfile(log_path):
        return {"error": f"File not found: {log_path}"}

    with open(log_path, "r", errors="replace") as fh:
        lines = fh.readlines()

    hal3_errors: list[dict] = []
    open_failures: list[str] = []
    timeouts: list[str] = []
    error_counts: dict[int, int] = {}
    cam_svc_errors: list[str] = []

    for line in lines:
        # HAL3 error codes
        m = _HAL3_ERROR_RE.search(line)
        if m:
            code = int(m.group("code"))
            if code in HAL3_ERROR_CODES:
                hal3_errors.append({
                    "code": code,
                    "description": HAL3_ERROR_CODES[code],
                    "frame": m.group("frame"),
                    "stream": m.group("stream"),
                    "line": line.strip()[:200],
                })
                error_counts[code] = error_counts.get(code, 0) + 1

        # Camera service errors
        if _CAM_SVC_RE.search(line):
            cam_svc_errors.append(line.strip()[:200])

        # Open failures
        if _HAL_OPEN_RE.search(line):
            open_failures.append(line.strip()[:200])

        # Timeouts
        if _TIMEOUT_RE.search(line):
            timeouts.append(line.strip()[:200])

    # Diagnosis
    if any(c == 1 for c in error_counts):
        diagnosis = (
            f"FATAL: CAMERA3_MSG_ERROR_DEVICE detected {error_counts.get(1, 0)} time(s). "
            "Camera HAL has encountered an unrecoverable error — the camera must be closed and "
            "reopened (CameraDevice.close() + CameraManager.openCamera()). "
            "Check dmesg for I2C/MIPI initialization failures. "
            "Escalate to /multimedia-camera-expert for sensor bring-up review."
        )
    elif open_failures:
        diagnosis = (
            f"{len(open_failures)} camera open failure(s). "
            "Check: (1) camera HAL .so loaded correctly, (2) /dev/videoN permissions, "
            "(3) SELinux denial (adb shell dmesg | grep avc | grep camera), "
            "(4) power sequence for MCLK and AVDD rails."
        )
    elif timeouts:
        diagnosis = (
            f"{len(timeouts)} capture/result timeout(s). "
            "HAL is not delivering results within the timeout window. "
            "Check ISP pipeline stalls (use parse_v4l2_log) and "
            "verify that capture request pipeline depth ≤ pipeline_max_depth."
        )
    elif error_counts:
        most_common = max(error_counts, key=lambda k: error_counts[k])
        diagnosis = (
            f"Most common error: code {most_common} ({HAL3_ERROR_CODES.get(most_common, 'unknown')}) "
            f"× {error_counts[most_common]}. "
            "Total errors by code: " + ", ".join(f"code{k}×{v}" for k, v in error_counts.items())
        )
    else:
        diagnosis = "No Camera HAL3 error codes detected in log."

    return {
        "file": log_path,
        "lines_parsed": len(lines),
        "hal3_errors": hal3_errors[:20],
        "open_failures": open_failures[:10],
        "timeouts": timeouts[:10],
        "camera_service_errors": cam_svc_errors[:10],
        "error_summary": {f"code_{k}": v for k, v in error_counts.items()},
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python camera_hal_error_decoder.py <logcat_file>")
        sys.exit(1)
    print(json.dumps(parse_camera_hal_errors(sys.argv[1]), indent=2))
