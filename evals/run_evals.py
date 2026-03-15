"""
evals/run_evals.py — BSP Knowledge Skill eval runner.

Usage:
    pytest evals/run_evals.py                  # run all eval cases
    pytest evals/run_evals.py -k power         # run only power-thermal cases
    pytest evals/run_evals.py --skill boot     # run cases for a specific skill prefix
    pytest evals/blackboard_eval.py -v         # run Blackboard structural tests

Each eval case is a JSON file under evals/cases/ with the structure:
    {
        "id": "case_001",
        "skill": "power-thermal-expert",
        "input": "<BSP engineer question or log snippet>",
        "expected_topics": ["<keyword_1>", "<keyword_2>"],
        "min_score": 4
    }

Scoring is performed by checking that each expected_topic appears in the skill
response.  A case passes when the fraction of matched topics meets min_score / 5.
"""

from __future__ import annotations

import json
import pathlib
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--skill",
        action="store",
        default=None,
        help="Filter eval cases by skill name prefix",
    )


@pytest.fixture
def skill_filter(request: pytest.FixtureRequest) -> str | None:
    return request.config.getoption("--skill")

CASES_DIR = pathlib.Path(__file__).parent / "cases"


def _load_cases() -> list[dict]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        with path.open() as fh:
            cases.append(json.load(fh))
    return cases


_ALL_CASES = _load_cases()


@pytest.mark.parametrize("case", _ALL_CASES, ids=[c["id"] for c in _ALL_CASES] if _ALL_CASES else [])
def test_eval_case(case: dict) -> None:
    """Placeholder: each eval case must define id, skill, input, and expected_topics."""
    assert "id" in case, "Case is missing 'id'"
    assert "skill" in case, "Case is missing 'skill'"
    assert "input" in case, "Case is missing 'input'"
    assert "expected_topics" in case, "Case is missing 'expected_topics'"
    assert isinstance(case["expected_topics"], list), "'expected_topics' must be a list"
    # Full scoring logic will be wired once skills and the MCP server are implemented.
    pytest.skip("Skill invocation not yet wired — eval infrastructure placeholder")


@pytest.mark.parametrize("case", _ALL_CASES, ids=[c["id"] for c in _ALL_CASES] if _ALL_CASES else [])
def test_eval_case_schema(case: dict, skill_filter: str | None) -> None:
    """Validate that each case JSON has the required schema fields."""
    if skill_filter and skill_filter not in case.get("skill", ""):
        pytest.skip(f"Filtered out by --skill={skill_filter}")
    required = {"id", "skill", "input", "expected_topics", "min_score"}
    missing = required - set(case.keys())
    assert not missing, f"Case {case.get('id')} missing fields: {missing}"
    assert isinstance(case["expected_topics"], list) and len(case["expected_topics"]) >= 2
    assert 1 <= case["min_score"] <= 5
