# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This repository implements **BSP Knowledge Skill Sets** — Claude Code skills that form a three-layer AI mentor system for SoC BSP (Board Support Package) engineers working on MediaTek or Qualcomm platforms. Read `BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md` for strategic intent and `ROADMAP.md` for milestone-by-milestone implementation plan with current status.

## Current Development Status

**Phases 1 and 2 are complete. Phase 3 is the active work front.**

What exists and works:
- Kuzu knowledge graph schema (`knowledge-graph/schema/schema.py`, `init_db.py`)
- 10 open-source seed scripts (`knowledge-graph/base/`) — **501 nodes** in base graph
- Four GraphRAG query templates (`knowledge-graph/queries/`)
- Document ingestion pipeline (`mcp/tools/spec_extractor/`) including `graph_diff_writer.py`
- MCP server with graph query tools (`mcp/server.py`, `mcp/tools/graph_query/query_tools.py`)
- Tool safety gate (`mcp/tools/safety_gate.py`) — 82 unit tests passing
- 16 log parsers in `mcp/tools/log_parsers/`
- 6 domain `skill.md` files written (one per skill directory)
- 180 eval cases in `evals/cases/` (30 per skill)
- `scripts/build_base_graph.py`, `scripts/ingest_custom.py`, `scripts/install.sh`

What is pending (Phase 2 human-gated, non-blocking for Phase 3):
- Human expert scoring of 180 eval cases (≥ 4/5 per skill)
- MCP integration test end-to-end (≥ 90% tool-calling success rate)

What is missing (Phase 3 primary gap):
- **`skills/bsp-knowledge-mentor/skill.md`** — ITS teaching engine, not yet written
- **`skills/bsp-knowledge-mentor/socratic-templates.yaml`** — Socratic questioning sequences
- **`skills/bsp-knowledge-mentor/term-dictionary.yaml`** — ≥ 100 BSP ↔ business term pairs
- **`mcp/tools/impact_translator/`** — business impact translation engine, not yet written
- **≥ 20 multi-domain eval cases** — for Blackboard pattern testing

## Hard Constraints

- **Zero server dependencies.** Every component installs via `pip`. No Docker, no Neo4j, no Qdrant. Graph DB: Kuzu (embedded). Vector store: ChromaDB (embedded).
- **Open-source knowledge only in `knowledge-graph/base/`.** Sources: ARM public TRMs, AMBA specs, Linux kernel docs. No proprietary SoC register maps in this repo.
- **`knowledge-graph/custom/` is gitignored.** End users populate this with in-house SoC TRMs. Never commit anything from `custom/`.
- **Skills are Claude Code native.** `skill.md` files register to `~/.claude/skills/` (user-level) or `.claude/skills/` (project-level), invoked with `/skill-name`.

## Architecture

```
Layer 3: skills/bsp-knowledge-mentor/   ← ITS teaching engine, Blackboard coordinator (⬜ Phase 3, active)
Layer 2: skills/<domain>-expert/        ← Six domain skills (✅ complete — all skill.md written)
Layer 1: knowledge-graph/ + mcp/        ← Kuzu graph + MCP tool server (✅ complete)
```

Layer 1 must exist before writing Layer 2. Layer 2 must be complete before writing Layer 3.

## Knowledge Graph

### Schema

Defined in `knowledge-graph/schema/schema.py`. Node tables and their primary keys:

| Table | Primary key | Key fields |
|---|---|---|
| `Component` | `name` | `type`, `namespace`, `vendor` |
| `PowerDomain` | `name` | `voltage_mv`, `current_ma`, `namespace` |
| `ClockSource` | `name` | `frequency_hz`, `parent_clk`, `namespace` |
| `Register` | `name` | `address`, `access_type`, `reset_value`, `component`, `namespace` |
| `Interrupt` | `name` | `irq_type`, `irq_id`, `trigger`, `namespace` |
| `FailureMode` | `name` | `symptom`, `root_cause`, `affected_domain`, `source`, `namespace` |

Relationship tables: `SUPPLIES`, `POWERS`, `CLOCKS`, `DEPENDS_ON_CLOCK`, `TRIGGERS`, `ROUTES_TO`, `TRANSLATES`, `STREAMS_TO`, `DMA_TO`, `SHARED_WITH`, `CAUSED_BY`, `AFFECTS_IF_REMOVED`. Do not create ad-hoc tables outside this schema.

### Base vs Custom Separation

The `namespace` field on every node (not separate DB files) separates open-source knowledge from user-proprietary knowledge:

- `namespace="base"` — ARM/Linux open-source knowledge, written by seed scripts in `knowledge-graph/base/`
- `namespace="custom"` — user's in-house SoC knowledge, written by `scripts/ingest_custom.py`

When querying, `custom` results should take precedence over `base` for the same component name.

### Writing to the Graph

Kuzu 0.11+ has no `MERGE` statement. Use the helpers from `knowledge-graph/base/_ingest_helpers.py`:

```python
from _ingest_helpers import upsert_node, create_rel

# Idempotent node creation (silently skips if primary key exists)
upsert_node(conn, "Component", {"name": "GIC-600", "type": "interrupt-controller", "namespace": "base", ...})

# Relationship creation (silently handles errors)
create_rel(conn, "ROUTES_TO", "Component", "Component", src_name="GIC-600", dst_name="Cortex-A55-Cluster")
```

All seed scripts in `knowledge-graph/base/` follow this pattern. New seed scripts must import from `_ingest_helpers` and set `namespace="base"`.

### GraphRAG Queries

Query templates in `knowledge-graph/queries/` are Python functions that return structured dicts. Domain skills call these via the MCP server — do not embed inline Cypher in `skill.md` files.

## MCP Tool Server

### Running the Server

**Must be run from the repo root** as `python mcp/server.py`. Do not run from inside `mcp/` — the local `mcp/` directory will shadow the installed `mcp` SDK package and cause import errors.

```bash
# Correct
python mcp/server.py

# Wrong — local mcp/ shadows installed mcp package
cd mcp && python server.py
```

The server uses **stdio transport** (FastMCP default). `MCP_HOST` / `MCP_PORT` env vars exist but are secondary — skills communicate via stdio, not TCP.

### Registered MCP Tools (current)

All four are `READ_ONLY` and exposed by `mcp/server.py`:

| Tool | Input | Purpose |
|---|---|---|
| `query_power_chain` | `component_name: str` | Trace PMIC → PowerDomain → Component supply path |
| `query_cross_domain_failure` | `symptom_keywords: list[str]` | Multi-hop failure mode analysis |
| `query_interrupt_path` | `irq_source: str` | IRQ source → GIC-600 → ITS → CPU routing |
| `query_isp_pipeline` | `sensor_name: str` (optional) | Sensor → ISP → DMA-BUF → GPU/NPU data path |

### Adding New Tools

1. Write the implementation in the appropriate `mcp/tools/` subdirectory
2. Register it in `mcp/tools/safety_gate.py` → `TOOL_RISK_LEVELS` dict
3. Add an `@mcp.tool()` decorated function in `mcp/server.py` that calls `check_approval(tool_name)` first

### Safety Gate

`mcp/tools/safety_gate.py` exports two functions:

```python
get_risk_level(tool_name: str) -> RiskLevel        # READ_ONLY / CONFIG / DESTRUCTIVE
check_approval(tool_name: str, requires_human_approval: bool = False) -> bool
# Raises PermissionError for DESTRUCTIVE tools unless requires_human_approval=True
```

Unknown tools default to `READ_ONLY` with a warning. New tools must be added to `TOOL_RISK_LEVELS` — do not leave them unregistered.

### Log Parsers

`mcp/tools/log_parsers/` contains 16 parsers, all registered in `safety_gate.py` and `mcp/server.py`:

| Parser file | MCP tool name | Domain skill |
|---|---|---|
| `ftrace_parser.py` | `parse_ftrace` | power-thermal |
| `perf_parser.py` | `parse_perf_stat` | power-thermal |
| `thermal_parser.py` | `parse_thermal_log` | power-thermal |
| `dvfs_opp_calc.py` | `compute_dvfs_efficiency` | power-thermal |
| `suspend_resume_parser.py` | `parse_suspend_resume_log` | power-thermal |
| `pll_checker.py` | `parse_pll_log` | power-thermal |
| `power_island_scanner.py` | `scan_power_islands` | power-thermal |
| `pmic_log_parser.py` | `parse_pmic_log` | boot-debug |
| `irq_stat_parser.py` | `parse_irq_stats` | interrupt-virt |
| `v4l2_stats_parser.py` | `parse_v4l2_log` | multimedia |
| `emmc_io_parser.py` | `parse_emmc_io_log` | multimedia |
| `camera_hal_error_decoder.py` | `parse_camera_hal_errors` | multimedia |
| `perfetto_gpu_parser.py` | `parse_perfetto_gpu` | gpu-rendering |
| `agp_parser.py` | `parse_agp_report` | gpu-rendering |
| `vm_exit_counter.py` | `parse_vm_exit_stats` | interrupt-virt |
| `its_validator.py` | `validate_its_table` | interrupt-virt |

New parsers go here and must be registered in both `safety_gate.py` and `mcp/server.py`.

## Skill File Convention

```
skills/<skill-name>/
├── skill.md      # Claude Code skill definition → registered to ~/.claude/skills/<name>.md
├── *.yaml        # Supporting data (Socratic templates, term dictionaries)
└── evals/        # ≥ 30 test cases: case_NNN.json {input, expected_output, domain}
```

`skill.md` required frontmatter:

```markdown
---
description: <one-line description used by Claude Code for invocation routing>
---
```

Knowledge anchors in `skill.md` must cite specific open-source references (ARM TRM section numbers, Linux kernel `Documentation/` paths). No proprietary SoC assumptions in the base prompt.

## Domain Skills — Knowledge Anchors

| Skill | Primary open-source references |
|---|---|
| `power-thermal-expert` | ARM DynamIQ power model, Linux `Documentation/scheduler/sched-energy.rst`, ACPI C-state spec, LPDDR5 JEDEC JESD79-5; **STR:** Linux `Documentation/power/states.rst`, `Documentation/driver-api/pm/` (`dev_pm_ops` callback chain), ARM PSCI spec DEN0022; **STD:** Linux `Documentation/power/hibernation.rst` (`swsusp` snapshot); STD annotated as not applicable to Android targets |
| `boot-debug-expert` | ARM CoreSight SoC-600 TRM (ADIv6), AMBA APB spec, Linux `Documentation/driver-api/clk.rst` |
| `multimedia-camera-expert` | Linux `Documentation/userspace-api/media/`, DMA-BUF kernel docs (`Documentation/driver-api/dma-buf.rst`), F2FS docs, MIPI CSI-2 open spec |
| `gpu-rendering-expert` | Android GPU Inspector docs, Perfetto GPU counters, OpenGL ES 3.x spec, Vulkan render pass spec |
| `interrupt-virtualization-expert` | ARM GIC-600 TRM (public), ARM GICv3/v4 Architecture Specification, Linux `Documentation/core-api/irq/`, KVM ARM vGIC documentation |
| `hardware-spec-extractor` | Accellera IP-XACT 2022 standard |

## bsp-knowledge-mentor Rules

To be encoded in `skills/bsp-knowledge-mentor/skill.md` (Phase 3, pending). Must enforce:

- Never give a direct fix script. Guide with Socratic questions: symptom confirmation → resource state probe → hypothesis → tool verification.
- Learner level gates response depth: app-layer → HAL abstractions; driver → register-level; algorithm → Roofline/NPU; management → business impact only.
- Cross-department output must not contain raw register addresses or values.
- Power domain shutdown must never be suggested without verifying the full supply sequence.
- Blackboard mode: spawn domain skill sub-agents, collect confidence-scored hypotheses, run Arbiter convergence, synthesize structured report.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize and populate the base knowledge graph
python knowledge-graph/schema/init_db.py
python scripts/build_base_graph.py        # builds 501-node base graph
python scripts/build_base_graph.py --clean  # wipe and rebuild from scratch

# Start MCP server (from repo root — never from inside mcp/)
python mcp/server.py

# Register skills (copy to user Claude skills directory)
cp skills/*/skill.md ~/.claude/skills/

# Add user's in-house SoC documents to custom graph
python scripts/ingest_custom.py --input /path/to/TRM.pdf --soc mt6989

# Run unit tests
pytest tests/test_safety_gate.py -v       # safety gate — 82 tests

# Run evals
pytest evals/run_evals.py
```
