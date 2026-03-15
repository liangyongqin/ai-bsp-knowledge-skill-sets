"""
evals/blackboard_eval.py — Blackboard session evaluation harness.

What Blackboard mode is:
    The bsp-knowledge-mentor skill operates in "Blackboard mode" for cross-domain
    problems that span multiple hardware or software domains.  When invoked, the
    mentor acts as an Arbiter: it dispatches sub-agent instances of the relevant
    domain skills (power-thermal-expert, multimedia-camera-expert, etc.), collects
    confidence-scored hypotheses from each, runs iterative convergence rounds, and
    synthesises a structured final report.  This file validates both the structural
    integrity of Blackboard test cases and the correctness of the Arbiter dispatch
    and report validation logic — without requiring a live LLM or MCP server.

Usage:
    # Structural tests (no LLM, no API key required)
    pytest evals/blackboard_eval.py -v

    # Full live session replay (future — Phase 3 integration tests)
    # Requires: ANTHROPIC_API_KEY env var + running MCP server (python mcp/server.py)
    # pytest evals/blackboard_eval.py -v -m live
"""

from __future__ import annotations

import dataclasses
import pytest


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BlackboardCase:
    """A single cross-domain Blackboard evaluation scenario."""

    id: str
    """Unique identifier, e.g. 'xdom_001'."""

    problem_statement: str
    """Cross-domain symptom description presented to the Arbiter."""

    initial_evidence: dict
    """Log snippets, keywords, and context available at session start (NOT a file path)."""

    expected_domains: list[str]
    """Domain skills the Arbiter must activate, e.g. ['power-thermal-expert', 'multimedia-camera-expert']."""

    expected_root_cause_keywords: list[str]
    """Keywords that must appear (case-insensitive) in the final synthesised report."""

    expected_report_sections: list[str]
    """Top-level section names the final Blackboard report must contain."""

    min_domain_coverage: int
    """Minimum number of expected_domains that must contribute a hypothesis."""

    convergence_rounds_max: int
    """Maximum Arbiter rounds before the session is considered unresolved and escalated."""

    tags: list[str]
    """Free-form labels for filtering, e.g. ['cross-domain', 'thermal', 'multimedia']."""


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


BLACKBOARD_CASES: list[BlackboardCase] = [
    BlackboardCase(
        id="xdom_001",
        problem_statement=(
            "Device reboots randomly after approximately 30 minutes of continuous "
            "4K video recording.  The reboot is silent — no kernel panic visible in "
            "dmesg — and occurs only under sustained thermal load."
        ),
        initial_evidence={
            "dmesg_tail": [
                "[1823.441] thermal thermal_zone3: cpu-cluster0 tripped at 98°C",
                "[1823.448] mali d5000000.gpu: devfreq: throttling to 299 MHz",
                "[1823.502] mediatek-isp 1a000000.isp: DMA underrun on port CAM_A",
            ],
            "keywords": ["thermal throttle", "ISP DMA underrun", "silent reboot", "98°C"],
            "soc_context": "MediaTek Dimensity-class SoC, 4K30 recording pipeline active",
        },
        expected_domains=[
            "multimedia-camera-expert",
            "power-thermal-expert",
            "gpu-rendering-expert",
        ],
        expected_root_cause_keywords=[
            "thermal",
            "PMIC",
            "brownout",
            "ISP",
            "power domain",
            "OPP",
        ],
        expected_report_sections=[
            "Root cause",
            "Causal chain",
            "Business impact",
            "Recommended actions",
            "Contributing domains",
        ],
        min_domain_coverage=2,
        convergence_rounds_max=3,
        tags=["cross-domain", "thermal", "multimedia", "gpu", "silent-reboot"],
    ),
    BlackboardCase(
        id="xdom_002",
        problem_statement=(
            "Camera preview frame rate drops from 30 fps to 8–12 fps whenever a "
            "3D game is in the foreground.  Frames are delayed but not dropped at "
            "the V4L2 capture level.  The issue is absent when the display is off."
        ),
        initial_evidence={
            "v4l2_log_excerpt": [
                "v4l2-ctl: frame interval 33 ms -> 120 ms (timestamp delta spike)",
                "v4l2-ctl: buffer queue depth: 8 of 8 filled",
            ],
            "perfetto_counters": {
                "gpu_frequency_mhz": 798,
                "cpu_big_frequency_mhz": 1144,
                "isp_bus_bandwidth_gbps": 0.9,
            },
            "keywords": [
                "camera stutter",
                "GPU contention",
                "ISP bus bandwidth",
                "DVFS interaction",
            ],
            "soc_context": "Shared DRAM bandwidth budget between GPU and ISP",
        },
        expected_domains=[
            "multimedia-camera-expert",
            "gpu-rendering-expert",
            "power-thermal-expert",
        ],
        expected_root_cause_keywords=[
            "DRAM bandwidth",
            "GPU",
            "ISP",
            "DVFS",
            "QoS",
            "interconnect",
        ],
        expected_report_sections=[
            "Root cause",
            "Causal chain",
            "Business impact",
            "Recommended actions",
            "Contributing domains",
        ],
        min_domain_coverage=2,
        convergence_rounds_max=3,
        tags=["cross-domain", "multimedia", "gpu", "bandwidth-contention", "camera-stutter"],
    ),
    BlackboardCase(
        id="xdom_003",
        problem_statement=(
            "System fails to resume from Suspend-to-RAM (STR) when a MIPI CSI-2 "
            "camera stream is active at suspend time.  The resume sequence stalls "
            "after the PMIC regulators are re-enabled but before the display "
            "re-lights.  A second STR attempt with the camera stream stopped "
            "succeeds reliably."
        ),
        initial_evidence={
            "dmesg_resume_sequence": [
                "[suspend] Disabling non-boot CPUs ...",
                "[suspend] platform mipicsi0: suspend_noirq callback timed out (5000 ms)",
                "[resume ] PSCI CPU_ON returned -22 for CPU3",
            ],
            "keywords": [
                "STR resume hang",
                "MIPI CSI-2",
                "suspend_noirq timeout",
                "PSCI CPU_ON",
            ],
            "soc_context": "ARM PSCI-based multi-cluster SoC; camera sensor uses continuous clock mode",
        },
        expected_domains=[
            "power-thermal-expert",
            "multimedia-camera-expert",
            "boot-debug-expert",
        ],
        expected_root_cause_keywords=[
            "STR",
            "PSCI",
            "suspend_noirq",
            "MIPI",
            "regulator",
            "dev_pm_ops",
        ],
        expected_report_sections=[
            "Root cause",
            "Causal chain",
            "Business impact",
            "Recommended actions",
            "Contributing domains",
        ],
        min_domain_coverage=2,
        convergence_rounds_max=4,
        tags=["cross-domain", "STR", "multimedia", "boot-debug", "pm-callback"],
    ),
    BlackboardCase(
        id="xdom_004",
        problem_statement=(
            "An IRQ storm originating from the audio CODEC triggers simultaneously "
            "with a burst of camera DMA completion interrupts.  The combined IRQ "
            "pressure causes audio underruns and camera frame drops within the same "
            "50 ms window."
        ),
        initial_evidence={
            "irq_log_excerpt": [
                "irq 147 (audio-codec): 18420 events/s  [STORM]",
                "irq  83 (isp-dma-cam-a): 4200 events/s",
                "irq  84 (isp-dma-cam-b): 3900 events/s",
            ],
            "dmesg_excerpt": [
                "ALSA: audio underrun on PCM0 — handler latency 2.3 ms",
                "mediatek-isp: frame drop on sensor0 — DMA completion late",
            ],
            "keywords": [
                "IRQ storm",
                "audio underrun",
                "camera frame drop",
                "GIC affinity",
                "CPU isolation",
            ],
            "soc_context": "GIC-600 with ITS; real-time audio thread pinned to CPU2",
        },
        expected_domains=[
            "interrupt-virtualization-expert",
            "multimedia-camera-expert",
        ],
        expected_root_cause_keywords=[
            "IRQ affinity",
            "GIC-600",
            "DMA",
            "CPU isolation",
            "CODEC",
            "latency",
        ],
        expected_report_sections=[
            "Root cause",
            "Causal chain",
            "Business impact",
            "Recommended actions",
            "Contributing domains",
        ],
        min_domain_coverage=2,
        convergence_rounds_max=3,
        tags=["cross-domain", "interrupt", "multimedia", "audio", "irq-storm"],
    ),
    BlackboardCase(
        id="xdom_005",
        problem_statement=(
            "NPU inference throughput degrades from 120 TOPS to 65 TOPS after "
            "approximately 10 minutes of sustained workload.  CPU and GPU frequencies "
            "remain at their requested OPP levels.  Thermal sensors show NPU junction "
            "temperature rising to 95°C."
        ),
        initial_evidence={
            "perf_counters": {
                "npu_utilisation_pct": 98,
                "npu_frequency_mhz": 800,
                "npu_dma_stall_cycles_pct": 34,
                "npu_junction_temp_c": 95,
            },
            "dmesg_excerpt": [
                "npu-thermal: npu0 throttling OPP 800->500 MHz (trip point 95°C)",
                "npu-dma: descriptor fetch stall — AXI bus timeout on master ID 0x1F",
            ],
            "keywords": [
                "NPU throttle",
                "thermal OPP",
                "DMA stall",
                "AXI timeout",
                "throughput degradation",
            ],
            "soc_context": "NPU shares AXI interconnect with ISP and GPU DMA masters",
        },
        expected_domains=[
            "power-thermal-expert",
            "interrupt-virtualization-expert",
        ],
        expected_root_cause_keywords=[
            "thermal throttle",
            "OPP",
            "DMA",
            "AXI",
            "NPU",
            "interconnect",
        ],
        expected_report_sections=[
            "Root cause",
            "Causal chain",
            "Business impact",
            "Recommended actions",
            "Contributing domains",
        ],
        min_domain_coverage=2,
        convergence_rounds_max=3,
        tags=["cross-domain", "thermal", "NPU", "DMA", "throughput-degradation"],
    ),
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

# Canonical mapping from human-readable section labels (as they appear in
# expected_report_sections) to the lowercase dict keys a well-formed Blackboard
# report must expose.
_SECTION_KEY_MAP: dict[str, str] = {
    "Root cause": "root_cause",
    "Causal chain": "causal_chain",
    "Business impact": "business_impact",
    "Recommended actions": "recommended_actions",
    "Contributing domains": "contributing_domains",
}


def validate_blackboard_report(report: dict, case: BlackboardCase) -> dict:
    """Validate a Blackboard final report against the expected structure.

    Checks:
    - Each expected_report_sections entry maps to a present key in *report*.
    - Each expected_root_cause_keywords token appears (case-insensitive) in
      the string representation of the report.
    - The ``contributing_domains`` value covers at least *case.min_domain_coverage*
      of *case.expected_domains*.

    Returns a result dict:
    {
        "case_id": str,
        "sections_present": list[str],   # labels from expected_report_sections that are found
        "sections_missing": list[str],   # labels from expected_report_sections that are absent
        "keywords_matched": list[str],
        "keywords_missing": list[str],
        "domain_coverage": int,          # number of expected_domains present in contributing_domains
        "passed": bool,
        "score": float,                  # 0.0–1.0
    }
    """
    report_text = str(report).lower()

    # Section presence check
    sections_present: list[str] = []
    sections_missing: list[str] = []
    for section_label in case.expected_report_sections:
        key = _SECTION_KEY_MAP.get(section_label, section_label.lower().replace(" ", "_"))
        if key in report:
            sections_present.append(section_label)
        else:
            sections_missing.append(section_label)

    # Keyword match check (case-insensitive substring)
    keywords_matched: list[str] = []
    keywords_missing: list[str] = []
    for kw in case.expected_root_cause_keywords:
        if kw.lower() in report_text:
            keywords_matched.append(kw)
        else:
            keywords_missing.append(kw)

    # Domain coverage check
    contributing: list[str] = report.get("contributing_domains", [])
    if isinstance(contributing, list):
        coverage = sum(1 for d in case.expected_domains if d in contributing)
    else:
        coverage = 0

    # Score: average of three sub-scores
    section_score = len(sections_present) / max(len(case.expected_report_sections), 1)
    keyword_score = len(keywords_matched) / max(len(case.expected_root_cause_keywords), 1)
    coverage_score = min(coverage / max(case.min_domain_coverage, 1), 1.0)
    score = round((section_score + keyword_score + coverage_score) / 3.0, 4)

    passed = (
        not sections_missing
        and not keywords_missing
        and coverage >= case.min_domain_coverage
    )

    return {
        "case_id": case.id,
        "sections_present": sections_present,
        "sections_missing": sections_missing,
        "keywords_matched": keywords_matched,
        "keywords_missing": keywords_missing,
        "domain_coverage": coverage,
        "passed": passed,
        "score": score,
    }


def validate_arbiter_dispatch(dispatched_agents: list[str], case: BlackboardCase) -> dict:
    """Validate that the Arbiter dispatched the correct domain skills.

    Args:
        dispatched_agents: List of skill names the Arbiter actually activated.
        case: The BlackboardCase being evaluated.

    Returns:
    {
        "correct": list[str],    # expected domains that were dispatched
        "missed": list[str],     # expected domains that were NOT dispatched
        "unexpected": list[str], # dispatched agents not in expected_domains
        "coverage_ok": bool,     # True when len(correct) >= case.min_domain_coverage
    }
    """
    dispatched_set = set(dispatched_agents)
    expected_set = set(case.expected_domains)

    correct = [d for d in case.expected_domains if d in dispatched_set]
    missed = [d for d in case.expected_domains if d not in dispatched_set]
    unexpected = [d for d in dispatched_agents if d not in expected_set]
    coverage_ok = len(correct) >= case.min_domain_coverage

    return {
        "correct": correct,
        "missed": missed,
        "unexpected": unexpected,
        "coverage_ok": coverage_ok,
    }


# ---------------------------------------------------------------------------
# Pytest tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", BLACKBOARD_CASES, ids=[c.id for c in BLACKBOARD_CASES])
def test_blackboard_case_structure(case: BlackboardCase) -> None:
    """Validate case definition is well-formed (runs without live LLM)."""
    assert len(case.expected_domains) >= 2, (
        f"{case.id}: expected_domains must list at least 2 skills, got {case.expected_domains}"
    )
    assert len(case.expected_root_cause_keywords) >= 3, (
        f"{case.id}: expected_root_cause_keywords must have >= 3 entries"
    )
    assert len(case.expected_report_sections) >= 3, (
        f"{case.id}: expected_report_sections must have >= 3 sections"
    )
    assert case.min_domain_coverage >= 2, (
        f"{case.id}: min_domain_coverage must be >= 2"
    )
    assert case.convergence_rounds_max <= 5, (
        f"{case.id}: convergence_rounds_max must be <= 5, got {case.convergence_rounds_max}"
    )
    assert case.id, f"Case must have a non-empty id"
    assert case.problem_statement, f"{case.id}: problem_statement must not be empty"
    assert isinstance(case.initial_evidence, dict), (
        f"{case.id}: initial_evidence must be a dict"
    )
    assert isinstance(case.tags, list) and len(case.tags) >= 1, (
        f"{case.id}: tags must be a non-empty list"
    )


@pytest.mark.parametrize("case", BLACKBOARD_CASES, ids=[c.id for c in BLACKBOARD_CASES])
def test_validate_blackboard_report_structure(case: BlackboardCase) -> None:
    """Test that the validator correctly identifies missing sections in a mock report."""
    # Build a mock report that is intentionally incomplete:
    # - has root_cause (one section present)
    # - has only the first contributing domain
    # - missing causal_chain, business_impact, recommended_actions
    mock_report: dict = {
        "root_cause": "mock root cause for structural test",
        "confidence": 0.85,
        "contributing_domains": case.expected_domains[:1],
        # deliberately omitting: causal_chain, business_impact, recommended_actions
    }
    result = validate_blackboard_report(mock_report, case)

    assert result["case_id"] == case.id
    assert isinstance(result["sections_present"], list)
    assert isinstance(result["sections_missing"], list)
    assert isinstance(result["keywords_matched"], list)
    assert isinstance(result["keywords_missing"], list)
    assert isinstance(result["domain_coverage"], int)
    assert isinstance(result["score"], float)
    assert 0.0 <= result["score"] <= 1.0

    # With a minimal mock report the validator must flag failure
    assert result["passed"] is False, (
        f"{case.id}: mock report missing sections — validator should return passed=False"
    )
    assert result["score"] < 1.0, (
        f"{case.id}: incomplete mock report should have score < 1.0, got {result['score']}"
    )
    # At least some sections must be missing
    assert len(result["sections_missing"]) >= 1, (
        f"{case.id}: mock report is missing sections; sections_missing should be non-empty"
    )


@pytest.mark.parametrize("case", BLACKBOARD_CASES, ids=[c.id for c in BLACKBOARD_CASES])
def test_validate_arbiter_dispatch_coverage(case: BlackboardCase) -> None:
    """Test that arbiter dispatch validator catches missed domains."""
    # Only dispatch the first expected domain — coverage must be insufficient
    partial_dispatch = case.expected_domains[:1]
    result = validate_arbiter_dispatch(partial_dispatch, case)

    assert not result["coverage_ok"], (
        f"{case.id}: partial dispatch of {partial_dispatch} should fail coverage check "
        f"(min_domain_coverage={case.min_domain_coverage})"
    )
    assert len(result["missed"]) >= 1, (
        f"{case.id}: at least one expected domain must be in 'missed'"
    )
    assert isinstance(result["correct"], list)
    assert isinstance(result["unexpected"], list)
    # The one dispatched domain should be in 'correct', not in 'unexpected'
    assert partial_dispatch[0] in result["correct"]
    assert partial_dispatch[0] not in result["unexpected"]


@pytest.mark.parametrize("case", BLACKBOARD_CASES, ids=[c.id for c in BLACKBOARD_CASES])
def test_full_blackboard_session_placeholder(case: BlackboardCase) -> None:
    """Full Blackboard session replay — skipped until mentor skill is wired to live API."""
    pytest.skip(
        "Live Blackboard session replay requires MCP server + Claude API — "
        "pending Phase 3 integration test"
    )


# ---------------------------------------------------------------------------
# CLI summary
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    print("Blackboard evaluation cases")
    print("=" * 70)
    for case in BLACKBOARD_CASES:
        print(f"\n[{case.id}] {case.problem_statement[:72]}...")
        print(f"  Expected domains   : {', '.join(case.expected_domains)}")
        print(f"  Min coverage       : {case.min_domain_coverage}/{len(case.expected_domains)}")
        print(f"  Max conv. rounds   : {case.convergence_rounds_max}")
        print(f"  Root cause kw      : {', '.join(case.expected_root_cause_keywords)}")
        print(f"  Report sections    : {', '.join(case.expected_report_sections)}")
        print(f"  Tags               : {', '.join(case.tags)}")
    print("\n" + "=" * 70)
    print(f"Total cases: {len(BLACKBOARD_CASES)}")
    print("\nTo run structural tests (no LLM required):")
    print("  pytest evals/blackboard_eval.py -v")
