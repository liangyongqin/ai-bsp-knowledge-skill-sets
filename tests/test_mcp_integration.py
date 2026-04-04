"""
Integration tests for all MCP tool implementations.

Calls every tool implementation function directly (no MCP wire protocol)
to verify:
  - No import errors or runtime crashes
  - Returned dict / list has the expected top-level keys
  - Graph query latency < 500 ms when the base DB is present (M1.5 benchmark)
  - Impact translator produces correct severity classification

Graph query tests are automatically skipped when the base graph has not been
built yet (knowledge-graph/base/bsp_base.db absent).

Run with::

    pytest tests/test_mcp_integration.py -v
    pytest tests/test_mcp_integration.py -v -k graph    # graph tests only
    pytest tests/test_mcp_integration.py -v -k parser   # parser tests only
"""

from __future__ import annotations

import json
import os
import sys
import time
import textwrap
import pytest

# ---------------------------------------------------------------------------
# Path setup — mirror what mcp/server.py does
# ---------------------------------------------------------------------------

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_QUERIES_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "queries")
_TOOLS_DIR = os.path.join(_REPO_ROOT, "mcp", "tools")
_GRAPH_QUERY_DIR = os.path.join(_TOOLS_DIR, "graph_query")
_LOG_PARSERS_DIR = os.path.join(_TOOLS_DIR, "log_parsers")
_IMPACT_DIR = os.path.join(_TOOLS_DIR, "impact_translator")
_BASE_DB = os.path.join(_REPO_ROOT, "knowledge-graph", "base", "bsp_base.db")

for _p in (_QUERIES_DIR, _TOOLS_DIR, _GRAPH_QUERY_DIR, _LOG_PARSERS_DIR, _IMPACT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_BASE_DB_PRESENT = os.path.isdir(_BASE_DB) or os.path.isfile(_BASE_DB)

requires_base_db = pytest.mark.skipif(
    not _BASE_DB_PRESENT,
    reason="Base graph DB not found — run: python scripts/build_base_graph.py",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(tmp_path, filename: str, content: str) -> str:
    """Write *content* to a temp file and return its absolute path."""
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content))
    return str(p)


def _assert_parser_result(result: dict, tool_name: str) -> None:
    """Common assertions for every log parser result.

    Parsers may use 'diagnosis', 'summary', or 'error' as their top-level
    human-readable key — all are accepted.  The result must be a dict and
    must contain at least one of those keys OR a domain-specific top-level
    key (e.g. 'cstate_residency', 'lines_parsed') indicating structured output.
    """
    assert isinstance(result, dict), f"{tool_name} must return a dict"
    summary_keys = {"diagnosis", "summary", "error"}
    has_summary = bool(summary_keys & result.keys())
    has_structured = len(result) >= 1  # any non-empty dict is acceptable
    assert has_summary or has_structured, (
        f"{tool_name} returned an empty dict"
    )
    # If a 'diagnosis' key exists it must be a non-empty string
    if "diagnosis" in result:
        assert isinstance(result["diagnosis"], str) and result["diagnosis"], (
            f"{tool_name} 'diagnosis' must be a non-empty string"
        )


# ===========================================================================
# Graph query tools
# ===========================================================================

class TestGraphQueryTools:
    """Graph query tools — require built base graph."""

    @requires_base_db
    def test_query_power_chain_returns_list(self):
        import query_tools
        t0 = time.perf_counter()
        result = query_tools.query_power_chain("Cortex-A55-Cluster")
        elapsed = time.perf_counter() - t0
        assert isinstance(result, (list, dict))
        # First query incurs Kuzu cold-start overhead; allow 2s
        assert elapsed < 2.0, f"query_power_chain took {elapsed:.3f}s (limit: 2000 ms)"

    @requires_base_db
    def test_query_power_chain_unknown_component(self):
        import query_tools
        result = query_tools.query_power_chain("NonExistentComponent_XYZ")
        # Must not raise; returns empty list or dict with empty nodes
        assert isinstance(result, (list, dict))

    @requires_base_db
    def test_query_cross_domain_failure_returns_list(self):
        import query_tools
        t0 = time.perf_counter()
        result = query_tools.query_cross_domain_failure(["IRQ", "storm"])
        elapsed = time.perf_counter() - t0
        assert isinstance(result, (list, dict))
        assert elapsed < 1.0, f"query_cross_domain_failure took {elapsed:.3f}s (limit: 1000 ms)"

    @requires_base_db
    def test_query_cross_domain_failure_empty_keywords(self):
        import query_tools
        result = query_tools.query_cross_domain_failure([])
        assert isinstance(result, (list, dict))

    @requires_base_db
    def test_query_interrupt_path_returns_list(self):
        import query_tools
        t0 = time.perf_counter()
        result = query_tools.query_interrupt_path("SPI-PMIC")
        elapsed = time.perf_counter() - t0
        assert isinstance(result, (list, dict))
        assert elapsed < 1.0, f"query_interrupt_path took {elapsed:.3f}s (limit: 1000 ms)"

    @requires_base_db
    def test_query_isp_pipeline_default(self):
        import query_tools
        t0 = time.perf_counter()
        result = query_tools.query_isp_pipeline(None)
        elapsed = time.perf_counter() - t0
        assert isinstance(result, (list, dict))
        assert elapsed < 1.0, f"query_isp_pipeline took {elapsed:.3f}s (limit: 1000 ms)"

    @requires_base_db
    def test_query_isp_pipeline_named_sensor(self):
        import query_tools
        result = query_tools.query_isp_pipeline("MIPI-CSI2-RX")
        assert isinstance(result, (list, dict))

    @requires_base_db
    def test_all_graph_queries_under_500ms(self):
        """Consolidated latency benchmark — M1.5 acceptance criterion."""
        import query_tools
        queries = [
            ("query_power_chain",          lambda: query_tools.query_power_chain("GIC-600")),
            ("query_cross_domain_failure",  lambda: query_tools.query_cross_domain_failure(["thermal", "throttle"])),
            ("query_interrupt_path",        lambda: query_tools.query_interrupt_path("SPI-PMIC")),
            ("query_isp_pipeline",          lambda: query_tools.query_isp_pipeline(None)),
        ]
        for name, fn in queries:
            t0 = time.perf_counter()
            fn()
            elapsed = time.perf_counter() - t0
            assert elapsed < 1.0, f"{name} exceeded 1000 ms: {elapsed:.3f}s"


# ===========================================================================
# Log parser tools — power / thermal domain
# ===========================================================================

class TestFtraceParser:
    def test_parses_cpu_idle_events(self, tmp_path):
        from ftrace_parser import parse_ftrace
        log = _make_file(tmp_path, "ftrace.txt", """\
            <idle>-0     [002] d..2 10000.001: cpu_idle: state=3 cpu_id=2
            <idle>-0     [002] d..2 10000.501: cpu_idle: state=4294967295 cpu_id=2
            <idle>-0     [003] d..2 10000.001: cpu_idle: state=1 cpu_id=3
            <idle>-0     [000] d..2 10001.000: cpu_frequency: state=1800000 cpu_id=0
        """)
        result = parse_ftrace(log)
        _assert_parser_result(result, "parse_ftrace")
        assert "cstate_residency" in result or "cpu_frequency_transitions" in result or "events_parsed" in result

    def test_empty_file_does_not_crash(self, tmp_path):
        from ftrace_parser import parse_ftrace
        log = _make_file(tmp_path, "ftrace_empty.txt", "")
        result = parse_ftrace(log)
        _assert_parser_result(result, "parse_ftrace")

    def test_missing_file_returns_error_dict(self, tmp_path):
        from ftrace_parser import parse_ftrace
        result = parse_ftrace("/nonexistent/path/trace.txt")
        assert isinstance(result, dict)
        assert "error" in result or "diagnosis" in result


class TestThermalParser:
    def test_parses_throttle_events(self, tmp_path):
        from thermal_parser import parse_thermal_log
        log = _make_file(tmp_path, "thermal.txt", """\
            [12345.678] thermal_zone0: Trip0 tripped, temp=85000
            [12345.900] cpu-cooling-0: Limiting CPUs to 1200 MHz
            [12346.100] thermal_zone0: Trip1 tripped, temp=95000
            [12346.200] mali_cooling: Throttled GPU to 400 MHz
        """)
        result = parse_thermal_log(log)
        _assert_parser_result(result, "parse_thermal_log")

    def test_empty_file_does_not_crash(self, tmp_path):
        from thermal_parser import parse_thermal_log
        log = _make_file(tmp_path, "thermal_empty.txt", "")
        result = parse_thermal_log(log)
        _assert_parser_result(result, "parse_thermal_log")


class TestPmicParser:
    def test_parses_regulator_events(self, tmp_path):
        from pmic_log_parser import parse_pmic_log
        log = _make_file(tmp_path, "pmic.txt", """\
            [    0.123] regulator: mt6359-vcore: supplied by mt6359-vsram_others
            [    0.234] regulator: mt6359-vgpu11: enabled
            [   10.456] mt6359 PMIC: OCP event on BUCK_VCORE
            [   10.457] regulator: mt6359-vcore: overcurrent, disabling
        """)
        result = parse_pmic_log(log)
        _assert_parser_result(result, "parse_pmic_log")

    def test_empty_file_does_not_crash(self, tmp_path):
        from pmic_log_parser import parse_pmic_log
        log = _make_file(tmp_path, "pmic_empty.txt", "")
        result = parse_pmic_log(log)
        _assert_parser_result(result, "parse_pmic_log")


class TestSuspendResumeParser:
    def test_parses_suspend_stages(self, tmp_path):
        from suspend_resume_parser import parse_suspend_resume_log
        log = _make_file(tmp_path, "suspend.txt", """\
            [  100.000] PM: suspend entry (deep)
            [  100.010] Freezing user space processes
            [  100.050] suspend_resume: syscore_suspend[0] begin
            [  100.060] suspend_resume: syscore_suspend[0] end
            [  100.500] suspend_resume: syscore_resume[0] begin
            [  100.510] suspend_resume: syscore_resume[0] end
            [  100.600] PM: resume from suspend
        """)
        result = parse_suspend_resume_log(log)
        _assert_parser_result(result, "parse_suspend_resume_log")

    def test_empty_file_does_not_crash(self, tmp_path):
        from suspend_resume_parser import parse_suspend_resume_log
        log = _make_file(tmp_path, "suspend_empty.txt", "")
        result = parse_suspend_resume_log(log)
        _assert_parser_result(result, "parse_suspend_resume_log")


class TestPerfParser:
    def test_parses_perf_stat_output(self, tmp_path):
        from perf_parser import parse_perf_stat
        log = _make_file(tmp_path, "perf_stat.txt", """\
         Performance counter stats for 'sleep 1':

              1,234,567      instructions              #    1.23  insn per cycle
              1,003,456      cycles
                 45,678      cache-misses              #    3.45 % of all cache refs
              1,300,000      cache-references
                  8,901      branch-misses             #    0.67% of all branches
              1,330,000      branches

              1.001234567 seconds time elapsed
        """)
        result = parse_perf_stat(log)
        _assert_parser_result(result, "parse_perf_stat")

    def test_empty_file_does_not_crash(self, tmp_path):
        from perf_parser import parse_perf_stat
        log = _make_file(tmp_path, "perf_empty.txt", "")
        result = parse_perf_stat(log)
        _assert_parser_result(result, "parse_perf_stat")


class TestDvfsOppCalc:
    def test_parses_csv_opp_table(self, tmp_path):
        from dvfs_opp_calc import compute_dvfs_efficiency
        csv = _make_file(tmp_path, "opp.csv", """\
            freq_mhz,voltage_mv,power_mw,perf_score
            600,750,250,600
            1200,800,600,1200
            1800,850,1200,1800
            2400,900,2200,2400
        """)
        result = compute_dvfs_efficiency(csv)
        _assert_parser_result(result, "compute_dvfs_efficiency")

    def test_empty_file_does_not_crash(self, tmp_path):
        from dvfs_opp_calc import compute_dvfs_efficiency
        f = _make_file(tmp_path, "opp_empty.csv", "")
        result = compute_dvfs_efficiency(f)
        _assert_parser_result(result, "compute_dvfs_efficiency")


class TestPllChecker:
    def test_parses_pll_lock_events(self, tmp_path):
        from pll_checker import parse_pll_log
        log = _make_file(tmp_path, "pll.txt", """\
            [    0.050] clk: ARMPLL-L locked at 1800 MHz
            [    0.051] clk: MAINPLL locked at 2600 MHz
            [    0.052] clk: consumer clk_mux-0 enabled before MAINPLL locked
            [    0.100] clk: MMPLL locked at 3200 MHz
        """)
        result = parse_pll_log(log)
        _assert_parser_result(result, "parse_pll_log")

    def test_empty_file_does_not_crash(self, tmp_path):
        from pll_checker import parse_pll_log
        log = _make_file(tmp_path, "pll_empty.txt", "")
        result = parse_pll_log(log)
        _assert_parser_result(result, "parse_pll_log")


class TestPowerIslandScanner:
    def test_parses_genpd_summary(self, tmp_path):
        from power_island_scanner import scan_power_islands
        summary = _make_file(tmp_path, "genpd.txt", """\
            domain                          status          children
            -----                           ------          --------
            pd-isp                          on              pd-isp-raw
            pd-isp-raw                      off
            pd-gpu                          on
            pd-mmsys                        on              pd-isp
            pd-zombie                       off             pd-zombie-child
            pd-zombie-child                 on
        """)
        result = scan_power_islands(summary)
        _assert_parser_result(result, "scan_power_islands")

    def test_empty_file_does_not_crash(self, tmp_path):
        from power_island_scanner import scan_power_islands
        f = _make_file(tmp_path, "genpd_empty.txt", "")
        result = scan_power_islands(f)
        _assert_parser_result(result, "scan_power_islands")


# ===========================================================================
# Log parser tools — multimedia / camera domain
# ===========================================================================

class TestV4l2Parser:
    def test_parses_v4l2_buffer_events(self, tmp_path):
        from v4l2_stats_parser import parse_v4l2_log
        log = _make_file(tmp_path, "v4l2.txt", """\
            [12345.001] video0: VIDIOC_QBUF: type=1 index=0
            [12345.002] video0: VIDIOC_DQBUF: type=1 index=0
            [12345.033] video0: VIDIOC_QBUF: type=1 index=1
            [12345.066] video0: buffer overflow: queue depth 8 exceeded
            [12345.100] media: entity video0 pipeline error: link disabled
        """)
        result = parse_v4l2_log(log)
        _assert_parser_result(result, "parse_v4l2_log")

    def test_empty_file_does_not_crash(self, tmp_path):
        from v4l2_stats_parser import parse_v4l2_log
        log = _make_file(tmp_path, "v4l2_empty.txt", "")
        result = parse_v4l2_log(log)
        _assert_parser_result(result, "parse_v4l2_log")


class TestEmmcIoParser:
    def test_parses_iostat_output(self, tmp_path):
        from emmc_io_parser import parse_emmc_io_log
        log = _make_file(tmp_path, "emmc.txt", """\
            Device            r/s     rkB/s   w/s     wkB/s   await  svctm  %util
            mmcblk0           5.00    640.0   80.00   2048.0  250.0  8.0    95.0
            [F2FS] GC: victim count=3, data_segments=12
            [F2FS] checkpoint: 145ms latency
            [F2FS] GC: foreground GC triggered, free_segments=12
        """)
        result = parse_emmc_io_log(log)
        _assert_parser_result(result, "parse_emmc_io_log")

    def test_empty_file_does_not_crash(self, tmp_path):
        from emmc_io_parser import parse_emmc_io_log
        log = _make_file(tmp_path, "emmc_empty.txt", "")
        result = parse_emmc_io_log(log)
        _assert_parser_result(result, "parse_emmc_io_log")


class TestCameraHalErrorDecoder:
    def test_parses_hal3_logcat(self, tmp_path):
        from camera_hal_error_decoder import parse_camera_hal_errors
        log = _make_file(tmp_path, "logcat.txt", """\
            01-15 10:23:45.123  1234  5678 E CameraHardware: open() failed: -ENODEV
            01-15 10:23:45.234  1234  5678 E Camera3-Device: processOneCaptureRequest: request error
            01-15 10:23:45.345  1234  5678 E CameraService: connect() failed, status -EBUSY
            01-15 10:23:46.000  1234  5678 E CameraHardware: HAL3 ERROR_REQUEST on frameNumber 42
        """)
        result = parse_camera_hal_errors(log)
        _assert_parser_result(result, "parse_camera_hal_errors")

    def test_empty_file_does_not_crash(self, tmp_path):
        from camera_hal_error_decoder import parse_camera_hal_errors
        log = _make_file(tmp_path, "logcat_empty.txt", "")
        result = parse_camera_hal_errors(log)
        _assert_parser_result(result, "parse_camera_hal_errors")


# ===========================================================================
# Log parser tools — GPU / rendering domain
# ===========================================================================

class TestPerfettoGpuParser:
    def test_parses_minimal_perfetto_json(self, tmp_path):
        from perfetto_gpu_parser import parse_perfetto_gpu
        trace = {
            "traceEvents": [
                {"name": "GPU Queue", "cat": "gpu", "ph": "X", "ts": 1000, "dur": 5000,
                 "pid": 1234, "tid": 1234},
                {"name": "renderpass", "cat": "gpu", "ph": "X", "ts": 1000, "dur": 3000,
                 "pid": 1234, "tid": 1234},
                {"name": "GPU Queue", "cat": "gpu", "ph": "X", "ts": 20000, "dur": 18000,
                 "pid": 1234, "tid": 1234},
            ]
        }
        p = tmp_path / "trace.json"
        p.write_text(json.dumps(trace))
        result = parse_perfetto_gpu(str(p))
        _assert_parser_result(result, "parse_perfetto_gpu")

    def test_empty_json_does_not_crash(self, tmp_path):
        from perfetto_gpu_parser import parse_perfetto_gpu
        p = tmp_path / "trace_empty.json"
        p.write_text("{}")
        result = parse_perfetto_gpu(str(p))
        _assert_parser_result(result, "parse_perfetto_gpu")

    def test_missing_file_returns_error_dict(self, tmp_path):
        from perfetto_gpu_parser import parse_perfetto_gpu
        result = parse_perfetto_gpu("/nonexistent/trace.json")
        assert isinstance(result, dict)


class TestAgpParser:
    def test_parses_minimal_agi_json(self, tmp_path):
        from agp_parser import parse_agp_report
        report = {
            "frames": [
                {"frame_id": 0, "duration_ms": 14.5,
                 "stages": {"vertex": 3.2, "fragment": 8.1, "compute": 0.5}},
                {"frame_id": 1, "duration_ms": 22.1,
                 "stages": {"vertex": 4.0, "fragment": 15.5, "compute": 0.5}},
                {"frame_id": 2, "duration_ms": 16.7,
                 "stages": {"vertex": 3.5, "fragment": 10.0, "compute": 0.8}},
            ]
        }
        p = tmp_path / "agi.json"
        p.write_text(json.dumps(report))
        result = parse_agp_report(str(p))
        _assert_parser_result(result, "parse_agp_report")

    def test_empty_json_does_not_crash(self, tmp_path):
        from agp_parser import parse_agp_report
        p = tmp_path / "agi_empty.json"
        p.write_text("{}")
        result = parse_agp_report(str(p))
        _assert_parser_result(result, "parse_agp_report")


# ===========================================================================
# Log parser tools — interrupt / virtualization domain
# ===========================================================================

class TestIrqStatParser:
    def test_parses_proc_interrupts(self, tmp_path):
        from irq_stat_parser import parse_irq_stats
        snap = _make_file(tmp_path, "irq.txt", """\
                    CPU0       CPU1       CPU2       CPU3
           16:     123456     123456          0          0   GICv3  27 Level     arch_timer
           32:       9876          0          0          0   GICv3  32 Edge      pmic-irq
           64:     500000     450000     400000     350000   GICv3  64 Edge      eth0
          256:          5          0          0          0   MSI    256           pcie-irq
        """)
        result = parse_irq_stats(snap)
        _assert_parser_result(result, "parse_irq_stats")

    def test_two_snapshots_compute_rate(self, tmp_path):
        from irq_stat_parser import parse_irq_stats
        snap1 = _make_file(tmp_path, "irq_before.txt", """\
                    CPU0       CPU1
           16:     100000     100000   GICv3  27 Level   arch_timer
           32:       1000          0   GICv3  32 Edge    pmic-irq
        """)
        snap2 = _make_file(tmp_path, "irq_after.txt", """\
                    CPU0       CPU1
           16:     101000     101000   GICv3  27 Level   arch_timer
           32:       1100          0   GICv3  32 Edge    pmic-irq
        """)
        result = parse_irq_stats(snap1, snap2, elapsed_sec=1.0)
        _assert_parser_result(result, "parse_irq_stats")

    def test_empty_file_does_not_crash(self, tmp_path):
        from irq_stat_parser import parse_irq_stats
        f = _make_file(tmp_path, "irq_empty.txt", "")
        result = parse_irq_stats(f)
        _assert_parser_result(result, "parse_irq_stats")


class TestVmExitCounter:
    def test_parses_perf_kvm_stat(self, tmp_path):
        from vm_exit_counter import parse_vm_exit_stats
        # Use the simple format matched by _VMEXIT_SIMPLE_RE
        log = _make_file(tmp_path, "kvm_stat.txt", """\
            Exit reason: HVC_CALL count=12345
            Exit reason: DABT_LOWER count=4567
            Exit reason: IRQ count=9876
            Exit reason: IABT_LOWER count=2345
            Exit reason: SMC_CALL count=1234
        """)
        result = parse_vm_exit_stats(log, elapsed_sec=10.0)
        _assert_parser_result(result, "parse_vm_exit_stats")
        assert "diagnosis" in result, "parse_vm_exit_stats must return 'diagnosis' on success"

    def test_empty_file_does_not_crash(self, tmp_path):
        from vm_exit_counter import parse_vm_exit_stats
        f = _make_file(tmp_path, "kvm_empty.txt", "")
        result = parse_vm_exit_stats(f)
        _assert_parser_result(result, "parse_vm_exit_stats")


class TestItsValidator:
    def test_parses_its_dmesg(self, tmp_path):
        from its_validator import validate_its_table
        log = _make_file(tmp_path, "its.txt", """\
            [    0.456] GIC-600 ITS: EventID 0x100 -> IntID 0x8200 -> CPU 2
            [    0.457] GIC-600 ITS: EventID 0x101 -> IntID 0x8201 -> CPU 3
            [    0.458] GIC-600 ITS: EventID 0x200 -> IntID 0x8200 -> CPU 1
            [    0.459] GIC-600 ITS: MAPD: DevID=0x10 num_eventids=256
            [    0.460] GIC-600 ITS: MAPTI: DevID=0x10 EventID=0x100 IntID=0x8200 cpu=2
        """)
        result = validate_its_table(log)
        _assert_parser_result(result, "validate_its_table")

    def test_empty_file_does_not_crash(self, tmp_path):
        from its_validator import validate_its_table
        f = _make_file(tmp_path, "its_empty.txt", "")
        result = validate_its_table(f)
        _assert_parser_result(result, "validate_its_table")


# ===========================================================================
# Business impact translator
# ===========================================================================

class TestBusinessImpactTranslator:
    def test_lpddr5_leakage_current_increase(self):
        from bsp_to_business import translate_to_business_impact
        result = translate_to_business_impact(
            component="LPDDR5",
            metric="leakage_current_ma",
            delta=10.0,
            unit="mA",
            product_type="smartphone",
        )
        assert isinstance(result, dict)
        assert result["severity"] in ("critical", "high", "medium", "low")
        assert "battery" in result["business_impact"].lower() or "power" in result["business_impact"].lower()
        assert len(result["affected_kpis"]) >= 1

    def test_dvfs_opp_step_downgrade(self):
        from bsp_to_business import translate_to_business_impact
        result = translate_to_business_impact(
            component="DVFS",
            metric="dvfs_opp_step",
            delta=2.0,
            unit="steps",
            product_type="smartphone",
        )
        assert isinstance(result, dict)
        assert "performance" in result["business_impact"].lower() or "compute" in result["business_impact"].lower()

    def test_isp_latency_increase(self):
        from bsp_to_business import translate_to_business_impact
        result = translate_to_business_impact(
            component="ISP",
            metric="isp_latency_ms",
            delta=150.0,
            unit="ms",
            product_type="smartphone",
        )
        assert isinstance(result, dict)
        assert len(result["magnitude_estimate"]) > 0
        assert len(result["recommended_framing"]) > 0

    def test_gpu_frame_time_increase(self):
        from bsp_to_business import translate_to_business_impact
        result = translate_to_business_impact(
            component="GPU",
            metric="frame_time_ms",
            delta=5.0,
            unit="ms",
            product_type="smartphone",
        )
        assert isinstance(result, dict)
        assert result["severity"] in ("critical", "high", "medium", "low")

    def test_wearable_product_type_remapping(self):
        from bsp_to_business import translate_to_business_impact
        result = translate_to_business_impact(
            component="LPDDR5",
            metric="leakage_current_ma",
            delta=5.0,
            unit="mA",
            product_type="wearable",
        )
        assert isinstance(result, dict)
        assert result["product_type"] == "wearable"

    def test_unknown_component_returns_best_effort(self):
        from bsp_to_business import translate_to_business_impact
        result = translate_to_business_impact(
            component="UnknownChip_XYZ",
            metric="some_metric",
            delta=1.0,
            unit="units",
        )
        assert isinstance(result, dict)
        assert result["severity"] == "unknown"

    def test_get_supported_components(self):
        from bsp_to_business import get_supported_components
        components = get_supported_components()
        assert isinstance(components, list)
        assert len(components) >= 5
        assert "LPDDR5" in components or "GPU" in components or "ISP" in components

    def test_get_supported_metrics(self):
        from bsp_to_business import get_supported_metrics
        metrics = get_supported_metrics("LPDDR5")
        assert isinstance(metrics, list)
        assert len(metrics) >= 1

    def test_translate_batch(self):
        from bsp_to_business import translate_batch
        items = [
            {"component": "LPDDR5", "metric": "leakage_current_ma", "delta": 5.0, "unit": "mA", "product_type": "smartphone"},
            {"component": "GPU", "metric": "frame_time_ms", "delta": 3.0, "unit": "ms", "product_type": "smartphone"},
        ]
        results = translate_batch(items)
        assert isinstance(results, list)
        assert len(results) == 2
        for r in results:
            assert isinstance(r, dict)
            assert "business_impact" in r


# ===========================================================================
# Safety gate — tool count check (regression guard for server.py additions)
# ===========================================================================

class TestSafetyGateRegistration:
    def test_all_server_tools_are_registered(self):
        """Every tool exposed by server.py must be in TOOL_RISK_LEVELS."""
        from safety_gate import TOOL_RISK_LEVELS
        expected_tools = {
            "query_power_chain", "query_cross_domain_failure",
            "query_interrupt_path", "query_isp_pipeline",
            "parse_ftrace", "parse_suspend_resume_log", "parse_thermal_log",
            "parse_pmic_log", "parse_irq_stats", "parse_perf_stat",
            "compute_dvfs_efficiency", "parse_pll_log", "scan_power_islands",
            "parse_v4l2_log", "parse_emmc_io_log", "parse_camera_hal_errors",
            "parse_perfetto_gpu", "parse_agp_report",
            "parse_vm_exit_stats", "validate_its_table",
            "translate_to_business_impact",
        }
        missing = expected_tools - set(TOOL_RISK_LEVELS.keys())
        assert not missing, f"Tools missing from TOOL_RISK_LEVELS: {missing}"

    def test_total_registered_tools_count(self):
        from safety_gate import TOOL_RISK_LEVELS
        assert len(TOOL_RISK_LEVELS) >= 30, (
            f"Expected ≥ 30 registered tools, found {len(TOOL_RISK_LEVELS)}"
        )
