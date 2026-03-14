# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This repository implements **BSP Knowledge Skill Sets** — a set of Claude Agent skills that form a three-layer AI mentor system for SoC BSP (Board Support Package) engineers. Read `BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md` for strategic intent and `ROADMAP.md` for the concrete milestone-by-milestone implementation plan.

## Architecture Overview

The system has three layers that depend on each other in strict order:

```
Layer 3: skills/bsp-knowledge-mentor/   ← ITS teaching engine, coordinates all others
Layer 2: skills/<domain>-expert/        ← Six domain skills (parallel, independent)
Layer 1: knowledge-graph/ + tools/      ← GraphRAG + Neo4j; must exist before skills
```

**Critical constraint:** Domain skills must not be written before the Layer 1 knowledge graph is populated. Skills without graph grounding will hallucinate hardware facts (register addresses, power sequences, clock dependencies).

## Skill Directory Convention

Every skill under `skills/` follows this structure:

```
skills/<skill-name>/
├── prompt.md     # Full system prompt: persona, domain rules, GraphRAG query hooks
├── tools.md      # Tool catalog: name, input/output schema, safety level
├── config.yaml   # Trigger patterns, learner-level routing hints, model params
└── evals/        # ≥ 30 anonymized real BSP problem cases with expected outputs
```

## Tool Safety Classification

Every tool call must be tagged in `config.yaml` with one of three risk levels:

| Level | Meaning | `requires_human_approval` |
|---|---|---|
| `READ_ONLY` | Reads logs, files, graph queries | `false` |
| `CONFIG` | Writes to knowledge graph, modifies tunables | `false` |
| `DESTRUCTIVE` | Modifies hardware state, triggers builds | `true` — mandatory |

The safety gate is implemented in `tools/safety_gate.py`. Never bypass it.

## Knowledge Graph Conventions

- **Node types** are defined in `knowledge-graph/schema/nodes.cypher`. Do not create ad-hoc node labels outside this schema.
- **Edge types** are defined in `knowledge-graph/schema/edges.cypher`. Hardware relationships must use the canonical edge names (`SUPPLIES`, `CLOCKS`, `TRIGGERS`, `CAUSED_BY`, etc.).
- **Seed data** lives in `knowledge-graph/seed-data/` as Cypher scripts. New failure modes discovered from real cases are added here.
- **Reusable query templates** live in `knowledge-graph/queries/`. Domain skills reference these rather than writing inline Cypher.

## bsp-knowledge-mentor Behavior Rules

The mentor skill has strict behavioral constraints that must be preserved in `prompt.md`:

- **Never give a direct fix script.** Guide the engineer to derive the answer via Socratic questions.
- **Learner level gates the response depth**: app-layer engineers get HAL abstractions; driver engineers get register-level detail; management gets business impact only.
- **Cross-department messages must not contain raw register addresses or values.**
- **Power domain shutdown must never be suggested without verifying the full supply sequence first.**

## Data Sovereignty

All BSP document ingestion and inference runs Air-Gapped (no public cloud egress). The isolation boundary is verified by `infra/air-gap/verify_isolation.sh`. Do not add any code that makes outbound HTTP calls to external APIs with BSP document content.

## Six Domain Skills Summary

| Skill | Core domain | Key physical anchor |
|---|---|---|
| `power-thermal-expert` | DVFS, EAS, C-states, PMIC, LPDDR5 | P = αCV²f |
| `boot-debug-expert` | Power sequencing, PLL lock, ADIv6 | Supply order: VDD_CORE → VDD_IO → VDD_ANA |
| `multimedia-camera-expert` | ISP pipeline, V4L2, DMA-BUF, eMMC/F2FS | Zero-Copy: V4L2 + DMA-BUF eliminates CPU memcpy |
| `gpu-rendering-expert` | Render pipeline, Overdraw, Draw Call | Depth Pre-pass reduces fragment shader work |
| `interrupt-virtualization-expert` | GIC-600, ITS, GICv4 virtual injection | GICv4 direct injection eliminates List Register VM Exit |
| `hardware-spec-extractor` | IP-XACT parsing, register extraction | Accellera 2022 standard for IP-XACT XML |

## Blackboard Multi-Agent Pattern

Complex cross-domain failures (requiring ≥ 3 skills) use the Blackboard pattern implemented in `tools/blackboard_runner.py`. The data structure is defined in Section 7.1 of `BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md`. The Arbiter's keyword-routing logic and confidence-weighted convergence rules are in Section 7.2 — do not deviate from this design without updating the decision log in `ROADMAP.md`.
