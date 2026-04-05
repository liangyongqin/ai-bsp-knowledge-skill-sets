#!/usr/bin/env python3
"""
evals/regression_runner.py — Re-run all eval cases and report accuracy drift.

Validates every eval case JSON under evals/cases/ and every Blackboard case in
blackboard_eval.py, saves a timestamped scorecard snapshot to evals/scorecards/,
and optionally compares against a previous snapshot to detect regressions.

Usage::

    # Run all eval cases, save scorecard snapshot
    python3 evals/regression_runner.py

    # Compare against a previous snapshot
    python3 evals/regression_runner.py --baseline evals/scorecards/2026-04-01T12-00-00.json

    # Output as JSON (machine-readable)
    python3 evals/regression_runner.py --json

    # Dry run — validate cases without saving a scorecard
    python3 evals/regression_runner.py --dry-run

    # Also usable via pytest
    pytest evals/regression_runner.py -v

Scorecard format (JSON)::

    {
        "timestamp": "2026-04-06T14:30:00",
        "total_cases": 200,
        "schema_valid": 200,
        "schema_invalid": 0,
        "by_skill": {
            "power-thermal-expert": {"total": 30, "valid": 30, "invalid": 0},
            ...
        },
        "blackboard_cases": 5,
        "blackboard_structural_pass": 5,
        "issues": []
    }
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import pathlib
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = pathlib.Path(__file__).resolve().parent
CASES_DIR = _HERE / "cases"
SCORECARDS_DIR = _HERE / "scorecards"

# ---------------------------------------------------------------------------
# Eval case schema validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"id", "skill", "input", "expected_topics", "min_score"}


def validate_case(case: dict) -> list[str]:
    """Return a list of validation errors for a single eval case dict."""
    errors: list[str] = []
    case_id = case.get("id", "<unknown>")

    missing = REQUIRED_FIELDS - set(case.keys())
    if missing:
        errors.append(f"{case_id}: missing required fields: {missing}")
        return errors

    if not isinstance(case["expected_topics"], list) or len(case["expected_topics"]) < 2:
        errors.append(f"{case_id}: expected_topics must be a list with >= 2 entries")

    if not isinstance(case["min_score"], (int, float)) or not (1 <= case["min_score"] <= 5):
        errors.append(f"{case_id}: min_score must be between 1 and 5")

    if not isinstance(case["input"], str) or len(case["input"].strip()) < 10:
        errors.append(f"{case_id}: input must be a non-trivial string (>= 10 chars)")

    if not isinstance(case["skill"], str) or not case["skill"].strip():
        errors.append(f"{case_id}: skill must be a non-empty string")

    return errors


def load_all_cases() -> list[dict]:
    """Load and return all eval case JSON files from cases/."""
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        with path.open() as fh:
            try:
                cases.append(json.load(fh))
            except json.JSONDecodeError as exc:
                cases.append({"id": path.stem, "_parse_error": str(exc)})
    return cases


# ---------------------------------------------------------------------------
# Blackboard structural validation
# ---------------------------------------------------------------------------

def validate_blackboard_cases() -> dict:
    """Validate Blackboard case definitions structurally.

    Returns:
        {"total": int, "passed": int, "issues": list[str]}
    """
    try:
        from evals.blackboard_eval import BLACKBOARD_CASES
    except ImportError:
        try:
            from blackboard_eval import BLACKBOARD_CASES
        except ImportError:
            return {"total": 0, "passed": 0, "issues": ["Could not import BLACKBOARD_CASES"]}

    total = len(BLACKBOARD_CASES)
    passed = 0
    issues: list[str] = []

    for case in BLACKBOARD_CASES:
        case_issues: list[str] = []
        if len(case.expected_domains) < 2:
            case_issues.append(f"{case.id}: expected_domains < 2")
        if len(case.expected_root_cause_keywords) < 3:
            case_issues.append(f"{case.id}: expected_root_cause_keywords < 3")
        if len(case.expected_report_sections) < 3:
            case_issues.append(f"{case.id}: expected_report_sections < 3")
        if case.min_domain_coverage < 2:
            case_issues.append(f"{case.id}: min_domain_coverage < 2")
        if case.convergence_rounds_max > 5:
            case_issues.append(f"{case.id}: convergence_rounds_max > 5")
        if not case.problem_statement:
            case_issues.append(f"{case.id}: empty problem_statement")
        if not isinstance(case.initial_evidence, dict):
            case_issues.append(f"{case.id}: initial_evidence not a dict")
        if not case.tags:
            case_issues.append(f"{case.id}: empty tags")

        if case_issues:
            issues.extend(case_issues)
        else:
            passed += 1

    return {"total": total, "passed": passed, "issues": issues}


# ---------------------------------------------------------------------------
# Scorecard generation
# ---------------------------------------------------------------------------

def build_scorecard(cases: list[dict], blackboard: dict) -> dict:
    """Build a scorecard dict from validated cases and blackboard results."""
    by_skill: dict[str, dict] = {}
    all_issues: list[str] = []
    schema_valid = 0
    schema_invalid = 0

    for case in cases:
        if "_parse_error" in case:
            all_issues.append(f"{case['id']}: JSON parse error: {case['_parse_error']}")
            schema_invalid += 1
            continue

        errors = validate_case(case)
        skill = case.get("skill", "<unknown>")

        if skill not in by_skill:
            by_skill[skill] = {"total": 0, "valid": 0, "invalid": 0}
        by_skill[skill]["total"] += 1

        if errors:
            schema_invalid += 1
            by_skill[skill]["invalid"] += 1
            all_issues.extend(errors)
        else:
            schema_valid += 1
            by_skill[skill]["valid"] += 1

    all_issues.extend(blackboard.get("issues", []))

    return {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "total_cases": len(cases),
        "schema_valid": schema_valid,
        "schema_invalid": schema_invalid,
        "by_skill": dict(sorted(by_skill.items())),
        "blackboard_cases": blackboard["total"],
        "blackboard_structural_pass": blackboard["passed"],
        "issues": all_issues,
    }


# ---------------------------------------------------------------------------
# Baseline comparison
# ---------------------------------------------------------------------------

def compare_scorecards(current: dict, baseline: dict) -> dict:
    """Compare current scorecard against a baseline and report drift.

    Returns:
        {
            "regressions": list[str],
            "improvements": list[str],
            "unchanged": bool,
            "case_count_delta": int,
            "valid_delta": int,
            "blackboard_delta": int,
        }
    """
    regressions: list[str] = []
    improvements: list[str] = []

    case_delta = current["total_cases"] - baseline["total_cases"]
    valid_delta = current["schema_valid"] - baseline["schema_valid"]
    invalid_delta = current["schema_invalid"] - baseline["schema_invalid"]
    bb_delta = current["blackboard_structural_pass"] - baseline["blackboard_structural_pass"]

    if invalid_delta > 0:
        regressions.append(
            f"Schema-invalid cases increased by {invalid_delta} "
            f"({baseline['schema_invalid']} -> {current['schema_invalid']})"
        )
    elif invalid_delta < 0:
        improvements.append(
            f"Schema-invalid cases decreased by {abs(invalid_delta)} "
            f"({baseline['schema_invalid']} -> {current['schema_invalid']})"
        )

    if bb_delta < 0:
        regressions.append(
            f"Blackboard structural pass decreased by {abs(bb_delta)} "
            f"({baseline['blackboard_structural_pass']} -> {current['blackboard_structural_pass']})"
        )
    elif bb_delta > 0:
        improvements.append(
            f"Blackboard structural pass increased by {bb_delta} "
            f"({baseline['blackboard_structural_pass']} -> {current['blackboard_structural_pass']})"
        )

    # Per-skill comparison
    all_skills = set(current.get("by_skill", {}).keys()) | set(baseline.get("by_skill", {}).keys())
    for skill in sorted(all_skills):
        cur = current.get("by_skill", {}).get(skill, {"valid": 0, "invalid": 0, "total": 0})
        base = baseline.get("by_skill", {}).get(skill, {"valid": 0, "invalid": 0, "total": 0})
        inv_d = cur["invalid"] - base["invalid"]
        if inv_d > 0:
            regressions.append(f"{skill}: invalid cases +{inv_d}")
        elif inv_d < 0:
            improvements.append(f"{skill}: invalid cases {inv_d}")

    return {
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": not regressions and not improvements,
        "case_count_delta": case_delta,
        "valid_delta": valid_delta,
        "blackboard_delta": bb_delta,
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def print_scorecard(sc: dict) -> None:
    """Print a human-readable scorecard summary."""
    print("=" * 64)
    print("  BSP Eval Regression Report")
    print(f"  Timestamp: {sc['timestamp']}")
    print("=" * 64)

    print(f"\n  Eval cases:  {sc['total_cases']}")
    print(f"    Valid:     {sc['schema_valid']}")
    print(f"    Invalid:   {sc['schema_invalid']}")

    print(f"\n  Blackboard cases:          {sc['blackboard_cases']}")
    print(f"    Structural pass:         {sc['blackboard_structural_pass']}")

    print("\n  By skill:")
    print("  " + "-" * 52)
    for skill, counts in sc["by_skill"].items():
        status = "OK" if counts["invalid"] == 0 else f"!!! {counts['invalid']} invalid"
        print(f"    {skill:<38s} {counts['total']:>3d}  {status}")

    if sc["issues"]:
        print(f"\n  Issues ({len(sc['issues'])}):")
        print("  " + "-" * 52)
        for issue in sc["issues"]:
            print(f"    - {issue}")
    else:
        print("\n  No issues found.")

    print("\n" + "=" * 64)


def print_comparison(comp: dict) -> None:
    """Print baseline comparison results."""
    print("\n  Baseline Comparison")
    print("  " + "-" * 52)
    print(f"    Case count delta:      {comp['case_count_delta']:+d}")
    print(f"    Valid cases delta:     {comp['valid_delta']:+d}")
    print(f"    Blackboard delta:      {comp['blackboard_delta']:+d}")

    if comp["regressions"]:
        print(f"\n  REGRESSIONS ({len(comp['regressions'])}):")
        for r in comp["regressions"]:
            print(f"    !! {r}")
    if comp["improvements"]:
        print(f"\n  Improvements ({len(comp['improvements'])}):")
        for i in comp["improvements"]:
            print(f"    ++ {i}")
    if comp["unchanged"]:
        print("\n    No drift detected.")


# ---------------------------------------------------------------------------
# Pytest integration
# ---------------------------------------------------------------------------

import pytest

_ALL_CASES = load_all_cases()


@pytest.mark.parametrize(
    "case", _ALL_CASES,
    ids=[c.get("id", f"unknown_{i}") for i, c in enumerate(_ALL_CASES)] if _ALL_CASES else [],
)
def test_eval_case_schema_regression(case: dict) -> None:
    """Validate that each eval case JSON passes schema validation."""
    assert "_parse_error" not in case, f"JSON parse error: {case.get('_parse_error')}"
    errors = validate_case(case)
    assert not errors, f"Schema validation errors: {errors}"


def test_blackboard_structural_regression() -> None:
    """Validate all Blackboard cases pass structural checks."""
    result = validate_blackboard_cases()
    assert result["total"] > 0, "No Blackboard cases found"
    assert result["passed"] == result["total"], (
        f"{result['total'] - result['passed']} Blackboard cases failed structural checks: "
        f"{result['issues']}"
    )


def test_eval_case_count_minimum() -> None:
    """Ensure we have at least 200 eval cases (no accidental deletion)."""
    assert len(_ALL_CASES) >= 200, (
        f"Expected >= 200 eval cases, found {len(_ALL_CASES)}. "
        "Cases may have been accidentally deleted."
    )


def test_skill_coverage() -> None:
    """Ensure all 7 skills have eval coverage."""
    expected_skills = {
        "power-thermal-expert",
        "boot-debug-expert",
        "multimedia-camera-expert",
        "gpu-rendering-expert",
        "interrupt-virtualization-expert",
        "hardware-spec-extractor",
        "bsp-knowledge-mentor",
    }
    found_skills = {c.get("skill") for c in _ALL_CASES if "skill" in c}
    missing = expected_skills - found_skills
    assert not missing, f"Skills with no eval cases: {missing}"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-run all BSP eval cases and report accuracy drift.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 evals/regression_runner.py\n"
            "  python3 evals/regression_runner.py --baseline evals/scorecards/2026-04-01T12-00-00.json\n"
            "  python3 evals/regression_runner.py --json --dry-run\n"
        ),
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to a previous scorecard JSON to compare against",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output scorecard as JSON instead of human-readable table",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate cases but do not save a scorecard snapshot",
    )
    args = parser.parse_args()

    cases = load_all_cases()
    blackboard = validate_blackboard_cases()
    scorecard = build_scorecard(cases, blackboard)

    # Save scorecard
    if not args.dry_run:
        SCORECARDS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = SCORECARDS_DIR / f"{scorecard['timestamp']}.json"
        with open(out_path, "w") as fh:
            json.dump(scorecard, fh, indent=2)
            fh.write("\n")

    # Baseline comparison
    comparison = None
    if args.baseline:
        baseline_path = pathlib.Path(args.baseline)
        if not baseline_path.exists():
            print(f"Error: baseline file not found: {args.baseline}", file=sys.stderr)
            return 1
        with open(baseline_path) as fh:
            baseline = json.load(fh)
        comparison = compare_scorecards(scorecard, baseline)

    # Output
    if args.json:
        output = {"scorecard": scorecard}
        if comparison:
            output["comparison"] = comparison
        print(json.dumps(output, indent=2))
    else:
        print_scorecard(scorecard)
        if comparison:
            print_comparison(comparison)
        if not args.dry_run:
            print(f"\n  Scorecard saved to: {out_path}")

    # Exit code: non-zero if there are regressions
    if comparison and comparison["regressions"]:
        return 1
    if scorecard["schema_invalid"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
