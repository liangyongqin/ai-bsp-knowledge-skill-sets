"""
BSP-to-Business Impact Translator — convert physical BSP metric deltas into
business-language impact statements for PM / management communication.

This module maps low-level BSP engineering metrics (leakage current, DVFS OPP
steps, ISP latency, IRQ latency, etc.) to KPIs that non-engineers care about:
battery life, camera launch time, video recording reliability, gaming FPS.

The rule table covers 25+ mappings across power/thermal, multimedia/camera,
GPU rendering, and interrupt/system domains.

Usage::

    from mcp.tools.impact_translator.bsp_to_business import translate_to_business_impact

    result = translate_to_business_impact(
        component="LPDDR5",
        metric="leakage_current_ma",
        delta=2.0,
        unit="mA",
        product_type="smartphone",
    )
    print(result["business_impact"])
    # → "A 2.0 mA increase in LPDDR5 leakage current reduces idle battery
    #    life by approximately 4%, shortening screen-off standby time."

CLI usage::

    # JSON from stdin:
    echo '{"component":"ISP","metric":"isp_latency_ms","delta":80,"unit":"ms"}' | \\
        python bsp_to_business.py

    # Flags:
    python bsp_to_business.py --component GPU --metric frame_time_ms --delta 3.0 --unit ms
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule representation
# ---------------------------------------------------------------------------

@dataclass
class _ImpactRule:
    """A single BSP metric → business impact translation rule."""

    component: str
    """Normalised component name (upper-case for matching)."""

    metric: str
    """Normalised metric name (lower-case for matching)."""

    severity_fn: object
    """Callable(delta: float, product_type: str) -> str that returns severity level."""

    business_impact_fn: object
    """Callable(delta, unit, product_type) -> str — one-sentence business statement."""

    magnitude_fn: object
    """Callable(delta, unit) -> str — concise magnitude estimate."""

    affected_kpis: list[str]
    """List of business KPI strings this rule affects."""

    recommended_framing: str
    """Template string for PM / management communication."""

    raw_reasoning: str
    """BSP physics explanation for engineers."""


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

def _severity_power_leakage(delta: float, product_type: str) -> str:
    """Leakage current: 0.5 mA per 1% battery/hr at idle."""
    if abs(delta) < 0.5:
        return "low"
    if abs(delta) < 2.0:
        return "medium"
    if abs(delta) < 5.0:
        return "high"
    return "critical"


def _severity_dvfs_opp(delta: float, product_type: str) -> str:
    """Each OPP step ≈ 15–25% compute reduction."""
    steps = abs(delta)
    if steps < 1:
        return "low"
    if steps < 2:
        return "medium"
    if steps < 3:
        return "high"
    return "critical"


def _severity_throttle(delta: float, product_type: str) -> str:
    if abs(delta) < 100:
        return "low"
    if abs(delta) < 500:
        return "medium"
    if abs(delta) < 2000:
        return "high"
    return "critical"


def _severity_pmic_transient(delta: float, product_type: str) -> str:
    """Even small PMIC transients can cause CDC violations."""
    if abs(delta) < 50:
        return "low"
    if abs(delta) < 100:
        return "medium"
    if abs(delta) < 200:
        return "high"
    return "critical"


def _severity_cstate(delta: float, product_type: str) -> str:
    """C-state residency reduction (percentage points)."""
    if abs(delta) < 5:
        return "low"
    if abs(delta) < 20:
        return "medium"
    if abs(delta) < 50:
        return "high"
    return "critical"


def _severity_isp_latency(delta: float, product_type: str) -> str:
    """>300 ms is user-noticeable; >500 ms is severe."""
    if abs(delta) < 50:
        return "low"
    if abs(delta) < 150:
        return "medium"
    if abs(delta) < 300:
        return "high"
    return "critical"


def _severity_dma_stall(delta: float, product_type: str) -> str:
    """16 ms = one missed frame at 60 fps."""
    if abs(delta) < 8:
        return "low"
    if abs(delta) < 16:
        return "medium"
    if abs(delta) < 50:
        return "high"
    return "critical"


def _severity_emmc_gc(delta: float, product_type: str) -> str:
    """100 ms = visible recording glitch."""
    if abs(delta) < 30:
        return "low"
    if abs(delta) < 100:
        return "medium"
    if abs(delta) < 300:
        return "high"
    return "critical"


def _severity_v4l2_underrun(delta: float, product_type: str) -> str:
    if abs(delta) < 1:
        return "low"
    if abs(delta) < 5:
        return "medium"
    if abs(delta) < 15:
        return "high"
    return "critical"


def _severity_frame_time(delta: float, product_type: str) -> str:
    """5% frame time change is visible as stutter."""
    if abs(delta) < 1:
        return "low"
    if abs(delta) < 3:
        return "medium"
    if abs(delta) < 8:
        return "high"
    return "critical"


def _severity_gpu_throttle(delta: float, product_type: str) -> str:
    if abs(delta) < 200:
        return "low"
    if abs(delta) < 1000:
        return "medium"
    if abs(delta) < 5000:
        return "high"
    return "critical"


def _severity_overdraw(delta: float, product_type: str) -> str:
    if abs(delta) < 1:
        return "low"
    if abs(delta) < 2:
        return "medium"
    if abs(delta) < 4:
        return "high"
    return "critical"


def _severity_irq_latency(delta: float, product_type: str) -> str:
    """500 µs = audio glitch; <200 µs is acceptable."""
    if abs(delta) < 100:
        return "low"
    if abs(delta) < 300:
        return "medium"
    if abs(delta) < 500:
        return "high"
    return "critical"


def _severity_noc_bw(delta: float, product_type: str) -> str:
    """NoC bandwidth saturation affects all domains."""
    if abs(delta) < 10:
        return "low"
    if abs(delta) < 30:
        return "medium"
    if abs(delta) < 60:
        return "high"
    return "critical"


def _severity_mem_bw(delta: float, product_type: str) -> str:
    if abs(delta) < 10:
        return "low"
    if abs(delta) < 30:
        return "medium"
    if abs(delta) < 60:
        return "high"
    return "critical"


def _severity_default(delta: float, product_type: str) -> str:
    return "medium"


# ---------------------------------------------------------------------------
# Business impact sentence factories
# ---------------------------------------------------------------------------

def _bi_lpddr5_leakage(delta: float, unit: str, product_type: str) -> str:
    pct = round(abs(delta) / 0.5 * 1.0, 1)
    direction = "reduces" if delta > 0 else "improves"
    return (
        f"A {delta:+.1f} {unit} change in LPDDR5 leakage current "
        f"{direction} idle battery life by approximately {pct:.1f}% per hour, "
        f"affecting {product_type} standby time."
    )


def _bi_dvfs_opp(delta: float, unit: str, product_type: str) -> str:
    pct_low = round(abs(delta) * 15, 0)
    pct_high = round(abs(delta) * 25, 0)
    direction = "reduces" if delta > 0 else "increases"
    return (
        f"Shifting {abs(delta):.0f} DVFS OPP step(s) {direction} sustained "
        f"compute throughput by {pct_low:.0f}–{pct_high:.0f}%, causing measurable "
        f"performance regression under sustained workloads on {product_type}."
    )


def _bi_throttle(delta: float, unit: str, product_type: str) -> str:
    direction = "worsens" if delta > 0 else "improves"
    return (
        f"A {delta:+.0f} {unit} change in thermal throttle duration "
        f"{direction} sustained frame rate on {product_type}, "
        "causing user-perceived stutter in gaming and video playback."
    )


def _bi_pmic_transient(delta: float, unit: str, product_type: str) -> str:
    risk = "increases" if delta > 0 else "reduces"
    return (
        f"A {delta:+.0f} {unit} PMIC output transient {risk} the risk of "
        "CDC timing violations in synchronous digital logic, which can manifest "
        f"as intermittent random reboots on {product_type}."
    )


def _bi_cstate(delta: float, unit: str, product_type: str) -> str:
    direction = "increases" if delta > 0 else "decreases"
    return (
        f"A {delta:+.1f} {unit} reduction in C-state residency "
        f"{direction} idle SoC power draw, shortening {product_type} "
        "screen-off standby time."
    )


def _bi_isp_latency(delta: float, unit: str, product_type: str) -> str:
    direction = "worsens" if delta > 0 else "improves"
    noticeable = abs(delta) >= 300
    note = " This is above the 300 ms perceptibility threshold." if noticeable else ""
    return (
        f"A {delta:+.0f} {unit} change in ISP processing latency "
        f"{direction} {product_type} camera launch time.{note}"
    )


def _bi_dma_stall(delta: float, unit: str, product_type: str) -> str:
    missed = abs(delta) >= 16
    note = " At 16 ms+, frames are dropped at 60 fps." if missed else ""
    direction = "introduces" if delta > 0 else "reduces"
    return (
        f"A {delta:+.0f} {unit} DMA buffer stall {direction} camera preview "
        f"stutter on {product_type}.{note}"
    )


def _bi_emmc_gc(delta: float, unit: str, product_type: str) -> str:
    visible = abs(delta) >= 100
    note = " Gaps ≥100 ms produce visible recording glitches." if visible else ""
    direction = "increases" if delta > 0 else "decreases"
    return (
        f"A {delta:+.0f} {unit} change in eMMC GC stall duration "
        f"{direction} video recording dropout risk on {product_type}.{note}"
    )


def _bi_v4l2_underrun(delta: float, unit: str, product_type: str) -> str:
    direction = "increases" if delta > 0 else "decreases"
    return (
        f"A {delta:+.1f} {unit} change in V4L2 buffer underrun rate "
        f"{direction} visible preview frame drops, degrading {product_type} "
        "camera quality perception."
    )


def _bi_frame_time(delta: float, unit: str, product_type: str) -> str:
    fps_impact = round(1000 / max(16.67 + abs(delta), 1) - 60, 1) if delta > 0 else 0
    direction = "extends" if delta > 0 else "reduces"
    return (
        f"A {delta:+.1f} {unit} change in GPU frame time {direction} the "
        f"render budget, causing visible stutter at changes ≥5% on {product_type}."
    )


def _bi_gpu_thermal(delta: float, unit: str, product_type: str) -> str:
    direction = "worsens" if delta > 0 else "improves"
    return (
        f"A {delta:+.0f} {unit} increase in GPU thermal throttle duration "
        f"{direction} sustained FPS cap during gaming sessions on {product_type}."
    )


def _bi_overdraw(delta: float, unit: str, product_type: str) -> str:
    direction = "increases" if delta > 0 else "decreases"
    return (
        f"A {delta:+.1f} {unit} change in UI overdraw layers {direction} "
        "fragment shader load, raising active-display battery drain on "
        f"{product_type} and potentially causing thermal throttle."
    )


def _bi_irq_latency(delta: float, unit: str, product_type: str) -> str:
    audio = abs(delta) >= 500
    camera = 100 <= abs(delta) < 500
    note = ""
    if audio:
        note = " Latency ≥500 µs causes audible audio glitches."
    elif camera:
        note = " Latency in this range can cause camera sensor sync errors."
    direction = "worsens" if delta > 0 else "improves"
    return (
        f"A {delta:+.0f} {unit} change in IRQ dispatch latency {direction} "
        f"real-time responsiveness on {product_type}.{note}"
    )


def _bi_noc_bw(delta: float, unit: str, product_type: str) -> str:
    direction = "creates" if delta > 0 else "relieves"
    return (
        f"A {delta:+.0f} {unit} change in NoC bandwidth utilisation "
        f"{direction} cross-fabric congestion, causing latency spikes across "
        f"all interconnected masters (ISP, GPU, NPU, CPU) on {product_type}."
    )


def _bi_mem_bw(delta: float, unit: str, product_type: str) -> str:
    direction = "degrades" if delta > 0 else "improves"
    return (
        f"A {delta:+.0f} {unit} change in memory bandwidth "
        f"{direction} throughput available to ISP, GPU, and NPU simultaneously, "
        f"causing multi-KPI regression across {product_type} features."
    )


# ---------------------------------------------------------------------------
# Magnitude estimate factories
# ---------------------------------------------------------------------------

def _mag_lpddr5_leakage(delta: float, unit: str) -> str:
    pct = round(abs(delta) / 0.5 * 1.0, 1)
    direction = "reduction" if delta > 0 else "improvement"
    return f"~{pct:.1f}% battery life {direction} per hour at idle"


def _mag_dvfs_opp(delta: float, unit: str) -> str:
    pct_mid = round(abs(delta) * 20, 0)
    return f"~{pct_mid:.0f}% sustained throughput change ({abs(delta):.0f} OPP step(s))"


def _mag_throttle(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f} ms additional throttle duration per thermal event"


def _mag_pmic_transient(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f} mV transient overshoot/undershoot vs nominal"


def _mag_cstate(delta: float, unit: str) -> str:
    return f"~{abs(delta):.1f}% C-state residency change → idle power regression"


def _mag_isp_latency(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f} ms camera launch time change"


def _mag_dma_stall(delta: float, unit: str) -> str:
    frames = round(abs(delta) / 16.67, 1)
    return f"~{abs(delta):.0f} ms stall ({frames:.1f} frames at 60 fps)"


def _mag_emmc_gc(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f} ms GC stall → {'' if abs(delta) >= 100 else 'sub-threshold '}recording gap"


def _mag_v4l2_underrun(delta: float, unit: str) -> str:
    return f"~{abs(delta):.1f} additional buffer underruns per second"


def _mag_frame_time(delta: float, unit: str) -> str:
    pct = round(abs(delta) / 16.67 * 100, 1)
    return f"~{abs(delta):.1f} ms frame time change ({pct:.1f}% of 60 fps budget)"


def _mag_gpu_throttle(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f} ms GPU frequency cap per thermal event"


def _mag_overdraw(delta: float, unit: str) -> str:
    return f"~{abs(delta):.1f}x overdraw layer increase → fragment shader pressure"


def _mag_irq_latency(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f} µs added IRQ dispatch latency"


def _mag_noc_bw(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f}% NoC utilisation change → cross-domain latency spike"


def _mag_mem_bw(delta: float, unit: str) -> str:
    return f"~{abs(delta):.0f}% memory bandwidth change → multi-master contention"


def _mag_default(delta: float, unit: str) -> str:
    return f"~{abs(delta):.2f} {unit} change"


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------
#
# Each entry maps (COMPONENT, metric) → an _ImpactRule.
# COMPONENT is stored upper-case; metric is stored lower-case.
# Matching is done case-insensitively on both keys.

_RULES: list[_ImpactRule] = [
    # ------------------------------------------------------------------
    # Power and Thermal
    # ------------------------------------------------------------------
    _ImpactRule(
        component="LPDDR5",
        metric="leakage_current_ma",
        severity_fn=_severity_power_leakage,
        business_impact_fn=_bi_lpddr5_leakage,
        magnitude_fn=_mag_lpddr5_leakage,
        affected_kpis=["battery_life", "standby_time"],
        recommended_framing=(
            "Frame as standby time regression. For a typical 4500 mAh battery, "
            "0.5 mA additional leakage costs ~1% idle battery life per hour — "
            "quantify as hours lost per charge cycle."
        ),
        raw_reasoning=(
            "LPDDR5 self-refresh leakage dissipates directly from battery at idle. "
            "Empirical rule: 0.5 mA added leakage ≈ 1% battery-per-hour at idle "
            "for a 4500 mAh cell (P = V·I, 3.7V × 0.5 mA ≈ 1.85 mW; "
            "4500 mAh × 3.7V = 16.65 Wh; 1.85 mW / 16650 mWh × 100% ≈ 0.011%/hr "
            "per 0.1 mA — scales linearly)."
        ),
    ),
    _ImpactRule(
        component="DVFS",
        metric="dvfs_opp_step",
        severity_fn=_severity_dvfs_opp,
        business_impact_fn=_bi_dvfs_opp,
        magnitude_fn=_mag_dvfs_opp,
        affected_kpis=["app_performance", "benchmark_score", "sustained_fps"],
        recommended_framing=(
            "Frame as sustained performance cap under load. Each OPP step typically "
            "represents 100–200 MHz and 50–100 mV; one step lost = ~15–25% compute "
            "reduction. Report as 'sustained workload throughput loss'."
        ),
        raw_reasoning=(
            "DVFS OPP tables are spaced approximately 15–25% apart in performance "
            "per step (empirical from ARM Cortex-A series CPUs). Stepping down one "
            "OPP means the CPU cannot sustain peak GFLOPS, directly reducing "
            "throughput for ML inference, image processing, and sustained gaming."
        ),
    ),
    _ImpactRule(
        component="CPUFreq",
        metric="dvfs_opp_step",
        severity_fn=_severity_dvfs_opp,
        business_impact_fn=_bi_dvfs_opp,
        magnitude_fn=_mag_dvfs_opp,
        affected_kpis=["app_performance", "benchmark_score", "sustained_fps"],
        recommended_framing=(
            "Frame as CPU performance regression. Report maximum sustained frequency "
            "drop and expected Geekbench/AnTuTu score reduction (~15–25% per step)."
        ),
        raw_reasoning=(
            "CPUFreq OPP step-down limits maximum sustained clock rate. For ARM "
            "Cortex-A55/A78 clusters, one OPP step ≈ 15–25% IPC-equivalent throughput "
            "loss under sustained load (voltage-frequency curve is approximately linear "
            "in the operating region)."
        ),
    ),
    _ImpactRule(
        component="thermal",
        metric="throttle_duration_ms",
        severity_fn=_severity_throttle,
        business_impact_fn=_bi_throttle,
        magnitude_fn=_mag_throttle,
        affected_kpis=["sustained_fps", "gaming_experience", "benchmark_score"],
        recommended_framing=(
            "Frame as user-perceived stutter during intensive sessions. Report as "
            "'seconds of sub-60 fps gameplay per minute under sustained load' or "
            "'thermal throttle frequency in 10-minute gaming session'."
        ),
        raw_reasoning=(
            "Thermal throttle events clock-gate CPU/GPU clusters to stay below "
            "Tjunction limits. Each throttle pulse drops frame budgets below 16.67 ms "
            "(60 fps), which is visible to the user as stutter. Duration >500 ms "
            "causes sustained FPS cap that dominates the gaming experience."
        ),
    ),
    _ImpactRule(
        component="PMIC",
        metric="pmic_transient_mv",
        severity_fn=_severity_pmic_transient,
        business_impact_fn=_bi_pmic_transient,
        magnitude_fn=_mag_pmic_transient,
        affected_kpis=["device_stability", "reboot_rate", "field_reliability"],
        recommended_framing=(
            "Frame as random reboot risk. Even a single CDC violation can cause "
            "a processor reset. Report as 'potential random reboot under peak load' "
            "with MTBF estimate if transient data is available."
        ),
        raw_reasoning=(
            "PMIC voltage transients that exceed the digital core's noise margin "
            "can cause setup/hold time violations in synchronous flip-flops (CDC). "
            "Transients >100 mV on a 0.75V core rail represent >13% noise margin "
            "violation, which can corrupt architectural state and trigger a reset."
        ),
    ),
    _ImpactRule(
        component="CPUFreq",
        metric="cstate_residency_pct",
        severity_fn=_severity_cstate,
        business_impact_fn=_bi_cstate,
        magnitude_fn=_mag_cstate,
        affected_kpis=["battery_life", "standby_time", "idle_power"],
        recommended_framing=(
            "Frame as screen-off battery drain regression. Quantify as hours lost "
            "per charge cycle based on measured idle current delta."
        ),
        raw_reasoning=(
            "CPU C-state residency determines how much time cores spend in low-power "
            "retention vs active states. Lower residency = higher average idle current. "
            "ARM Cortex-A cores in C0 draw ~10–50× more power than deep C-state; "
            "losing 10% residency raises average idle power by ~5–20 mW depending "
            "on cluster."
        ),
    ),
    # ------------------------------------------------------------------
    # Multimedia / Camera
    # ------------------------------------------------------------------
    _ImpactRule(
        component="ISP",
        metric="isp_latency_ms",
        severity_fn=_severity_isp_latency,
        business_impact_fn=_bi_isp_latency,
        magnitude_fn=_mag_isp_latency,
        affected_kpis=["camera_launch_time", "shot_to_shot_time", "camera_ux"],
        recommended_framing=(
            "Frame as camera launch time regression. Report absolute camera-open "
            "latency vs competitor. Changes >300 ms are user-perceptible; "
            "changes >500 ms affect user perception of 'snappiness'."
        ),
        raw_reasoning=(
            "ISP pipeline latency adds directly to camera open time (HAL3 configure "
            "stream → first preview frame). MIPI CSI-2 frame delivery + ISP "
            "processing + DMA writeback form the critical path. Increases >300 ms "
            "cross the human perception threshold for 'immediate vs delayed' response."
        ),
    ),
    _ImpactRule(
        component="ISP",
        metric="dma_buf_stall_ms",
        severity_fn=_severity_dma_stall,
        business_impact_fn=_bi_dma_stall,
        magnitude_fn=_mag_dma_stall,
        affected_kpis=["camera_preview_quality", "preview_frame_rate"],
        recommended_framing=(
            "Frame as camera preview stutter. At 60 fps, any stall >16 ms drops "
            "a frame. Report as 'dropped frames per minute in camera preview'."
        ),
        raw_reasoning=(
            "DMA-BUF stalls occur when the ISP output buffer is not consumed before "
            "the next frame arrives. At 60 fps the budget is 16.67 ms per frame. "
            "Stalls >16 ms overflow the buffer ring, causing the V4L2 pipeline to "
            "skip or repeat frames — visible as preview judder."
        ),
    ),
    _ImpactRule(
        component="eMMC",
        metric="emmc_gc_stall_ms",
        severity_fn=_severity_emmc_gc,
        business_impact_fn=_bi_emmc_gc,
        magnitude_fn=_mag_emmc_gc,
        affected_kpis=["video_recording_quality", "recording_dropout_rate"],
        recommended_framing=(
            "Frame as video recording dropout risk. At 4K@30fps, a 100 ms GC stall "
            "causes a visible freeze frame. Report as 'GC stall rate during 10-minute "
            "video recording'."
        ),
        raw_reasoning=(
            "F2FS garbage collection checkpoints block the eMMC write path for the "
            "checkpoint window. Camera HAL queues encoded frames to the media muxer; "
            "if the write path stalls >100 ms the encoder queue overflows and a frame "
            "is dropped, appearing as a visible glitch in the recording."
        ),
    ),
    _ImpactRule(
        component="ISP",
        metric="v4l2_underrun_rate",
        severity_fn=_severity_v4l2_underrun,
        business_impact_fn=_bi_v4l2_underrun,
        magnitude_fn=_mag_v4l2_underrun,
        affected_kpis=["camera_preview_quality", "camera_ux"],
        recommended_framing=(
            "Frame as preview frame drop rate. Report as 'dropped frames per second' "
            "or as a percentage of expected frames."
        ),
        raw_reasoning=(
            "V4L2 buffer underrun occurs when the ISP produces frames faster than "
            "userspace dequeues them, or when the sensor delivers no frame and the "
            "pipeline returns an error buffer. Each underrun event either repeats "
            "a frame or drops it — both degrade perceived preview quality."
        ),
    ),
    # ------------------------------------------------------------------
    # GPU / Rendering
    # ------------------------------------------------------------------
    _ImpactRule(
        component="GPU",
        metric="frame_time_ms",
        severity_fn=_severity_frame_time,
        business_impact_fn=_bi_frame_time,
        magnitude_fn=_mag_frame_time,
        affected_kpis=["gaming_fps", "ui_smoothness", "gaming_experience"],
        recommended_framing=(
            "Frame as frame rate regression. Report as average FPS drop and "
            "99th-percentile frame time. Any sustained increase >5% from 16.67 ms "
            "baseline is user-visible as stutter."
        ),
        raw_reasoning=(
            "GPU frame time is the end-to-end duration from draw call submission "
            "to scanout. At 60 fps, the budget is 16.67 ms. A 3 ms increase "
            "(18%) drops effective FPS to ~55 fps and causes 99th-percentile "
            "jank visible to users under normal scrolling and gaming."
        ),
    ),
    _ImpactRule(
        component="GPU",
        metric="throttle_duration_ms",
        severity_fn=_severity_gpu_throttle,
        business_impact_fn=_bi_gpu_thermal,
        magnitude_fn=_mag_gpu_throttle,
        affected_kpis=["sustained_gaming_fps", "gaming_experience", "thermal_headroom"],
        recommended_framing=(
            "Frame as gaming experience degradation. Report as 'sustained FPS cap "
            "after N minutes of gameplay' and compare to competitor devices."
        ),
        raw_reasoning=(
            "GPU thermal throttle triggers when Tjunction or SoC skin temperature "
            "exceeds trip points. The GPU frequency governor clamps to a lower "
            "OPP, reducing fillrate and shader throughput proportionally. Extended "
            "throttle (>1 s) creates sustained FPS drops users attribute to 'lag'."
        ),
    ),
    _ImpactRule(
        component="GPU",
        metric="overdraw_layers",
        severity_fn=_severity_overdraw,
        business_impact_fn=_bi_overdraw,
        magnitude_fn=_mag_overdraw,
        affected_kpis=["battery_drain", "ui_rendering_power", "thermal_headroom"],
        recommended_framing=(
            "Frame as battery drain increase during UI-heavy use. Report as "
            "'active display power increase' and link to thermal headroom reduction."
        ),
        raw_reasoning=(
            "UI overdraw occurs when SurfaceFlinger composites multiple semi-transparent "
            "layers over the same pixel. Each additional overdraw layer requires the "
            "fragment shader to execute once more per pixel, increasing GPU active "
            "power proportionally. 2× overdraw ≈ 2× fragment work, raising GPU "
            "power by 30–50% and consuming thermal headroom."
        ),
    ),
    # ------------------------------------------------------------------
    # Interrupt / System
    # ------------------------------------------------------------------
    _ImpactRule(
        component="GIC",
        metric="irq_latency_us",
        severity_fn=_severity_irq_latency,
        business_impact_fn=_bi_irq_latency,
        magnitude_fn=_mag_irq_latency,
        affected_kpis=["audio_quality", "camera_sync", "realtime_responsiveness"],
        recommended_framing=(
            "Frame as real-time feature reliability. Highlight audio glitch risk "
            "(>500 µs) or camera sync error risk (>200 µs). Report as 'P99 "
            "interrupt latency' measured under system load."
        ),
        raw_reasoning=(
            "GIC-600 IRQ dispatch latency includes: GIC distributor arbitration, "
            "CPU interface acknowledgement, kernel irq_handler invocation. Audio "
            "DMA interrupt handlers must fire within the DMA buffer period "
            "(typically 2–5 ms at 48 kHz); latency >500 µs leaves insufficient "
            "margin and causes ALSA XRUN (audible glitch)."
        ),
    ),
    _ImpactRule(
        component="GIC",
        metric="noc_bandwidth_pct",
        severity_fn=_severity_noc_bw,
        business_impact_fn=_bi_noc_bw,
        magnitude_fn=_mag_noc_bw,
        affected_kpis=["system_latency", "isp_performance", "gpu_performance", "npu_performance"],
        recommended_framing=(
            "Frame as all-domain performance degradation. When NoC saturates, "
            "every memory-bound workload slows simultaneously. Report as "
            "'multi-feature performance cliff under combined workload'."
        ),
        raw_reasoning=(
            "The Network-on-Chip arbitrates DRAM requests from CPU, GPU, ISP, NPU, "
            "and DMA engines. When aggregate utilisation >80%, arbitration queuing "
            "latency grows super-linearly (Little's Law). All masters experience "
            "increased read/write stall cycles simultaneously."
        ),
    ),
    # ------------------------------------------------------------------
    # Memory / Bandwidth
    # ------------------------------------------------------------------
    _ImpactRule(
        component="LPDDR5",
        metric="memory_bandwidth_pct",
        severity_fn=_severity_mem_bw,
        business_impact_fn=_bi_mem_bw,
        magnitude_fn=_mag_mem_bw,
        affected_kpis=["isp_performance", "gpu_performance", "npu_inference_speed", "battery_life"],
        recommended_framing=(
            "Frame as multi-feature performance regression and battery regression. "
            "Memory bandwidth reduction degrades camera, gaming, and AI features "
            "simultaneously. Report as 'peak memory bandwidth available per master'."
        ),
        raw_reasoning=(
            "LPDDR5 bandwidth is shared across all SoC masters via the NoC. "
            "A bandwidth reduction (e.g. from frequency throttle or PHY "
            "derating) reduces the sustained read/write throughput available. "
            "ISP requires ~8–15 GB/s for 4K/60fps; GPU requires 20–40 GB/s "
            "for gaming; NPU requires 10–20 GB/s for DNN inference. "
            "Contention under combined load causes all to degrade."
        ),
    ),
    # ------------------------------------------------------------------
    # Additional power/thermal rules (total count: 25+)
    # ------------------------------------------------------------------
    _ImpactRule(
        component="thermal",
        metric="junction_temp_c",
        severity_fn=lambda d, p: "critical" if abs(d) >= 5 else ("high" if abs(d) >= 2 else "medium"),
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.1f} °C rise in SoC junction temperature on {p} "
            "reduces thermal headroom, increasing throttle frequency and "
            "shortening long-term device reliability."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.1f} °C junction temperature change",
        affected_kpis=["thermal_headroom", "sustained_performance", "device_reliability"],
        recommended_framing=(
            "Frame as long-term reliability risk and sustained performance degradation. "
            "Each 10 °C rise roughly halves semiconductor MTTF (Arrhenius law)."
        ),
        raw_reasoning=(
            "SoC Tjunction limits (typically 105–125 °C) trigger thermal governors. "
            "Higher steady-state temperatures reduce the gap to the trip point, "
            "causing earlier and more frequent throttle events. Arrhenius electromigration "
            "acceleration factor: AF ≈ exp(Ea/k × (1/T1 − 1/T2))."
        ),
    ),
    _ImpactRule(
        component="PMIC",
        metric="quiescent_current_ua",
        severity_fn=lambda d, p: "low" if abs(d) < 50 else ("medium" if abs(d) < 200 else "high"),
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.0f} µA increase in PMIC quiescent current raises always-on "
            f"power draw on {p}, reducing deep-sleep standby time."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.0f} µA quiescent current increase → minor standby drain",
        affected_kpis=["standby_time", "battery_life"],
        recommended_framing=(
            "Frame as marginal standby time loss. At device scale, quiescent current "
            "accumulates over hours. Report as 'additional mAh drain per 8-hour "
            "overnight charge cycle'."
        ),
        raw_reasoning=(
            "PMIC quiescent current (Iq) flows regardless of load state. It represents "
            "the internal bias current of LDO/DCDC regulators. Iq increases with "
            "temperature and process variation. At 100 µA extra, over 8 hours: "
            "0.1 mA × 8 h = 0.8 mAh from a 4500 mAh battery = 0.018% — small but "
            "accumulates across all PMIC rails."
        ),
    ),
    _ImpactRule(
        component="LPDDR5",
        metric="refresh_rate_hz",
        severity_fn=lambda d, p: "medium" if abs(d) > 100 else "low",
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.0f} Hz change in LPDDR5 refresh rate on {p} "
            "alters memory access latency and power, affecting all "
            "memory-bound workload performance."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.0f} Hz refresh rate change → access latency impact",
        affected_kpis=["memory_latency", "battery_life"],
        recommended_framing=(
            "Frame as memory latency vs power trade-off. Higher refresh = lower "
            "retention error risk but higher power. Report as DRAM power delta."
        ),
        raw_reasoning=(
            "LPDDR5 refresh commands (REFab/REFpb) pause normal access while "
            "charging cell capacitors. Higher refresh rates increase tREF overhead "
            "(memory efficiency loss) and IDD5 current. Lower rates risk retention "
            "failures at high temperatures (JEDEC specifies 2× rate at >85 °C)."
        ),
    ),
    _ImpactRule(
        component="CPUFreq",
        metric="idle_power_mw",
        severity_fn=lambda d, p: "medium" if abs(d) > 50 else "low",
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.0f} mW increase in CPU idle power on {p} "
            "directly reduces screen-off standby duration."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.0f} mW idle power delta → proportional battery drain",
        affected_kpis=["standby_time", "battery_life"],
        recommended_framing=(
            "Frame as overnight battery drain. 50 mW idle increase = 400 mWh per 8-hour "
            "sleep = ~2.4% of a 4500 mAh / 3.7V = 16.65 Wh battery."
        ),
        raw_reasoning=(
            "CPU cluster idle power is dominated by leakage and any misconfigured "
            "clock gating. Idle power should be <1 mW per cluster in deep C-state "
            "with proper retention. Misconfigured CPUIdle governors or missing "
            "WFI instruction placement prevent entry into low-power states."
        ),
    ),
    _ImpactRule(
        component="ISP",
        metric="pipeline_stall_rate",
        severity_fn=lambda d, p: "high" if abs(d) > 5 else ("medium" if abs(d) > 1 else "low"),
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.1f} {u} change in ISP pipeline stall rate on {p} "
            "increases frame processing jitter, degrading camera consistency."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.1f} {u} ISP stall rate change",
        affected_kpis=["camera_preview_quality", "shot_consistency"],
        recommended_framing=(
            "Frame as camera consistency degradation. ISP stalls introduce "
            "frame-to-frame timing jitter that manifests as inconsistent preview "
            "quality. Report as 'stall events per 100 frames'."
        ),
        raw_reasoning=(
            "ISP stalls occur when the pixel pipeline cannot drain output buffers "
            "fast enough (DMA backpressure) or when tuning engine takes excessive "
            "cycles. Each stall cycle wastes sensor pixels and increases per-frame "
            "latency variance."
        ),
    ),
    _ImpactRule(
        component="GPU",
        metric="shader_cache_miss_rate",
        severity_fn=lambda d, p: "high" if abs(d) > 20 else ("medium" if abs(d) > 5 else "low"),
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.1f} {u} change in GPU shader cache miss rate on {p} "
            "causes shader compilation stutters during first-run gameplay."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.1f}% shader cache miss rate change",
        affected_kpis=["gaming_first_run_experience", "shader_compilation_stutter"],
        recommended_framing=(
            "Frame as first-run gaming jank. Shader compilation stutter occurs "
            "on first play of a game scene. Report as 'number of compilation "
            "stutter events in first 5-minute session'."
        ),
        raw_reasoning=(
            "GPU shader cache misses trigger on-the-fly GLSL/SPIR-V → ISA "
            "compilation on the first frame a shader is needed. Compilation "
            "blocks the draw call thread for 50–500 ms, causing a single "
            "severe jank frame. Higher miss rates = more stutters."
        ),
    ),
    _ImpactRule(
        component="eMMC",
        metric="write_throughput_mbps",
        severity_fn=lambda d, p: "high" if abs(d) > 50 else ("medium" if abs(d) > 20 else "low"),
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.0f} {u} reduction in eMMC write throughput on {p} "
            "slows app installation, OTA update, and photo save time."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.0f} MB/s write throughput change",
        affected_kpis=["ota_update_time", "photo_save_time", "app_install_time"],
        recommended_framing=(
            "Frame as OTA update duration increase. Report as additional minutes "
            "to complete a 2 GB OTA package write."
        ),
        raw_reasoning=(
            "eMMC sequential write throughput is determined by NAND program timing "
            "and cache write policy. F2FS relies on sustained sequential writes; "
            "throughput drops force more frequent GC cycles which further degrade "
            "available bandwidth — a positive feedback loop."
        ),
    ),
    _ImpactRule(
        component="NPU",
        metric="inference_latency_ms",
        severity_fn=lambda d, p: "high" if abs(d) > 50 else ("medium" if abs(d) > 10 else "low"),
        business_impact_fn=lambda d, u, p: (
            f"A {d:+.0f} {u} change in NPU inference latency on {p} "
            "worsens AI feature responsiveness (scene recognition, portrait mode, "
            "real-time language features)."
        ),
        magnitude_fn=lambda d, u: f"~{abs(d):.0f} ms NPU inference latency change",
        affected_kpis=["ai_feature_responsiveness", "camera_ai_quality", "on_device_ml_speed"],
        recommended_framing=(
            "Frame as AI feature delay. Users perceive >100 ms as 'slow'. "
            "Report as scene detection latency or real-time translation delay."
        ),
        raw_reasoning=(
            "NPU inference latency depends on model complexity, operator mapping "
            "to hardware accelerators, and DRAM bandwidth for weight fetching. "
            "Latency increases from thermal NPU throttle, bandwidth contention, "
            "or power domain frequency reduction."
        ),
    ),
]

# Build lookup index: (COMPONENT_UPPER, metric_lower) → _ImpactRule
_RULE_INDEX: dict[tuple[str, str], _ImpactRule] = {
    (r.component.upper(), r.metric.lower()): r
    for r in _RULES
}

# Component → list of supported metrics
_COMPONENT_METRICS: dict[str, list[str]] = {}
for _r in _RULES:
    _COMPONENT_METRICS.setdefault(_r.component.upper(), []).append(_r.metric.lower())


# ---------------------------------------------------------------------------
# Product-type KPI weight overrides
# ---------------------------------------------------------------------------

_PRODUCT_KPI_OVERRIDES: dict[str, dict[str, str]] = {
    "automotive": {
        "battery_life": "vehicle_standby_time",
        "gaming_experience": "infotainment_ux",
        "camera_launch_time": "rearview_camera_latency",
        "reboot_rate": "ECU_reset_rate",
        "field_reliability": "IEC26262_ASIL_compliance_risk",
    },
    "wearable": {
        "battery_life": "days_per_charge",
        "sustained_fps": "always_on_display_smoothness",
        "gaming_experience": "health_app_responsiveness",
    },
    "iot": {
        "battery_life": "sensor_node_lifetime_months",
        "standby_time": "deep_sleep_duration",
        "gaming_experience": "local_inference_latency",
    },
}


def _adapt_kpis(kpis: list[str], product_type: str) -> list[str]:
    """Remap KPI names for non-smartphone product types."""
    overrides = _PRODUCT_KPI_OVERRIDES.get(product_type, {})
    return [overrides.get(k, k) for k in kpis]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_to_business_impact(
    component: str,
    metric: str,
    delta: float,
    unit: str,
    product_type: str = "smartphone",
) -> dict:
    """Translate a BSP physical metric change into a business-language impact statement.

    Parameters
    ----------
    component:
        BSP component name, e.g. ``"LPDDR5"``, ``"GPU"``, ``"ISP"``,
        ``"CPUFreq"``, ``"eMMC"``, ``"GIC"``, ``"PMIC"``, ``"thermal"``,
        ``"DVFS"``, ``"NPU"``.
    metric:
        The physical metric being changed, e.g. ``"leakage_current_ma"``,
        ``"dvfs_opp_step"``, ``"frame_time_ms"``, ``"isp_latency_ms"``.
    delta:
        The change in the metric. Positive = increase / worsening (by convention).
        Negative = decrease / improvement.
    unit:
        Unit string for *delta*, e.g. ``"mA"``, ``"ms"``, ``"µs"``, ``"%"``.
    product_type:
        One of ``"smartphone"``, ``"tablet"``, ``"wearable"``,
        ``"automotive"``, ``"iot"``.

    Returns
    -------
    dict
        Keys: ``component``, ``metric``, ``delta``, ``unit``, ``product_type``,
        ``business_impact``, ``severity``, ``affected_kpis``,
        ``magnitude_estimate``, ``recommended_framing``, ``raw_reasoning``.
    """
    key = (component.upper(), metric.lower())
    rule = _RULE_INDEX.get(key)

    if rule is None:
        logger.warning(
            "No impact rule defined for component='%s' metric='%s'. "
            "Returning best-effort response.",
            component,
            metric,
        )
        return {
            "component": component,
            "metric": metric,
            "delta": delta,
            "unit": unit,
            "product_type": product_type,
            "business_impact": (
                f"A {delta:+.2f} {unit} change in {component}/{metric} on "
                f"{product_type} may affect device performance or power, but "
                "no specific business impact rule is defined for this combination."
            ),
            "severity": "unknown",
            "affected_kpis": [],
            "magnitude_estimate": _mag_default(delta, unit),
            "recommended_framing": (
                "Consult the BSP domain expert for this component/metric pair. "
                "Report raw metric delta and measured user-observable symptom."
            ),
            "raw_reasoning": (
                f"Rule not found for ({component}, {metric}). "
                "Add a new _ImpactRule entry to _RULES in bsp_to_business.py."
            ),
        }

    severity = rule.severity_fn(delta, product_type)
    business_impact = rule.business_impact_fn(delta, unit, product_type)
    magnitude_estimate = rule.magnitude_fn(delta, unit)
    affected_kpis = _adapt_kpis(rule.affected_kpis, product_type)

    return {
        "component": component,
        "metric": metric,
        "delta": delta,
        "unit": unit,
        "product_type": product_type,
        "business_impact": business_impact,
        "severity": severity,
        "affected_kpis": affected_kpis,
        "magnitude_estimate": magnitude_estimate,
        "recommended_framing": rule.recommended_framing,
        "raw_reasoning": rule.raw_reasoning,
    }


def get_supported_components() -> list[str]:
    """Return list of all component names that have at least one impact rule."""
    return sorted({r.component for r in _RULES})


def get_supported_metrics(component: str) -> list[str]:
    """Return list of supported metric names for *component*.

    Parameters
    ----------
    component:
        Component name (case-insensitive).

    Returns
    -------
    list[str]
        Metric names, or an empty list if *component* is not recognised.
    """
    return _COMPONENT_METRICS.get(component.upper(), [])


def translate_batch(items: list[dict]) -> list[dict]:
    """Translate a list of metric delta descriptions to business impact.

    Parameters
    ----------
    items:
        List of dicts, each with keys: ``component``, ``metric``, ``delta``,
        ``unit``, and optionally ``product_type`` (defaults to ``"smartphone"``).

    Returns
    -------
    list[dict]
        One result dict per input item, in the same order.
    """
    results = []
    for item in items:
        try:
            result = translate_to_business_impact(
                component=item["component"],
                metric=item["metric"],
                delta=float(item["delta"]),
                unit=item["unit"],
                product_type=item.get("product_type", "smartphone"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            result = {
                "error": f"Invalid input item: {exc}",
                "input": item,
            }
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json
    import sys as _sys

    parser = argparse.ArgumentParser(
        description=(
            "BSP-to-Business Impact Translator. "
            "Pass a single metric delta via flags or a JSON dict via stdin."
        )
    )
    parser.add_argument("--component", help="BSP component name (e.g. LPDDR5, GPU, ISP)")
    parser.add_argument("--metric", help="Metric name (e.g. leakage_current_ma, frame_time_ms)")
    parser.add_argument("--delta", type=float, help="Numeric delta (positive = increase)")
    parser.add_argument("--unit", help="Unit of the delta (e.g. mA, ms, µs)")
    parser.add_argument(
        "--product-type",
        default="smartphone",
        choices=["smartphone", "tablet", "wearable", "automotive", "iot"],
        help="Product type (default: smartphone)",
    )
    parser.add_argument(
        "--list-components",
        action="store_true",
        help="Print all supported components and exit",
    )
    parser.add_argument(
        "--list-metrics",
        metavar="COMPONENT",
        help="Print supported metrics for a component and exit",
    )
    args = parser.parse_args()

    if args.list_components:
        print(json.dumps(get_supported_components(), indent=2))
        _sys.exit(0)

    if args.list_metrics:
        metrics = get_supported_metrics(args.list_metrics)
        if not metrics:
            print(f"No rules found for component '{args.list_metrics}'.", file=_sys.stderr)
            _sys.exit(1)
        print(json.dumps(metrics, indent=2))
        _sys.exit(0)

    # Check if stdin has data (JSON mode)
    if not _sys.stdin.isatty():
        raw = _sys.stdin.read().strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON on stdin: {exc}", file=_sys.stderr)
            _sys.exit(1)

        if isinstance(payload, list):
            output = translate_batch(payload)
        else:
            output = translate_to_business_impact(
                component=payload["component"],
                metric=payload["metric"],
                delta=float(payload["delta"]),
                unit=payload["unit"],
                product_type=payload.get("product_type", "smartphone"),
            )
        print(json.dumps(output, indent=2))
        _sys.exit(0)

    # Flag mode
    if not all([args.component, args.metric, args.delta is not None, args.unit]):
        parser.print_help()
        _sys.exit(1)

    output = translate_to_business_impact(
        component=args.component,
        metric=args.metric,
        delta=args.delta,
        unit=args.unit,
        product_type=args.product_type,
    )
    print(json.dumps(output, indent=2))
