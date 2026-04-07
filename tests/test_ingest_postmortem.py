"""
Tests for the post-mortem report ingestion CLI (scripts/ingest_postmortem.py).

Covers: markdown parsing, JSON parsing, validation, dry-run, graph writing,
incremental idempotency, and edge cases.
"""

import json
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "schema")
_BASE_DIR = os.path.join(_REPO_ROOT, "knowledge-graph", "base")

sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, _SCHEMA_DIR)
sys.path.insert(0, _BASE_DIR)

from ingest_postmortem import (
    PostMortemEntry,
    parse_markdown,
    parse_json,
    parse_file,
    detect_format,
    validate_entries,
    write_to_graph,
    _generate_name,
    VALID_DOMAINS,
    VALID_SEVERITIES,
)


# ===========================================================================
# PostMortemEntry validation tests
# ===========================================================================

class TestPostMortemEntry:
    """Tests for PostMortemEntry dataclass validation."""

    def test_valid_entry(self):
        entry = PostMortemEntry(
            name="FM-TEST-001",
            symptom="System reboots after 30 min video recording",
            root_cause="DMA buffer exhaustion due to ISP overrun",
            affected_domain="multimedia",
            source="postmortem-2026-001",
            severity="high",
            affected_components=["ISP", "DMA-Controller"],
        )
        assert entry.validate() == []

    def test_empty_name(self):
        entry = PostMortemEntry(
            name="", symptom="x", root_cause="y",
            affected_domain="power", source="test",
        )
        errors = entry.validate()
        assert any("name" in e for e in errors)

    def test_empty_symptom(self):
        entry = PostMortemEntry(
            name="FM-X", symptom="", root_cause="y",
            affected_domain="power", source="test",
        )
        errors = entry.validate()
        assert any("symptom" in e for e in errors)

    def test_empty_root_cause(self):
        entry = PostMortemEntry(
            name="FM-X", symptom="x", root_cause="",
            affected_domain="power", source="test",
        )
        errors = entry.validate()
        assert any("root_cause" in e for e in errors)

    def test_invalid_domain(self):
        entry = PostMortemEntry(
            name="FM-X", symptom="x", root_cause="y",
            affected_domain="invalid_domain", source="test",
        )
        errors = entry.validate()
        assert any("affected_domain" in e for e in errors)

    def test_invalid_severity(self):
        entry = PostMortemEntry(
            name="FM-X", symptom="x", root_cause="y",
            affected_domain="power", source="test", severity="unknown",
        )
        errors = entry.validate()
        assert any("severity" in e for e in errors)

    def test_empty_source(self):
        entry = PostMortemEntry(
            name="FM-X", symptom="x", root_cause="y",
            affected_domain="power", source="",
        )
        errors = entry.validate()
        assert any("source" in e for e in errors)

    def test_all_valid_domains(self):
        for domain in VALID_DOMAINS:
            entry = PostMortemEntry(
                name="FM-X", symptom="x", root_cause="y",
                affected_domain=domain, source="test",
            )
            assert entry.validate() == [], f"Domain '{domain}' should be valid"

    def test_all_valid_severities(self):
        for sev in VALID_SEVERITIES:
            entry = PostMortemEntry(
                name="FM-X", symptom="x", root_cause="y",
                affected_domain="general", source="test", severity=sev,
            )
            assert entry.validate() == [], f"Severity '{sev}' should be valid"


# ===========================================================================
# Name generation tests
# ===========================================================================

class TestNameGeneration:
    """Tests for deterministic name generation."""

    def test_deterministic(self):
        name1 = _generate_name("system reboots", "report.md")
        name2 = _generate_name("system reboots", "report.md")
        assert name1 == name2

    def test_different_inputs_different_names(self):
        name1 = _generate_name("reboot", "report.md")
        name2 = _generate_name("hang", "report.md")
        assert name1 != name2

    def test_starts_with_prefix(self):
        name = _generate_name("any symptom", "any source")
        assert name.startswith("FM-PM-")

    def test_no_special_chars(self):
        name = _generate_name("CPU @100% & overheating!!!", "src")
        assert all(c.isalnum() or c == "-" for c in name)


# ===========================================================================
# Markdown parser tests
# ===========================================================================

SAMPLE_MARKDOWN = """\
## Post-Mortem: Random reboot during recording

**Symptom:** Device reboots after 30 minutes of 4K video recording
**Root Cause:** ISP DMA buffer pool exhausted due to thermal throttling reducing write bandwidth
**Domain:** multimedia
**Severity:** critical
**Source:** JIRA-BSP-4521
**Components:** ISP, DMA-Controller, PMIC-MT6359
**Resolution:** Increased DMA buffer pool from 8 to 16 buffers and added backpressure signaling

---

## Post-Mortem: Boot hang on cold start

**Symptom:** System hangs during cold boot at PLL lock stage
**Root Cause:** VDD_IO power rail sequencing violation causing PLL reference clock instability
**Domain:** boot
**Severity:** high
**Source:** JIRA-BSP-4530
**Components:** PMIC-MT6359, PLL-ARMPLL
"""


class TestMarkdownParser:
    """Tests for markdown post-mortem parsing."""

    def test_parses_two_entries(self):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        assert len(entries) == 2

    def test_first_entry_fields(self):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        e = entries[0]
        assert "reboots" in e.symptom.lower() or "4K" in e.symptom
        assert "DMA" in e.root_cause
        assert e.affected_domain == "multimedia"
        assert e.severity == "critical"
        assert e.source == "JIRA-BSP-4521"
        assert "ISP" in e.affected_components
        assert "DMA-Controller" in e.affected_components
        assert e.resolution is not None and "backpressure" in e.resolution

    def test_second_entry_fields(self):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        e = entries[1]
        assert "boot" in e.affected_domain
        assert e.severity == "high"
        assert "PLL" in e.root_cause

    def test_auto_generates_name(self):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        for e in entries:
            assert e.name.startswith("FM-PM-")

    def test_empty_input(self):
        entries = parse_markdown("")
        assert entries == []

    def test_missing_required_fields(self):
        md = "## Post-Mortem: Incomplete\n**Symptom:** something\n"
        entries = parse_markdown(md)
        assert entries == []  # no root_cause

    def test_default_source(self):
        md = "**Symptom:** crash\n**Root Cause:** OOM\n"
        entries = parse_markdown(md, default_source="test.md")
        assert len(entries) == 1
        assert entries[0].source == "test.md"

    def test_default_domain_is_general(self):
        md = "**Symptom:** crash\n**Root Cause:** unknown\n**Source:** test\n"
        entries = parse_markdown(md)
        assert len(entries) == 1
        assert entries[0].affected_domain == "general"

    def test_default_severity_is_medium(self):
        md = "**Symptom:** crash\n**Root Cause:** bug\n**Source:** test\n"
        entries = parse_markdown(md)
        assert entries[0].severity == "medium"


# ===========================================================================
# JSON parser tests
# ===========================================================================

SAMPLE_JSON = json.dumps([
    {
        "name": "FM-JSON-001",
        "symptom": "GPU frame drops under sustained load",
        "root_cause": "Thermal throttling reduces GPU clock below 500MHz",
        "affected_domain": "gpu",
        "severity": "high",
        "source": "perf-review-2026-Q1",
        "affected_components": ["Mali-G710", "LVTS-GPU"],
        "resolution": "Adjusted thermal trip point from 85C to 90C with hardware validation",
    },
    {
        "symptom": "IRQ storm on vCPU0",
        "root_cause": "ITS mapping table collision for device groups 3 and 7",
        "affected_domain": "interrupt",
        "source": "debug-session-2026-03-15",
    },
])


class TestJsonParser:
    """Tests for JSON post-mortem parsing."""

    def test_parses_two_entries(self):
        entries = parse_json(SAMPLE_JSON)
        assert len(entries) == 2

    def test_explicit_name_preserved(self):
        entries = parse_json(SAMPLE_JSON)
        assert entries[0].name == "FM-JSON-001"

    def test_auto_generated_name(self):
        entries = parse_json(SAMPLE_JSON)
        assert entries[1].name.startswith("FM-PM-")

    def test_components_as_list(self):
        entries = parse_json(SAMPLE_JSON)
        assert entries[0].affected_components == ["Mali-G710", "LVTS-GPU"]

    def test_components_as_string(self):
        data = json.dumps({"symptom": "x", "root_cause": "y",
                           "affected_domain": "general", "source": "t",
                           "affected_components": "A, B, C"})
        entries = parse_json(data)
        assert entries[0].affected_components == ["A", "B", "C"]

    def test_single_object(self):
        data = json.dumps({"symptom": "x", "root_cause": "y",
                           "affected_domain": "general", "source": "t"})
        entries = parse_json(data)
        assert len(entries) == 1

    def test_empty_array(self):
        entries = parse_json("[]")
        assert entries == []


# ===========================================================================
# Format detection tests
# ===========================================================================

class TestFormatDetection:
    """Tests for file format auto-detection."""

    def test_markdown_md(self):
        assert detect_format("report.md") == "markdown"

    def test_markdown_txt(self):
        assert detect_format("report.txt") == "markdown"

    def test_json(self):
        assert detect_format("cases.json") == "json"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Cannot auto-detect"):
            detect_format("data.csv")


# ===========================================================================
# File parsing integration tests
# ===========================================================================

class TestParseFile:
    """Tests for end-to-end file parsing."""

    def test_parse_markdown_file(self, tmp_path):
        f = tmp_path / "report.md"
        f.write_text(SAMPLE_MARKDOWN)
        entries = parse_file(str(f), "markdown")
        assert len(entries) == 2

    def test_parse_json_file(self, tmp_path):
        f = tmp_path / "cases.json"
        f.write_text(SAMPLE_JSON)
        entries = parse_file(str(f), "json")
        assert len(entries) == 2


# ===========================================================================
# Validation tests
# ===========================================================================

class TestValidation:
    """Tests for entry validation against schema."""

    def test_valid_entries(self):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        results = validate_entries(entries)
        assert all(r["valid"] for r in results)

    def test_invalid_entry(self):
        entry = PostMortemEntry(
            name="", symptom="", root_cause="",
            affected_domain="bad", source="",
        )
        results = validate_entries([entry])
        assert not results[0]["valid"]
        assert len(results[0]["schema_errors"]) >= 4


# ===========================================================================
# Graph writing tests (uses temporary Kuzu DB)
# ===========================================================================

class TestGraphWriting:
    """Tests for writing post-mortem entries to the Kuzu graph."""

    @pytest.fixture
    def tmp_db(self, tmp_path):
        """Create a temporary Kuzu DB with schema."""
        import kuzu
        import schema as _schema

        db_path = str(tmp_path / "test.db")
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        _schema.create_schema(conn)

        # Add a component so CAUSED_BY rels can be tested
        from _ingest_helpers import upsert_node
        upsert_node(conn, "Component", {
            "name": "ISP", "type": "image-signal-processor",
            "description": "test", "namespace": "base",
            "vendor": "test", "version": "1.0",
        })
        upsert_node(conn, "Component", {
            "name": "DMA-Controller", "type": "dma",
            "description": "test", "namespace": "base",
            "vendor": "test", "version": "1.0",
        })
        return db_path

    def test_write_creates_nodes(self, tmp_db):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        stats = write_to_graph(entries, "base", db_path=tmp_db)
        assert stats["nodes_created"] == 2
        assert stats["nodes_skipped"] == 0

    def test_write_creates_relationships(self, tmp_db):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        stats = write_to_graph(entries, "base", db_path=tmp_db)
        # First entry has ISP, DMA-Controller, PMIC-MT6359 (3 components)
        # ISP and DMA-Controller exist, PMIC-MT6359 does not
        assert stats["rels_created"] >= 2

    def test_idempotent_write(self, tmp_db):
        entries = parse_markdown(SAMPLE_MARKDOWN)
        stats1 = write_to_graph(entries, "base", db_path=tmp_db)
        stats2 = write_to_graph(entries, "base", db_path=tmp_db)
        assert stats1["nodes_created"] == 2
        assert stats2["nodes_skipped"] == 2
        assert stats2["nodes_created"] == 0

    def test_json_entries_write(self, tmp_db):
        entries = parse_json(SAMPLE_JSON)
        stats = write_to_graph(entries, "custom", db_path=tmp_db)
        assert stats["nodes_created"] == 2

    def test_empty_entries_noop(self, tmp_db):
        stats = write_to_graph([], "base", db_path=tmp_db)
        assert stats["nodes_created"] == 0
        assert stats["rels_created"] == 0


# ===========================================================================
# CLI help test
# ===========================================================================

class TestCLI:
    """Tests for CLI argument parsing."""

    def test_help_flag(self):
        """Verify the CLI has --help."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(_SCRIPTS_DIR, "ingest_postmortem.py"), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "--validate" in result.stdout
        assert "--namespace" in result.stdout

    def test_dry_run(self, tmp_path):
        """Verify --dry-run exits 0 without writing."""
        f = tmp_path / "report.md"
        f.write_text(SAMPLE_MARKDOWN)
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(_SCRIPTS_DIR, "ingest_postmortem.py"),
             "--input", str(f), "--dry-run"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "Dry-run complete" in result.stdout
