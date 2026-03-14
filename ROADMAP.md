# BSP Knowledge Skill Sets — Development Roadmap

> **Version:** v1.0
> **Start Date:** 2026-03-14
> **Reference:** [BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md](./BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md)

---

## Repository Structure Target

```
ai-bsp-knowledge-skill-sets/
│
├── skills/                          # Claude Agent Skill definitions
│   ├── bsp-knowledge-mentor/
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

## Phase 1 — Knowledge Graph Infrastructure
**Duration:** Month 1–2 (2026-03-14 → 2026-05-09)
**Goal:** Build the trustworthy knowledge foundation that eliminates hallucination.
**Principle:** No domain skill should be written before Phase 1 is complete — skills without a grounded knowledge base will hallucinate hardware facts.

### M1.1 — Repository Scaffolding
- [ ] Create directory structure as defined above
- [ ] Set up `README.md` with development guide and contribution conventions
- [ ] Define skill directory convention: each skill folder contains `prompt.md`, `tools.md`, `config.yaml`
- [ ] Set up Python virtual environment + `requirements.txt` (Neo4j driver, LlamaParse, Unstructured, etc.)

### M1.2 — Neo4j Knowledge Graph Setup
- [ ] Write `knowledge-graph/schema/nodes.cypher` — define all node types:
  - `Component` (CPU_Core, GPU, NPU, ISP, PMIC, DDR, eMMC)
  - `PowerDomain`, `ClockSource`, `Register`, `Interrupt`, `FailureMode`
- [ ] Write `knowledge-graph/schema/edges.cypher` — define all edge types:
  - `SUPPLIES`, `POWERS`, `CLOCKS`, `DEPENDS_ON_CLOCK`
  - `TRIGGERS`, `ROUTES_TO`, `TRANSLATES`
  - `STREAMS_TO`, `DMA_TO`, `SHARED_WITH`
  - `CAUSED_BY`, `AFFECTS_IF_REMOVED`
- [ ] Write `infra/neo4j/docker-compose.yaml` for local Neo4j Community deployment
- [ ] Write `infra/neo4j/init.sh` — apply schema, verify connectivity

### M1.3 — Seed Knowledge Ingestion
- [ ] Write `knowledge-graph/seed-data/power-tree.cypher` — PMIC → PowerDomain → Component supply chain
- [ ] Write `knowledge-graph/seed-data/clock-tree.cypher` — PLL → clock domain dependencies
- [ ] Write `knowledge-graph/seed-data/interrupt-routing.cypher` — GIC-600 IRQ routing table
- [ ] Write `knowledge-graph/seed-data/failure-modes.cypher` — top 20 most common BSP failure patterns (manually curated from existing case history)
- [ ] Verify: graph has ≥ 500 nodes covering the four core domains

### M1.4 — Document Ingestion Pipeline
- [ ] Write `tools/spec-extractor/pdf_ingest.py` — OCR + text cleaning for PDF datasheets
- [ ] Write `tools/spec-extractor/ipxact_parser.py` — Accellera IP-XACT XML → structured JSON
- [ ] Write `tools/spec-extractor/register_extractor.py` — extract register address, bit fields, reset values
- [ ] Write `tools/graph-writer/neo4j_writer.py` — load structured JSON → Neo4j nodes/edges
- [ ] Write `tools/spec-extractor/validate.py` — sampling-based accuracy check (register address spot-check)

### M1.5 — Air-Gap Security Baseline
- [ ] Write `infra/air-gap/acl_config.yaml` — document access control rules
- [ ] Write `infra/air-gap/verify_isolation.sh` — confirm no outbound traffic from inference stack
- [ ] Document data classification policy in `docs/data-classification.md`

### M1.6 — GraphRAG Query Templates
- [ ] Write `knowledge-graph/queries/power-chain.cypher` — trace supply path from PMIC to a given component
- [ ] Write `knowledge-graph/queries/cross-domain-failure.cypher` — multi-hop: symptom → power domain → thermal → clock violation
- [ ] Write `knowledge-graph/queries/interrupt-path.cypher` — IRQ source → GIC → ITS → vCPU
- [ ] Benchmark: multi-hop query success rate ≥ 85% against 20 test queries

**Phase 1 Exit Criteria:**
- [ ] Neo4j running locally with ≥ 500 nodes, ≥ 4 domains covered
- [ ] GraphRAG multi-hop query success rate ≥ 85%
- [ ] Document extraction accuracy ≥ 90% (sampled, human-verified)
- [ ] Air-gap isolation verified with no outbound data leakage

---

## Phase 2 — Domain Expert Skill Development
**Duration:** Month 3–4 (2026-05-10 → 2026-07-04)
**Goal:** Six deep-domain skills, each with validated tool-calling capability.
**Principle:** All six skills are developed in parallel. Each follows the same file convention.

### Skill File Convention (applies to all 6 skills)

```
skills/<skill-name>/
├── prompt.md       # Full system prompt (persona, rules, knowledge anchors)
├── tools.md        # Tool catalog: name, input schema, output schema, safety level
├── config.yaml     # Skill metadata: trigger patterns, routing hints, model params
└── evals/          # ≥ 30 test cases with expected outputs
```

### M2.1 — `power-thermal-expert`
- [ ] Write `prompt.md` — anchor to P=αCV²f, big/little core trade-off, DVFS OPP table
- [ ] Write `tools/log-parsers/ftrace_parser.py` — extract C-state residency time distribution
- [ ] Write `tools/log-parsers/perf_parser.py` — parse perf sampling, compute IPC per core
- [ ] Write `tools/log-parsers/thermal_parser.py` — LVTS temperature event timeline
- [ ] Implement Perf/Watt curve calculator (given OPP table, compute efficiency frontier)
- [ ] Write ≥ 30 eval cases covering: DVFS misconfiguration, C-state wrong residency, LPDDR5 deep sleep failure, EAS calibration drift

### M2.2 — `boot-debug-expert`
- [ ] Write `prompt.md` — power sequencing, PLL lock window, ADIv6 chain, latch-up prevention
- [ ] Write `tools/log-parsers/pmic_log_parser.py` — extract rail voltage ramp events and sequence violations
- [ ] Write `tools/log-parsers/pll_checker.py` — verify PLL lock time before clock consumer access
- [ ] Write `tools/log-parsers/power_island_scanner.py` — detect zombie power island states
- [ ] Write ≥ 30 eval cases covering: wrong supply order, premature PLL access, isolation cell clamp value mismatch, ADIv6 QDENY stuck

### M2.3 — `multimedia-camera-expert`
- [ ] Write `prompt.md` — ISP pipeline stages, V4L2 buffer model, eMMC half-duplex limitation
- [ ] Write `tools/log-parsers/v4l2_stats_parser.py` — buffer queue depth, overflow events
- [ ] Write `tools/log-parsers/emmc_io_parser.py` — F2FS GC and checkpoint event detection from iostat
- [ ] Write `tools/log-parsers/camera_hal_error_decoder.py` — decode ≥ 200 Android Camera HAL error codes
- [ ] Write `knowledge-graph/queries/isp-pipeline.cypher` — trace sensor → ISP → DMA-BUF → GPU/NPU path
- [ ] Write ≥ 30 eval cases covering: camera open fail (I2C/PMIC/MIPI), preview stutter, recording dropout, ISP AWB edge case

### M2.4 — `gpu-rendering-expert`
- [ ] Write `prompt.md` — render pipeline stages, Depth Pre-pass, Overdraw cost model, Draw Call budget
- [ ] Write `tools/log-parsers/perfetto_gpu_parser.py` — extract GPU task timeline, memory bandwidth events
- [ ] Write `tools/log-parsers/snapdragon_profiler_parser.py` — parse Snapdragon Profiler GPU timing export
- [ ] Implement Overdraw heatmap generator (from GPU Inspector output)
- [ ] Write ≥ 30 eval cases covering: Overdraw > 3x, Draw Call spike, Fragment Shader memory bandwidth bound, thermal throttling during render

### M2.5 — `interrupt-virtualization-expert`
- [ ] Write `prompt.md` — GIC-600 packet architecture, ITS EventID→IntID mapping, GICv4 direct injection model
- [ ] Write `tools/log-parsers/irq_stat_parser.py` — parse `/proc/interrupts` snapshots, detect interrupt storm
- [ ] Write `tools/log-parsers/vm_exit_counter.py` — extract VM Exit frequency per interrupt source from hypervisor trace
- [ ] Write ITS mapping table validator (cross-check EventID→IntID→target CPU consistency)
- [ ] Write ≥ 30 eval cases covering: List Register overflow, ITS table corruption, VM Exit storm, SGI cross-core delivery latency regression

### M2.6 — `hardware-spec-extractor`
- [ ] Write `prompt.md` — IP-XACT structure, register extraction workflow, graph injection steps
- [ ] Extend `tools/spec-extractor/ipxact_parser.py` to support Accellera 2022 standard
- [ ] Write batch processing wrapper: directory of PDFs/XMLs → bulk Neo4j import
- [ ] Write `tools/graph-writer/diff_writer.py` — only write new/changed nodes (idempotent imports)
- [ ] Write output validation: JSON schema check before graph write

### M2.7 — Tool Safety Framework
- [ ] Implement `tools/safety_gate.py` — classify every tool call as `READ_ONLY` / `CONFIG` / `DESTRUCTIVE`
- [ ] Enforce: `DESTRUCTIVE` operations require `requires_human_approval: true` in config
- [ ] Write unit tests for safety gate covering all three risk levels

**Phase 2 Exit Criteria:**
- [ ] Each skill passes ≥ 30 real BSP problem eval cases with human score ≥ 4/5
- [ ] Tool-calling success rate ≥ 90% (no API errors, correct output parsing)
- [ ] Average skill response time < 15 seconds
- [ ] Safety gate blocks all `DESTRUCTIVE` calls without explicit approval flag

---

## Phase 3 — ITS Mentor Engine & Blackboard Integration
**Duration:** Month 5–6 (2026-07-05 → 2026-08-29)
**Goal:** Wire the six domain skills into a coordinated, teachable system.

### M3.1 — `bsp-knowledge-mentor` Skill
- [ ] Write `skills/bsp-knowledge-mentor/prompt.md` — full system prompt per Appendix 10.1 of dev plan
- [ ] Implement learner level detector: classify questioner as app / driver / algo / management by keyword heuristics
- [ ] Write Socratic questioning template library (symptom confirmation → resource state query → hypothesis probe → tool verification)
- [ ] Implement conversation history tracker — persist learner level assessment across turns
- [ ] Enforce prohibition rules: no direct fix scripts, no register addresses in cross-department channels, no power domain changes without sequencing verification

### M3.2 — Blackboard Multi-Agent Framework
- [ ] Select and integrate multi-agent orchestration framework (LangGraph preferred; evaluate AutoGen as fallback)
- [ ] Implement `Blackboard` data structure — shared semantic memory (see Section 7.1 of dev plan)
- [ ] Implement `Arbiter` routing unit — keyword-based priority routing + confidence-weighted convergence
- [ ] Write `blackboard_runner.py` — orchestrates full diagnostic session: problem intake → parallel hypothesis → convergence → structured report
- [ ] Write end-to-end test: "30-minute recording random reboot" case requiring ≥ 3 skill collaboration

### M3.3 — Cross-Domain Terminology Translation
- [ ] Build BSP terminology dictionary: BSP physical ↔ business language ↔ algorithm metrics
- [ ] Write `tools/term-translator/translate.py` — bidirectional lookup with context disambiguation
- [ ] Write Slack Bolt bot (`infra/slack-bot/`) — intercepts cross-department messages, proposes translations inline
- [ ] Ensure output filter: no raw register values transmitted through public Slack channels

### M3.4 — Business Impact Translation Engine
- [ ] Write `tools/impact-translator/bsp_to_business.py` — maps low-level metric deltas to commercial outcomes
  - Template: `{component} {metric} {delta}` → `{product} {user-experience} {delta}` → `vs competitor {X}%`
- [ ] Write impact translation rules for: LPDDR5 leakage, DVFS OPP shift, ISP latency, eMMC write throughput, GPU thermal throttle

### M3.5 — Evaluation: Cross-Domain Cases
- [ ] Write ≥ 20 cross-domain eval cases requiring ≥ 3 skill collaboration
- [ ] Write `evals/blackboard_eval.py` — automated scoring of root cause identification accuracy
- [ ] Run A/B comparison: Blackboard mode vs single-skill mode on complex cases

**Phase 3 Exit Criteria:**
- [ ] Cross-domain complex case diagnosis accuracy ≥ 75% (expert blind review)
- [ ] Socratic guidance leads to ≥ 30% improvement in engineer problem-solving rate (pre/post measurement)
- [ ] Terminology translation response time < 5 seconds
- [ ] Blackboard convergence tested on ≥ 20 multi-domain cases without deadlock

---

## Phase 4 — Closed-Loop Automation & Knowledge Evolution
**Duration:** Month 7+ (2026-08-30 onwards)
**Goal:** System self-improves from real engineering work; BSP value becomes visible to stakeholders.

### M4.1 — Compiler-in-the-Loop CI/CD Integration
- [ ] Write Jenkins pipeline definition: AI-suggested DTS change → build → LAVA hardware test → result feedback
- [ ] Write `tools/ci-feedback/crash_log_ingestor.py` — auto-parse CI failures → feed back to LLM self-reflection
- [ ] Write `tools/ci-feedback/benchmark_tracker.py` — track perf regression across builds
- [ ] Define reinforcement signal schema: build result + test pass/fail + benchmark delta → agent feedback record

### M4.2 — Tacit Knowledge Sedimentation
- [ ] Write `tools/graph-writer/case_report_ingestor.py` — parse engineer post-mortem reports → extract new causal paths
- [ ] Implement new `FailureMode` node auto-creation when novel root cause is identified
- [ ] Implement knowledge graph versioning: tag each ingest batch with date and source case ID
- [ ] Write knowledge gap detector: identify topology regions with few `FailureMode` nodes (potential blind spots)

### M4.3 — BSP Value Visibility Dashboard
- [ ] Write quarterly BSP contribution report generator — aggregates: cases resolved, knowledge nodes added, time-to-diagnosis delta
- [ ] Mandate: every optimization recommendation output includes a business impact paragraph
- [ ] Write `tools/impact-translator/report_template.py` — structured optimization report with mandatory commercial impact section

### M4.4 — Continuous Evaluation Pipeline
- [ ] Write `evals/regression_runner.py` — weekly automated re-run of all eval cases, flag accuracy regressions
- [ ] Set up knowledge graph coverage monitor: alert when monthly new node count < 50
- [ ] Write security audit script: monthly verification of air-gap compliance

**Phase 4 Exit Criteria:**
- [ ] Knowledge graph grows ≥ 50 nodes/month from real case sedimentation
- [ ] 100% of optimization reports include business impact translation
- [ ] CI/CD automated test coverage ≥ 70%
- [ ] Zero confidential document leakage incidents (continuous monitoring)

---

## Dependency Map

```
M1.1 (scaffold)
  └─► M1.2 (Neo4j schema)
        └─► M1.3 (seed data)
              └─► M1.6 (GraphRAG queries)
  └─► M1.4 (doc ingestion pipeline)
        └─► M1.5 (air-gap validation)

[Phase 1 complete]
  └─► M2.1–M2.6 (domain skills, parallel)
        └─► M2.7 (safety framework, shared)

[Phase 2 complete]
  └─► M3.1 (mentor skill)
  └─► M3.2 (blackboard framework)
        ├─► M3.3 (terminology translation)
        └─► M3.4 (business impact engine)
              └─► M3.5 (cross-domain evals)

[Phase 3 complete]
  └─► M4.1 (CI/CD loop)
  └─► M4.2 (knowledge sedimentation)
  └─► M4.3 (value dashboard)
  └─► M4.4 (continuous eval)
```

---

## KPI Tracking

| Metric | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|
| Knowledge graph nodes | ≥ 500 | ≥ 1,000 | ≥ 1,500 | +50/month |
| GraphRAG multi-hop success | ≥ 85% | ≥ 90% | ≥ 90% | ≥ 90% |
| Single-domain diagnosis accuracy | — | ≥ 90% | ≥ 90% | ≥ 90% |
| Cross-domain diagnosis accuracy | — | — | ≥ 75% | ≥ 80% |
| Hallucination rate vs pure RAG | — | — | ≥ 50% reduction | maintained |
| Onboarding cycle reduction | — | — | ≥ 30% | ≥ 30% |
| Security incidents | 0 | 0 | 0 | 0 |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-14 | GraphRAG over pure vector RAG | Hardware topology is causal; vector search loses multi-hop dependency chains |
| 2026-03-14 | Phase 1 must complete before Phase 2 | Skills without grounded knowledge graph produce unverifiable hardware claims |
| 2026-03-14 | LangGraph as primary multi-agent framework | Native graph-based state machine maps cleanly to Blackboard pattern; AutoGen as fallback |
| 2026-03-14 | Air-gap is non-negotiable | BSP register maps and SoC TRMs are trade secrets; no public cloud egress permitted |

---

*Roadmap reflects the four-phase blueprint in BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md, translated into concrete file-level deliverables and sequenced by dependency order.*
