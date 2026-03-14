# BSP Knowledge Skill Sets

A set of Claude Agent skills that form a **three-layer AI mentor system** for SoC BSP (Board Support Package) engineers. The system provides Socratic-guided diagnostics, cross-domain failure analysis, and structured knowledge grounding via a GraphRAG knowledge graph — all running fully air-gapped to protect hardware trade secrets.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [Skill Directory Convention](#skill-directory-convention)
- [Domain Skills](#domain-skills)
- [Knowledge Graph](#knowledge-graph)
- [Tool Safety Classification](#tool-safety-classification)
- [Development Phases](#development-phases)
- [Getting Started](#getting-started)
- [Contributing](#contributing)

---

## Architecture Overview

The system is built in three layers that must be implemented in strict dependency order:

```
Layer 3: skills/bsp-knowledge-mentor/   ← ITS teaching engine; coordinates all others
Layer 2: skills/<domain>-expert/        ← Six domain skills (parallel, independent)
Layer 1: knowledge-graph/ + tools/      ← GraphRAG + Neo4j; must exist before skills
```

> **Critical constraint:** Domain skills must not be written before the Layer 1 knowledge graph is populated. Skills without graph grounding will hallucinate hardware facts (register addresses, power sequences, clock dependencies).

### Skill Interaction

```
User Query
    │
    ▼
bsp-knowledge-mentor  (entry coordinator)
    │
    ├──(teach mode)────► ITS Guidance Engine ──► Socratic question sequence
    │
    ├──(diagnose mode)─► Blackboard
    │                    ├── power-thermal-expert
    │                    ├── multimedia-camera-expert
    │                    ├── gpu-rendering-expert
    │                    └── interrupt-virtualization-expert
    │
    ├──(document mode)─► hardware-spec-extractor ──► GraphRAG query
    │
    └──(translate mode)► Terminology dictionary ──► Cross-department language bridge
```

---

## Repository Structure

```
ai-bsp-knowledge-skill-sets/
│
├── skills/                          # Claude Agent Skill definitions
│   ├── bsp-knowledge-mentor/        # Layer 3: ITS mentor & coordinator
│   ├── power-thermal-expert/
│   ├── boot-debug-expert/
│   ├── multimedia-camera-expert/
│   ├── gpu-rendering-expert/
│   ├── interrupt-virtualization-expert/
│   └── hardware-spec-extractor/
│
├── knowledge-graph/                 # GraphRAG / Neo4j infrastructure
│   ├── schema/                      # Node & edge type definitions (Cypher)
│   ├── seed-data/                   # Initial knowledge (power tree, clock tree, IRQ table)
│   └── queries/                     # Reusable GraphRAG query templates
│
├── tools/                           # Tool-calling implementations
│   ├── log-parsers/                 # ftrace, perf, dmesg, V4L2, thermal log parsers
│   ├── spec-extractor/              # IP-XACT & PDF ingestion pipeline
│   └── graph-writer/                # Neo4j ingest scripts
│
├── evals/                           # Evaluation harness
│   ├── cases/                       # Real BSP problem cases (anonymized)
│   └── scorecards/                  # Per-skill accuracy scorecards
│
├── infra/                           # Deployment & security configs
│   ├── neo4j/
│   ├── qdrant/
│   └── air-gap/                     # ACL and isolation verification scripts
│
└── docs/                            # Internal architecture docs
```

---

## Skill Directory Convention

Every skill under `skills/` follows this structure:

```
skills/<skill-name>/
├── prompt.md     # Full system prompt: persona, domain rules, GraphRAG query hooks
├── tools.md      # Tool catalog: name, input/output schema, safety level
├── config.yaml   # Trigger patterns, learner-level routing hints, model params
└── evals/        # ≥ 30 anonymized real BSP problem cases with expected outputs
```

---

## Domain Skills

### `bsp-knowledge-mentor` (Layer 3)

The system entry point and ITS (Intelligent Tutoring System) teaching engine. It coordinates all other skills and enforces Socratic guidance rules.

**Behavioral rules:**
- Never give a direct fix script — guide the engineer to derive the answer via Socratic questions.
- Learner level gates the response depth:

| Learner level | Trigger keywords | Mentor strategy |
|---|---|---|
| App-layer engineer | framework, API, SDK, FPS | HAL abstractions; avoid register details |
| Driver engineer | register, DMA, IRQ, kernel | Bit-level definitions, memory barriers, timing diagrams |
| Algorithm engineer | MIPS, model, latency, inference | Roofline model, NPU offload, bandwidth analysis |
| Management / PM | feature, experience, battery, temperature | Business impact translation only |

- Cross-department messages must not contain raw register addresses or values.
- Power domain shutdown must never be suggested without verifying the full supply sequence first.

### Six Domain Skills (Layer 2)

| Skill | Core domain | Key physical anchor |
|---|---|---|
| `power-thermal-expert` | DVFS, EAS, C-states, PMIC, LPDDR5 | P = αCV²f |
| `boot-debug-expert` | Power sequencing, PLL lock, ADIv6 | Supply order: VDD_CORE → VDD_IO → VDD_ANA |
| `multimedia-camera-expert` | ISP pipeline, V4L2, DMA-BUF, eMMC/F2FS | Zero-Copy: V4L2 + DMA-BUF eliminates CPU memcpy |
| `gpu-rendering-expert` | Render pipeline, Overdraw, Draw Call | Depth Pre-pass reduces fragment shader work |
| `interrupt-virtualization-expert` | GIC-600, ITS, GICv4 virtual injection | GICv4 direct injection eliminates List Register VM Exit |
| `hardware-spec-extractor` | IP-XACT parsing, register extraction | Accellera 2022 standard for IP-XACT XML |

---

## Knowledge Graph

The knowledge graph is the trustworthy foundation that eliminates hallucination. It uses **Neo4j** with **GraphRAG** (graph-based retrieval-augmented generation) rather than pure vector search, preserving the causal completeness of hardware topology.

### Schema

- **Node types** are defined in `knowledge-graph/schema/nodes.cypher`.
  - `Component` (CPU_Core, GPU, NPU, ISP, PMIC, DDR, eMMC)
  - `PowerDomain`, `ClockSource`, `Register`, `Interrupt`, `FailureMode`

- **Edge types** are defined in `knowledge-graph/schema/edges.cypher`.
  - `SUPPLIES`, `POWERS`, `CLOCKS`, `DEPENDS_ON_CLOCK`
  - `TRIGGERS`, `ROUTES_TO`, `TRANSLATES`
  - `STREAMS_TO`, `DMA_TO`, `SHARED_WITH`
  - `CAUSED_BY`, `AFFECTS_IF_REMOVED`

Do not create ad-hoc node labels or edges outside this schema.

### Reusable Query Templates

Reusable Cypher templates live in `knowledge-graph/queries/`. Domain skills reference these rather than writing inline Cypher.

---

## Tool Safety Classification

Every tool call must be tagged in `config.yaml` with one of three risk levels:

| Level | Meaning | `requires_human_approval` |
|---|---|---|
| `READ_ONLY` | Reads logs, files, graph queries | `false` |
| `CONFIG` | Writes to knowledge graph, modifies tunables | `false` |
| `DESTRUCTIVE` | Modifies hardware state, triggers builds | `true` — mandatory |

The safety gate is implemented in `tools/safety_gate.py`. **Never bypass it.**

---

## Development Phases

The project is built in four sequential phases. See [ROADMAP.md](./ROADMAP.md) for the full milestone breakdown and [BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md](./BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md) for strategic intent.

| Phase | Period | Goal |
|---|---|---|
| **Phase 1** — Knowledge Graph Infrastructure | Month 1–2 | Build grounded knowledge foundation; eliminates skill hallucination |
| **Phase 2** — Domain Expert Skill Development | Month 3–4 | Six deep-domain skills with validated tool-calling |
| **Phase 3** — ITS Mentor Engine & Blackboard Integration | Month 5–6 | Wire skills into a coordinated, teachable system |
| **Phase 4** — Closed-Loop Automation & Knowledge Evolution | Month 7+ | Self-improving system; BSP value visible to stakeholders |

### Phase Exit KPIs

| Metric | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| Knowledge graph nodes | ≥ 500 | ≥ 1,000 | ≥ 1,500 | +50/month |
| GraphRAG multi-hop success | ≥ 85% | ≥ 90% | ≥ 90% | ≥ 90% |
| Single-domain diagnosis accuracy | — | ≥ 90% | ≥ 90% | ≥ 90% |
| Cross-domain diagnosis accuracy | — | — | ≥ 75% | ≥ 80% |
| Security incidents | 0 | 0 | 0 | 0 |

---

## Getting Started

### Prerequisites

- Docker & Docker Compose (for local Neo4j)
- Python ≥ 3.11
- Neo4j Community Edition (via `infra/neo4j/docker-compose.yaml`)

### Local Setup

```bash
# 1. Start Neo4j
cd infra/neo4j
docker compose up -d

# 2. Apply schema and seed data
bash infra/neo4j/init.sh

# 3. Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Verify air-gap isolation
bash infra/air-gap/verify_isolation.sh
```

> **Data Sovereignty:** All BSP document ingestion and inference runs air-gapped (no public cloud egress). The isolation boundary is verified by `infra/air-gap/verify_isolation.sh`. Do not add any code that makes outbound HTTP calls to external APIs with BSP document content.

### Blackboard Multi-Agent Pattern

Complex cross-domain failures (requiring ≥ 3 skills) use the Blackboard pattern implemented in `tools/blackboard_runner.py`. The Arbiter's keyword-routing logic and confidence-weighted convergence rules are documented in Section 7.2 of `BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md`.

---

## Contributing

1. **Layer 1 first.** Do not add or modify any domain skill until `knowledge-graph/` is populated and Phase 1 exit criteria are met.
2. **Follow the skill directory convention.** Every skill folder must contain `prompt.md`, `tools.md`, `config.yaml`, and an `evals/` directory with ≥ 30 cases.
3. **Tag every tool call.** Add a `safety_level` (`READ_ONLY` / `CONFIG` / `DESTRUCTIVE`) in `config.yaml` for each tool. `DESTRUCTIVE` requires `requires_human_approval: true`.
4. **Stay within the schema.** New node and edge types must be added to `knowledge-graph/schema/` before use in seed data or skill queries.
5. **No cloud egress.** Do not introduce dependencies that send BSP document content to external APIs.
6. **Update the Decision Log.** Record any architectural decisions in the Decision Log table in [ROADMAP.md](./ROADMAP.md).
