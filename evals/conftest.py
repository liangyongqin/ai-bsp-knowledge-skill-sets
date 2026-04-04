"""Shared pytest configuration for the evals/ directory."""

from __future__ import annotations

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
