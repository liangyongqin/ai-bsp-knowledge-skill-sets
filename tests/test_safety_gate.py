"""
Unit tests for mcp/tools/safety_gate.py

Covers all three risk levels (READ_ONLY, CONFIG, DESTRUCTIVE) and the
public API: get_risk_level() and check_approval().

Run with:
    pytest tests/test_safety_gate.py -v
"""

from __future__ import annotations

import sys
import os
import pytest

# ---------------------------------------------------------------------------
# Path setup — make the local mcp/tools package importable
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_REPO_ROOT, "mcp", "tools")
sys.path.insert(0, _TOOLS_DIR)

from safety_gate import (  # noqa: E402
    RiskLevel,
    TOOL_RISK_LEVELS,
    get_risk_level,
    check_approval,
)


# ---------------------------------------------------------------------------
# Tests — RiskLevel enum
# ---------------------------------------------------------------------------

class TestRiskLevelEnum:
    def test_three_levels_exist(self):
        assert RiskLevel.READ_ONLY is not None
        assert RiskLevel.CONFIG is not None
        assert RiskLevel.DESTRUCTIVE is not None

    def test_levels_are_distinct(self):
        assert RiskLevel.READ_ONLY != RiskLevel.CONFIG
        assert RiskLevel.CONFIG != RiskLevel.DESTRUCTIVE
        assert RiskLevel.READ_ONLY != RiskLevel.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Tests — get_risk_level()
# ---------------------------------------------------------------------------

class TestGetRiskLevel:
    # --- READ_ONLY tools ---

    @pytest.mark.parametrize("tool_name", [
        "query_power_chain",
        "query_cross_domain_failure",
        "query_interrupt_path",
        "query_isp_pipeline",
        "parse_ftrace",
        "parse_thermal_log",
        "parse_pmic_log",
        "parse_irq_stats",
        "parse_suspend_resume_log",
        "parse_perf_stat",
        "compute_dvfs_efficiency",
        "parse_pll_log",
        "scan_power_islands",
        "parse_v4l2_log",
        "parse_emmc_io_log",
        "parse_camera_hal_errors",
        "parse_perfetto_gpu",
        "parse_agp_report",
        "parse_vm_exit_stats",
        "validate_its_table",
        "ingest_pdf",
        "parse_ipxact",
        "extract_registers",
        "validate_registers",
        "list_all_interrupts",
        "find_all_power_domains",
        "find_components_powered_by",
        "query_failures_by_domain",
        "query_multimedia_components",
    ])
    def test_read_only_tools(self, tool_name):
        assert get_risk_level(tool_name) == RiskLevel.READ_ONLY

    # --- CONFIG tools ---

    @pytest.mark.parametrize("tool_name", [
        "ingest_custom_pdf",
        "ingest_custom_ipxact",
        "update_custom_graph",
    ])
    def test_config_tools(self, tool_name):
        assert get_risk_level(tool_name) == RiskLevel.CONFIG

    # --- DESTRUCTIVE tools ---

    @pytest.mark.parametrize("tool_name", [
        "flash_firmware",
        "set_register_value",
        "trigger_hardware_reset",
        "run_external_build",
        "modify_dtb",
    ])
    def test_destructive_tools(self, tool_name):
        assert get_risk_level(tool_name) == RiskLevel.DESTRUCTIVE

    def test_unknown_tool_defaults_to_read_only(self):
        """Unknown tools must default to READ_ONLY (safe assumption)."""
        assert get_risk_level("totally_unknown_tool_xyz") == RiskLevel.READ_ONLY

    def test_all_registered_tools_have_valid_level(self):
        """Every entry in TOOL_RISK_LEVELS maps to a valid RiskLevel."""
        for name, level in TOOL_RISK_LEVELS.items():
            assert isinstance(level, RiskLevel), (
                f"Tool '{name}' has invalid risk level: {level!r}"
            )

    def test_registry_not_empty(self):
        assert len(TOOL_RISK_LEVELS) >= 30, (
            f"Expected ≥ 30 registered tools, found {len(TOOL_RISK_LEVELS)}"
        )


# ---------------------------------------------------------------------------
# Tests — check_approval()
# ---------------------------------------------------------------------------

class TestCheckApproval:
    # READ_ONLY — always permitted

    def test_read_only_permitted_without_approval(self):
        assert check_approval("query_power_chain") is True

    def test_read_only_permitted_with_approval(self):
        assert check_approval("query_power_chain", requires_human_approval=True) is True

    def test_read_only_parser_permitted(self):
        assert check_approval("parse_ftrace") is True

    # CONFIG — always permitted

    def test_config_permitted_without_approval(self):
        assert check_approval("ingest_custom_pdf") is True

    def test_config_permitted_with_approval(self):
        assert check_approval("ingest_custom_pdf", requires_human_approval=True) is True

    # DESTRUCTIVE — blocked without approval

    def test_destructive_raises_without_approval(self):
        with pytest.raises(PermissionError) as exc_info:
            check_approval("flash_firmware")
        assert "flash_firmware" in str(exc_info.value)
        assert "DESTRUCTIVE" in str(exc_info.value)

    def test_destructive_raises_without_approval_other_tool(self):
        with pytest.raises(PermissionError):
            check_approval("set_register_value", requires_human_approval=False)

    def test_destructive_permitted_with_approval(self):
        assert check_approval("flash_firmware", requires_human_approval=True) is True

    def test_destructive_permitted_with_approval_all_tools(self):
        for name, level in TOOL_RISK_LEVELS.items():
            if level == RiskLevel.DESTRUCTIVE:
                result = check_approval(name, requires_human_approval=True)
                assert result is True, f"Destructive tool '{name}' should be permitted with approval"

    # Unknown tools (defaults to READ_ONLY)

    def test_unknown_tool_permitted(self):
        """Unknown tools default to READ_ONLY and are therefore permitted."""
        assert check_approval("nonexistent_tool_abc") is True

    # Error message quality

    def test_destructive_error_contains_tool_name(self):
        for tool in ("trigger_hardware_reset", "modify_dtb"):
            with pytest.raises(PermissionError) as exc_info:
                check_approval(tool)
            assert tool in str(exc_info.value)

    def test_destructive_error_mentions_approval(self):
        with pytest.raises(PermissionError) as exc_info:
            check_approval("run_external_build")
        msg = str(exc_info.value).lower()
        assert "approval" in msg or "requires" in msg


# ---------------------------------------------------------------------------
# Tests — TOOL_RISK_LEVELS completeness
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:
    _REQUIRED_READ_ONLY = [
        # Graph query tools
        "query_power_chain",
        "query_cross_domain_failure",
        "query_interrupt_path",
        "query_isp_pipeline",
        # Log parsers (original set from ROADMAP)
        "parse_ftrace",
        "parse_thermal_log",
        "parse_pmic_log",
        "parse_irq_stats",
        "parse_suspend_resume_log",
        # New parsers
        "parse_perf_stat",
        "compute_dvfs_efficiency",
        "parse_pll_log",
        "scan_power_islands",
        "parse_v4l2_log",
        "parse_emmc_io_log",
        "parse_camera_hal_errors",
        "parse_perfetto_gpu",
        "parse_agp_report",
        "parse_vm_exit_stats",
        "validate_its_table",
    ]

    _REQUIRED_CONFIG = [
        "ingest_custom_pdf",
        "ingest_custom_ipxact",
        "update_custom_graph",
    ]

    _REQUIRED_DESTRUCTIVE = [
        "flash_firmware",
        "set_register_value",
        "trigger_hardware_reset",
    ]

    @pytest.mark.parametrize("tool_name", _REQUIRED_READ_ONLY)
    def test_required_read_only_registered(self, tool_name):
        assert tool_name in TOOL_RISK_LEVELS, (
            f"Required READ_ONLY tool '{tool_name}' missing from TOOL_RISK_LEVELS"
        )
        assert TOOL_RISK_LEVELS[tool_name] == RiskLevel.READ_ONLY

    @pytest.mark.parametrize("tool_name", _REQUIRED_CONFIG)
    def test_required_config_registered(self, tool_name):
        assert tool_name in TOOL_RISK_LEVELS, (
            f"Required CONFIG tool '{tool_name}' missing from TOOL_RISK_LEVELS"
        )
        assert TOOL_RISK_LEVELS[tool_name] == RiskLevel.CONFIG

    @pytest.mark.parametrize("tool_name", _REQUIRED_DESTRUCTIVE)
    def test_required_destructive_registered(self, tool_name):
        assert tool_name in TOOL_RISK_LEVELS, (
            f"Required DESTRUCTIVE tool '{tool_name}' missing from TOOL_RISK_LEVELS"
        )
        assert TOOL_RISK_LEVELS[tool_name] == RiskLevel.DESTRUCTIVE

    def test_no_tool_registered_as_none(self):
        for name, level in TOOL_RISK_LEVELS.items():
            assert level is not None, f"Tool '{name}' has None risk level"

    def test_tool_names_are_strings(self):
        for name in TOOL_RISK_LEVELS:
            assert isinstance(name, str), f"Tool name {name!r} is not a string"
            assert len(name) > 0, "Tool name must not be empty"
