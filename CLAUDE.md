# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This repository implements **BSP Knowledge Skill Sets** — Claude Code skills that form a three-layer AI mentor system for SoC BSP (Board Support Package) engineers working on MediaTek or Qualcomm platforms. Read `BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md` for strategic intent and `ROADMAP.md` for the concrete milestone-by-milestone implementation plan.

## Hard Constraints

- **Zero server dependencies.** Every component must install via `pip`. No Docker, no Neo4j, no Qdrant — nothing requiring IT approval. Graph DB: Kuzu (embedded). Vector store: ChromaDB (embedded).
- **Open-source knowledge only in `knowledge-graph/base/`.** Sources: ARM public TRMs, AMBA specs, Linux kernel docs, open BSP community docs. No proprietary SoC register maps in this repo.
- **`knowledge-graph/custom/` is gitignored.** This is where end users add their in-house SoC TRMs and internal case libraries. Never commit anything from `custom/`.
- **Skills are Claude Code native.** `skill.md` files register to `~/.claude/skills/` (user-level) or `.claude/skills/` (project-level), invoked with `/skill-name` in Claude Code CLI and VS Code.

## Architecture Overview

Three layers, strictly ordered by dependency:

```
Layer 3: skills/bsp-knowledge-mentor/   ← ITS teaching engine, Blackboard coordinator
Layer 2: skills/<domain>-expert/        ← Six domain skills (built in parallel)
Layer 1: knowledge-graph/ + mcp/        ← Kuzu graph + MCP tool server; must exist first
```

**Critical constraint:** Domain skills must not be written before the Layer 1 base knowledge graph is populated. Skills without graph grounding fabricate hardware facts (register addresses, power sequences, clock dependencies).

## Skill File Convention

Every skill under `skills/` produces one Claude Code skill:

```
skills/<skill-name>/
├── skill.md          # Claude Code skill definition → registered to ~/.claude/skills/
├── *.yaml            # Supporting data (Socratic templates, term dictionaries, etc.)
└── evals/            # ≥ 30 test cases: case_NNN.json with input + expected output
```

`skill.md` frontmatter:

```markdown
---
description: <one-line description used by Claude Code for invocation routing>
---
```

Knowledge anchors in `skill.md` must cite open-source specs (ARM TRM section numbers, Linux kernel doc paths) — no proprietary SoC assumptions.

## Knowledge Graph Conventions

- **Schema** is defined in `knowledge-graph/schema/schema.py` as Kuzu Python API table definitions. Do not create ad-hoc node/relationship types outside this schema.
- **Canonical relationship names** (from schema): `SUPPLIES`, `POWERS`, `CLOCKS`, `DEPENDS_ON_CLOCK`, `TRIGGERS`, `ROUTES_TO`, `TRANSLATES`, `STREAMS_TO`, `DMA_TO`, `SHARED_WITH`, `CAUSED_BY`, `AFFECTS_IF_REMOVED`.
- **Kuzu queries** use Cypher syntax. Reusable query templates live in `knowledge-graph/queries/` as Python functions — domain skills call these rather than embedding inline Cypher.
- **Two namespaces:** `base/` (open, committed) and `custom/` (user proprietary, gitignored). When both are queried, `custom/` results take precedence.

## MCP Tool Server

All tool-calling from skills goes through the local MCP server (`mcp/server.py`, binds to `localhost` only). Tool categories:

- `mcp/tools/log_parsers/` — ftrace, perf, dmesg, V4L2, thermal, PMIC, IRQ parsers
- `mcp/tools/graph_query/` — Kuzu query wrappers exposed as MCP tools
- `mcp/tools/spec_extractor/` — IP-XACT and PDF ingestion pipeline
- `mcp/tools/term_translator/` — BSP ↔ business language lookup
- `mcp/tools/impact_translator/` — low-level metric → commercial outcome mapping

Every tool must declare its risk level in `mcp/tools/safety_gate.py`:

| Level | Meaning | Requires human approval |
|---|---|---|
| `READ_ONLY` | Reads logs, files, graph queries | No |
| `CONFIG` | Writes to `custom/` knowledge graph | No |
| `DESTRUCTIVE` | Modifies hardware state or triggers external builds | Yes — enforced by MCP server |

## bsp-knowledge-mentor Behavioral Rules

These are encoded in `skills/bsp-knowledge-mentor/skill.md` and must be preserved:

- Never give a direct fix script. Guide via Socratic questioning: symptom confirmation → resource state probe → hypothesis → tool verification.
- Learner level gates response depth: app-layer → HAL abstractions; driver → register-level; algorithm → Roofline/NPU; management → business impact only.
- Cross-department output must not contain raw register addresses or values.
- Power domain shutdown must never be suggested without verifying full supply sequence first.
- Blackboard mode: spawn domain skill sub-agents, collect hypotheses with confidence scores, run Arbiter convergence, synthesize final structured report.

## Six Domain Skills — Knowledge Anchors

| Skill | Primary open-source references |
|---|---|
| `power-thermal-expert` | ARM DynamIQ power model, Linux `sched-energy.rst`, ACPI C-state spec, LPDDR5 JEDEC JESD79-5 |
| `boot-debug-expert` | ARM CoreSight SoC-600 TRM (ADIv6), AMBA APB spec, Linux `clk` debug docs |
| `multimedia-camera-expert` | Linux V4L2 docs (`Documentation/userspace-api/media/`), DMA-BUF kernel docs, F2FS docs, MIPI CSI-2 spec |
| `gpu-rendering-expert` | Android GPU Inspector docs, Perfetto GPU counters, OpenGL ES 3.x spec, Vulkan spec |
| `interrupt-virtualization-expert` | ARM GIC-600 TRM, ARM GICv3/v4 Architecture Specification, Linux irq docs, KVM ARM vGIC docs |
| `hardware-spec-extractor` | Accellera IP-XACT 2022 standard |

## Installation Flow (for reference when writing scripts)

```bash
pip install -r requirements.txt          # kuzu, chromadb, unstructured[pdf], pdfplumber, mcp, pytest
python knowledge-graph/schema/init_db.py # create base Kuzu DB
python scripts/build_base_graph.py       # ingest open-source seed knowledge
# Register skills:
cp skills/*/skill.md ~/.claude/skills/   # or symlink for development
# Start MCP server (in background):
python mcp/server.py
```
