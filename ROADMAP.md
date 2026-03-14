# BSP Knowledge Skill Sets — Development Roadmap

> **Version:** v1.2
> **Start Date:** 2026-03-14
> **Last Updated:** 2026-03-14
> **Reference:** [BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md](./BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md)

---

## Project Status Summary

**As of 2026-03-14**

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1 — Knowledge Graph Infrastructure | ✅ Complete | 6/6 milestones done |
| Phase 2 — Domain Expert Skill Development | 🔄 In Progress | ~15% (scaffolding + safety gate + spec extractor; no `skill.md` files yet; log parsers pending) |
| Phase 3 — ITS Mentor Engine & Blackboard | ⬜ Not Started | — |
| Phase 4 — Knowledge Evolution & Extensibility | ⬜ Not Started | (CI/CD templates scaffolded as part of M1.1) |

### What's Done

- Full repository scaffold: directory structure, `scripts/install.sh`, `requirements.txt`, `.gitignore`
- Kuzu schema (`knowledge-graph/schema/schema.py`, `init_db.py`) — all node and relationship tables defined
- Open-source seed knowledge: `arm-gic-600.py`, `arm-amba-axi.py`, `linux-dvfs-eas.py`, `common-failure-modes.py`
- Four GraphRAG query templates: `power_chain.py`, `cross_domain_failure.py`, `interrupt_path.py`, `isp_pipeline.py`
- Document ingestion pipeline: `pdf_ingest.py`, `ipxact_parser.py`, `register_extractor.py`, `validate.py`
- MCP local tool server: `mcp/server.py`, `mcp/tools/graph_query/query_tools.py`
- Tool safety gate: `mcp/tools/safety_gate.py` (READ_ONLY / CONFIG / DESTRUCTIVE classification)
- `scripts/build_base_graph.py`, `scripts/ingest_custom.py`
- All 7 skill directories scaffolded with `evals/` placeholder
- CI/CD reference templates: `templates/ci-integration/github-actions.yaml`, `jenkins-pipeline.groovy`
- Docs: `skill-registration.md`, `mcp-setup.md`, `custom-knowledge.md`

### What's Next (Immediate)

Phase 2 is the active work front. The unblocked items are:

1. **Write `skill.md` for each of the 6 domain skills** (all parallel, no dependencies between them)
2. **Write `mcp/tools/log_parsers/`** — currently empty; needed for tool-calling from skills
3. **Write eval cases** (`evals/cases/*.json`) for each skill — required for Phase 2 exit

---

## Design Constraints

- **Zero server dependencies.** Every component installs via `pip`. No Docker, no Neo4j, no Qdrant — nothing requiring IT approval. Graph DB: Kuzu (embedded). Vector store: ChromaDB (embedded).
- **Open-source knowledge only in `knowledge-graph/base/`.** Sources: ARM Architecture Reference Manuals, ARM GIC-600 spec, AMBA/AXI specs, Linux kernel documentation, open BSP community docs. No proprietary SoC TRMs in this repo.
- **`knowledge-graph/custom/` is gitignored.** End users populate this with in-house SoC TRMs and internal case libraries. Never commit anything from `custom/`.
- **Claude Code native.** `skill.md` files register to `~/.claude/skills/` (user-level) or `.claude/skills/` (project-level), invoked with `/skill-name` in Claude Code CLI and VS Code.

---

## Repository Structure Target

```
ai-bsp-knowledge-skill-sets/
│
├── skills/                              # Claude Code Skill source files
│   ├── bsp-knowledge-mentor/
│   │   ├── skill.md                     # Claude Code skill definition (registered to ~/.claude/skills/)
│   │   ├── socratic-templates.yaml      # Questioning sequence templates
│   │   ├── term-dictionary.yaml         # BSP ↔ business language ↔ algo metrics
│   │   └── evals/
│   ├── power-thermal-expert/
│   ├── boot-debug-expert/
│   ├── multimedia-camera-expert/
│   ├── gpu-rendering-expert/
│   ├── interrupt-virtualization-expert/
│   └── hardware-spec-extractor/
│
├── knowledge-graph/
│   ├── schema/                          # Kuzu table definitions (Python scripts)
│   ├── base/                            # Open-source seed knowledge (committed)
│   │   ├── arm-gic-600.py               # ✅ Done
│   │   ├── arm-amba-axi.py              # ✅ Done
│   │   ├── linux-dvfs-eas.py            # ✅ Done
│   │   └── common-failure-modes.py      # ✅ Done
│   ├── custom/                          # .gitignore'd — user fills with in-house data
│   │   └── README.md                    # ✅ Done
│   └── queries/                         # Reusable Kuzu Cypher query templates (.py)
│       ├── power_chain.py               # ✅ Done
│       ├── cross_domain_failure.py      # ✅ Done
│       ├── interrupt_path.py            # ✅ Done
│       └── isp_pipeline.py              # ✅ Done
│
├── mcp/                                 # MCP local tool server
│   ├── server.py                        # ✅ Done
│   └── tools/
│       ├── safety_gate.py               # ✅ Done
│       ├── log_parsers/                 # ⬜ Empty — Phase 2 work
│       ├── graph_query/query_tools.py   # ✅ Done
│       └── spec_extractor/              # ✅ Done (pdf_ingest, ipxact_parser, register_extractor, validate)
│
├── evals/                               # Evaluation harness
│   ├── cases/                           # ⬜ Empty — Phase 2 work
│   ├── run_evals.py                     # ✅ Done
│   └── scorecards/
│
├── scripts/                             # Developer utilities
│   ├── install.sh                       # ✅ Done
│   ├── build_base_graph.py              # ✅ Done
│   └── ingest_custom.py                 # ✅ Done
│
├── templates/                           # User-facing templates
│   └── ci-integration/
│       ├── github-actions.yaml          # ✅ Done (scaffolded)
│       └── jenkins-pipeline.groovy      # ✅ Done (scaffolded)
│
└── docs/
    ├── skill-registration.md            # ✅ Done
    ├── custom-knowledge.md              # ✅ Done
    └── mcp-setup.md                     # ✅ Done
```

---

## Skill File Convention (applies to all 7 skills)

Each skill under `skills/` produces one registered Claude Code skill:

```
skills/<skill-name>/
├── skill.md            # The Claude Code skill definition file
│                       # → copied/symlinked to ~/.claude/skills/<skill-name>.md
│                       # → or placed in .claude/skills/ for project-level registration
├── *.yaml              # Supporting data files referenced by skill.md
└── evals/              # ≥ 30 test cases: input (BSP question) + expected output
    ├── case_001.json
    └── ...
```

`skill.md` format:

```markdown
---
description: <one-line description used by Claude Code to decide when to invoke>
---

<full system prompt: persona, domain rules, GraphRAG query hooks, tool invocations>
```

---

## Phase 1 — Knowledge Graph Infrastructure ✅ Complete
**Duration:** Month 1–2 (2026-03-14 → 2026-05-09)

### M1.1 — Repository Scaffolding ✅
- [x] Create directory structure
- [x] Write `scripts/install.sh`
- [x] Write `requirements.txt` (kuzu, chromadb, unstructured[pdf], pdfplumber, mcp, pytest)
- [x] Add `knowledge-graph/custom/` to `.gitignore`
- [x] Write `docs/skill-registration.md`

### M1.2 — Kuzu Knowledge Graph Setup ✅
- [x] Write `knowledge-graph/schema/schema.py` — all node and relationship table definitions
- [x] Write `knowledge-graph/schema/init_db.py` — create and initialize Kuzu DB
- [x] Write `scripts/build_base_graph.py` — full base graph rebuild orchestrator

### M1.3 — Open-Source Seed Knowledge Ingestion ✅
- [x] Write `knowledge-graph/base/arm-gic-600.py` — GIC-600, ITS, GICv4 nodes
- [x] Write `knowledge-graph/base/arm-amba-axi.py` — AMBA AXI4, DMA-BUF interconnect nodes
- [x] Write `knowledge-graph/base/linux-dvfs-eas.py` — CPUFreq OPP, EAS energy model, C-state nodes
- [x] Write `knowledge-graph/base/common-failure-modes.py` — top 30 open-source documented failure patterns
- [x] Write `knowledge-graph/custom/README.md`
- [ ] Verify: base graph ≥ 500 nodes (pending `build_base_graph.py` execution against a live DB)

### M1.4 — Document Ingestion Pipeline ✅
- [x] Write `mcp/tools/spec_extractor/pdf_ingest.py`
- [x] Write `mcp/tools/spec_extractor/ipxact_parser.py` (Accellera IP-XACT XML → structured JSON)
- [x] Write `mcp/tools/spec_extractor/register_extractor.py`
- [x] Write `mcp/tools/spec_extractor/validate.py`
- [x] Write `scripts/ingest_custom.py`

### M1.5 — Kuzu GraphRAG Query Templates ✅
- [x] Write `knowledge-graph/queries/power_chain.py`
- [x] Write `knowledge-graph/queries/cross_domain_failure.py`
- [x] Write `knowledge-graph/queries/interrupt_path.py`
- [x] Write `knowledge-graph/queries/isp_pipeline.py`
- [ ] Benchmark: all four templates < 500 ms on base graph (pending live execution)

### M1.6 — MCP Local Tool Server Setup ✅
- [x] Write `mcp/server.py` (localhost-only binding)
- [x] Write `mcp/tools/graph_query/query_tools.py`
- [x] Write `mcp/tools/safety_gate.py`
- [x] Write `docs/mcp-setup.md`
- [ ] End-to-end verification: skill tool call → MCP server → Kuzu response (pending)

---

## Phase 2 — Domain Expert Skill Development 🔄 In Progress
**Duration:** Month 3–4 (2026-05-10 → 2026-07-04)
**Goal:** Six domain skills, each grounded in the base knowledge graph, with validated tool-calling via MCP.
**Current state:** Skill directories scaffolded. `skill.md` files, log parsers, and eval cases all pending.

### Skill File Convention (applies to all 6 skills)

```
skills/<skill-name>/
├── skill.md            # ⬜ Not written for any skill yet — this is the primary gap
├── *.yaml              # Supporting data (where applicable)
└── evals/              # ⬜ No cases written yet
```

### M2.1 — `power-thermal-expert` ⬜
- [ ] Write `skills/power-thermal-expert/skill.md` — anchor to: P=αCV²f (ARM DynamIQ power model), Linux EAS energy model (`sched-energy.rst`), ACPI C-state spec, LPDDR5 JEDEC JESD79-5 deep sleep timing
- [ ] Write `mcp/tools/log_parsers/ftrace_parser.py` — C-state residency from `trace-cmd` output
- [ ] Write `mcp/tools/log_parsers/perf_parser.py` — parse `perf stat`, compute IPC per cluster
- [ ] Write `mcp/tools/log_parsers/thermal_parser.py` — throttling events from `dmesg` / kernel thermal drivers
- [ ] Write `mcp/tools/log_parsers/dvfs_opp_calc.py` — Perf/Watt efficiency frontier from OPP table
- [ ] Register MCP tools: `analyze_cstate_residency`, `compute_dvfs_efficiency`, `parse_thermal_events`
- [ ] Write ≥ 30 eval cases: DVFS misconfiguration, C-state stuck, LPDDR5 deep sleep failure, EAS calibration drift, PMIC transient response

### M2.2 — `boot-debug-expert` ⬜
- [ ] Write `skills/boot-debug-expert/skill.md` — anchor to: ARM CoreSight SoC-600 TRM (ADIv6), AMBA APB power sequencing spec, ARM latch-up prevention guidelines
- [ ] Write `mcp/tools/log_parsers/pmic_log_parser.py` — voltage rail ramp events and sequence violations
- [ ] Write `mcp/tools/log_parsers/pll_checker.py` — premature clock consumer access before PLL lock
- [ ] Write `mcp/tools/log_parsers/power_island_scanner.py` — zombie power island states from `pm_domain` debug
- [ ] Write ≥ 30 eval cases: wrong supply order, premature PLL access, isolation cell clamp mismatch, ADIv6 QDENY stuck, CoreSight trace link failure

### M2.3 — `multimedia-camera-expert` ⬜
- [ ] Write `skills/multimedia-camera-expert/skill.md` — anchor to: Linux V4L2 spec, DMA-BUF kernel docs, F2FS docs, MIPI CSI-2 open spec
- [ ] Write `mcp/tools/log_parsers/v4l2_stats_parser.py` — buffer queue depth and overflow events
- [ ] Write `mcp/tools/log_parsers/emmc_io_parser.py` — F2FS GC and checkpoint stalls from `iostat -x`
- [ ] Write `mcp/tools/log_parsers/camera_hal_error_decoder.py` — Android Camera HAL3 error codes (≥ 100 AOSP-documented)
- [ ] Write ≥ 30 eval cases: camera open fail, preview stutter, recording dropout, ISP pipeline stall

### M2.4 — `gpu-rendering-expert` ⬜
- [ ] Write `skills/gpu-rendering-expert/skill.md` — anchor to: Android GPU Inspector docs, Perfetto GPU counters, OpenGL ES 3.x spec, Vulkan spec
- [ ] Write `mcp/tools/log_parsers/perfetto_gpu_parser.py` — GPU task timeline and thermal throttling from Perfetto JSON trace
- [ ] Write `mcp/tools/log_parsers/agp_parser.py` — Android GPU Inspector export: Draw Call count, Overdraw ratio, Fragment Shader ALU utilization
- [ ] Write ≥ 30 eval cases: Overdraw > 3x, Draw Call CPU bottleneck, Fragment Shader memory bandwidth bound, GPU thermal throttle

### M2.5 — `interrupt-virtualization-expert` ⬜
- [ ] Write `skills/interrupt-virtualization-expert/skill.md` — anchor to: ARM GIC-600 TRM, ARM GICv3/v4 Architecture Specification, Linux `irq` docs, KVM ARM vGIC documentation
- [ ] Write `mcp/tools/log_parsers/irq_stat_parser.py` — `/proc/interrupts` snapshots, interrupt storm detection
- [ ] Write `mcp/tools/log_parsers/vm_exit_counter.py` — VM Exit frequency from KVM perf events (`kvm:kvm_exit`)
- [ ] Write `mcp/tools/log_parsers/its_validator.py` — ITS EventID→IntID→target CPU consistency from GIC debug register dump
- [ ] Write ≥ 30 eval cases: List Register overflow, ITS table corruption, VM Exit storm, SGI cross-core latency regression

### M2.6 — `hardware-spec-extractor` ⬜
- [ ] Write `skills/hardware-spec-extractor/skill.md` — guides user through ingestion workflow: which files to provide, what the tool extracts, how to verify before graph write
- [ ] Extend `mcp/tools/spec_extractor/ipxact_parser.py` for Accellera IP-XACT 2022 (component/design/busInterface hierarchy)
- [ ] Write `mcp/tools/spec_extractor/graph_diff_writer.py` — idempotent Kuzu write (skip existing nodes)
- [ ] Write output validation: JSON schema check before any graph write
- [ ] Write ≥ 30 eval cases: IP-XACT round-trip accuracy, malformed XML recovery, duplicate detection, batch import

### M2.7 — Tool Safety Framework ✅ (safety_gate.py done; unit tests pending)
- [x] Write `mcp/tools/safety_gate.py` — READ_ONLY / CONFIG / DESTRUCTIVE classification
- [x] Enforce in MCP server: DESTRUCTIVE tools refuse without approval flag
- [ ] Write pytest unit tests for safety gate covering all three risk levels

**Phase 2 Exit Criteria:**
- [ ] Each skill registered and invocable via `/skill-name` in Claude Code CLI and VS Code
- [ ] Each skill passes ≥ 30 eval cases with human expert score ≥ 4/5
- [ ] MCP tool-calling success rate ≥ 90%
- [ ] Safety gate unit tests pass

---

## Phase 3 — ITS Mentor Engine & Blackboard Integration ⬜ Not Started
**Duration:** Month 5–6 (2026-07-05 → 2026-08-29)
**Prerequisite:** All 6 domain skills in Phase 2 must be complete and passing evals.

### M3.1 — `bsp-knowledge-mentor` Skill ⬜
- [ ] Write `skills/bsp-knowledge-mentor/skill.md` — full system prompt per Appendix 10.1 of dev plan
- [ ] Write `skills/bsp-knowledge-mentor/socratic-templates.yaml` — questioning sequences
- [ ] Write `skills/bsp-knowledge-mentor/term-dictionary.yaml` — ≥ 100 BSP ↔ business ↔ algo term pairs
- [ ] Encode learner-level detection rules (app / driver / algo / management keyword heuristics)
- [ ] Encode all prohibition rules in prompt

### M3.2 — Blackboard Multi-Agent Pattern (Claude Code Sub-agents) ⬜
- [ ] Implement Blackboard pattern using Claude Code sub-agents: mentor spawns domain skills, collects hypotheses, runs Arbiter, synthesizes report
- [ ] Write Blackboard session template (Markdown working document per Section 7.1 of dev plan)
- [ ] Implement Arbiter logic in mentor prompt: keyword routing, confidence threshold convergence
- [ ] Write `evals/blackboard_eval.py`
- [ ] End-to-end test: "30-minute recording random reboot" requiring multimedia + power-thermal + gpu collaboration

### M3.3 — Terminology Translation ⬜
- [ ] Expand `term-dictionary.yaml` to ≥ 200 term pairs across all six domains
- [ ] Write `mcp/tools/term_translator/translate.py` — bidirectional lookup, exposed as MCP tool

### M3.4 — Business Impact Translation Engine ⬜
- [ ] Write `mcp/tools/impact_translator/bsp_to_business.py`
- [ ] Write impact rules: LPDDR5 leakage → battery life, DVFS shift → sustained performance, ISP latency → camera UX, eMMC throughput → recording reliability, GPU throttle → frame rate
- [ ] Expose as MCP tool: `translate_to_business_impact(component, metric, delta, product_type)`

### M3.5 — Cross-Domain Evaluation ⬜
- [ ] Write ≥ 20 multi-domain eval cases (≥ 3 skill contributions each; drawn from open LKML bug reports and Linaro case studies)
- [ ] Extend `evals/run_evals.py` for Blackboard session replay and scoring
- [ ] A/B comparison: mentor-guided Blackboard mode vs direct single-skill on same complex cases

**Phase 3 Exit Criteria:**
- [ ] Cross-domain diagnosis accuracy ≥ 75% (expert blind review)
- [ ] Mentor correctly identifies learner level in ≥ 90% of test prompts
- [ ] Terminology translation ≥ 200 pairs, ≥ 85% accuracy
- [ ] Blackboard tested on ≥ 20 multi-domain cases without infinite loop

---

## Phase 4 — Knowledge Evolution & User Extensibility ⬜ Not Started
**Duration:** Month 7+ (2026-08-30 onwards)

### M4.1 — Knowledge Sedimentation CLI ⬜
- [ ] Extend `scripts/ingest_custom.py` — parse post-mortem reports (Markdown / plain text) → extract symptom/cause/resolution → write to `knowledge-graph/custom/` as `FailureMode` nodes
- [ ] Implement Kuzu graph versioning: tag each ingest with date, source file hash, SoC tag
- [ ] Write knowledge gap detector: query topology regions with few `FailureMode` nodes

### M4.2 — Business Impact Report Template ⬜
- [ ] Write `templates/optimization-report.md` — structured report with mandatory business impact section
- [ ] Write `mcp/tools/impact_translator/report_generator.py` — auto-fill business impact section

### M4.3 — CI/CD Integration Templates 🔄 Scaffolded
- [x] Write `templates/ci-integration/github-actions.yaml` (scaffolded)
- [x] Write `templates/ci-integration/jenkins-pipeline.groovy` (scaffolded)
- [ ] Write `docs/ci-integration.md`
- [ ] Validate GitHub Actions template end-to-end in this repo

### M4.4 — Base Graph Maintenance ⬜
- [ ] Write `scripts/update_base_graph.sh` — fetch latest ARM public spec release notes, flag changed sections
- [ ] Write `evals/regression_runner.py` — re-run all eval cases, report accuracy drift
- [ ] Set up GitHub Actions: weekly eval regression run on base graph

---

## Dependency Map

```
M1.1 (scaffold) ✅
  └─► M1.2 (Kuzu schema) ✅
        └─► M1.3 (seed ingestion) ✅
              └─► M1.5 (GraphRAG queries) ✅
  └─► M1.4 (doc ingestion pipeline) ✅
  └─► M1.6 (MCP server) ✅

[Phase 1 complete ✅]
  └─► M2.1–M2.6 (domain skills — parallel, all unblocked) ⬜
        └─► M2.7 (safety framework) ✅ partial

[Phase 2 complete]
  └─► M3.1 (bsp-knowledge-mentor)
        └─► M3.2 (blackboard sub-agent pattern)
  └─► M3.3 (terminology translation)
  └─► M3.4 (business impact engine)
        └─► M3.5 (cross-domain evals)

[Phase 3 complete]
  └─► M4.1 (knowledge sedimentation CLI)
  └─► M4.2 (report template + generator)
  └─► M4.3 (CI/CD templates) 🔄 partial
  └─► M4.4 (base graph maintenance + regression runner)
```

---

## KPI Tracking

| Metric | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|
| Base graph nodes | ≥ 500 | ≥ 800 | ≥ 1,000 | maintained |
| GraphRAG query latency | < 500 ms | < 500 ms | < 500 ms | < 500 ms |
| Single-domain diagnosis accuracy | — | ≥ 90% | ≥ 90% | ≥ 90% |
| Cross-domain diagnosis accuracy | — | — | ≥ 75% | ≥ 80% |
| Learner-level detection accuracy | — | — | ≥ 90% | ≥ 90% |
| Terminology coverage (term pairs) | — | — | ≥ 200 | growing |
| Hallucination rate vs pure RAG | — | — | ≥ 50% reduction | maintained |
| Server dependencies required | 0 ✅ | 0 | 0 | 0 |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-14 | GraphRAG over pure vector RAG | Hardware topology is causal; vector search loses multi-hop dependency chains (PMIC → PowerDomain → CPU → Clock) |
| 2026-03-14 | Phase 1 before Phase 2 | Skills without grounded knowledge graph produce unverifiable hardware claims |
| 2026-03-14 | Kuzu (embedded) instead of Neo4j | Neo4j requires a server; corporate IT commonly blocks self-hosted DBs. Kuzu is Cypher-compatible, embeds in-process, installs via pip |
| 2026-03-14 | ChromaDB (embedded) instead of Qdrant | Same reason — zero server footprint, pip installable |
| 2026-03-14 | Claude Code sub-agents instead of LangGraph | Skills are Claude Code native; sub-agent pattern achieves Blackboard coordination without an external framework dependency |
| 2026-03-14 | Open-source knowledge only in base graph | End users are MTK/Qualcomm BSP engineers; their in-house SoC TRMs are proprietary. Base stays open; `custom/` is user-managed and gitignored |
| 2026-03-14 | CI/CD as templates, not in-repo execution | User CI environments (Jenkins + LAVA) are company-internal; this repo provides reference templates only |

---

*Roadmap v1.2 — updated with accurate Phase 1 completion status and Phase 2 current state as of 2026-03-14.*
