# BSP Knowledge Skill Sets — Development Roadmap

> **Version:** v1.1
> **Start Date:** 2026-03-14
> **Reference:** [BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md](./BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md)

---

## Design Constraints

- **Zero server dependencies.** Every component installs via `pip`. No Docker, no Neo4j, no Qdrant server — nothing that requires IT approval.
- **Open-source knowledge base only.** Seed data sources: ARM Architecture Reference Manuals, ARM GIC-600 spec, AMBA/AXI specs, Linux kernel documentation, open BSP community docs. No proprietary SoC TRMs in this repo.
- **Two-layer knowledge.** `knowledge-graph/base/` is maintained here (open). `knowledge-graph/custom/` is populated by end users with their in-house SoC docs and never committed to this repo.
- **Claude Code native.** Skills are `.md` files registered to `~/.claude/skills/` (or project-level `.claude/skills/`). Invoked with `/skill-name` in Claude Code CLI and VS Code extension.

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
│   │   ├── arm-gic-600.py               # GIC-600 nodes/edges ingest script
│   │   ├── arm-amba-axi.py
│   │   ├── linux-dvfs-eas.py
│   │   └── common-failure-modes.py
│   ├── custom/                          # .gitignore'd — user fills with in-house data
│   │   └── README.md                    # Instructions for adding custom knowledge
│   └── queries/                         # Reusable Kuzu Cypher query templates (.py)
│
├── mcp/                                 # MCP local tool server
│   ├── server.py                        # MCP server entry point (localhost only)
│   └── tools/
│       ├── log_parsers/                 # ftrace, perf, dmesg, V4L2, thermal parsers
│       ├── graph_query/                 # Kuzu query wrappers exposed as MCP tools
│       └── spec_extractor/              # IP-XACT & PDF ingestion pipeline
│
├── evals/                               # Evaluation harness
│   ├── cases/                           # Anonymized real BSP problem cases (JSON)
│   ├── run_evals.py                     # Eval runner
│   └── scorecards/                      # Per-skill accuracy results
│
├── scripts/                             # Developer utilities
│   ├── install.sh                       # pip install + skill registration helper
│   ├── build_base_graph.py              # Rebuild base knowledge graph from scratch
│   └── ingest_custom.py                 # CLI: add user's in-house docs to custom/
│
├── templates/                           # User-facing templates
│   └── ci-integration/
│       ├── github-actions.yaml          # GitHub Actions workflow template
│       └── jenkins-pipeline.groovy      # Jenkins pipeline template (reference only)
│
└── docs/
    ├── skill-registration.md            # How to register skills in Claude Code / VS Code
    ├── custom-knowledge.md              # How to add in-house SoC knowledge
    └── mcp-setup.md                     # How to configure the local MCP server
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

## Phase 1 — Knowledge Graph Infrastructure
**Duration:** Month 1–2 (2026-03-14 → 2026-05-09)
**Goal:** Build the open-source knowledge foundation that grounds all skills against hallucination.
**Principle:** No domain skill should be written before Phase 1 is complete — skills without a grounded knowledge base will fabricate hardware facts.

### M1.1 — Repository Scaffolding
- [ ] Create directory structure as defined above
- [ ] Write `scripts/install.sh` — `pip install -r requirements.txt` + register all skills to `~/.claude/skills/`
- [ ] Write `requirements.txt`:
  - `kuzu` — embedded graph database
  - `chromadb` — embedded vector store
  - `unstructured[pdf]` — PDF text extraction
  - `pdfplumber` — structured PDF table/layout parsing
  - `mcp` — MCP server SDK
  - `pytest` — eval runner
- [ ] Add `knowledge-graph/custom/` to `.gitignore`
- [ ] Write `docs/skill-registration.md` — step-by-step for Claude Code CLI and VS Code

### M1.2 — Kuzu Knowledge Graph Setup
- [ ] Write `knowledge-graph/schema/schema.py` — define all Kuzu node and relationship tables:
  - Node tables: `Component`, `PowerDomain`, `ClockSource`, `Register`, `Interrupt`, `FailureMode`
  - Relationship tables: `SUPPLIES`, `POWERS`, `CLOCKS`, `DEPENDS_ON_CLOCK`, `TRIGGERS`, `ROUTES_TO`, `TRANSLATES`, `STREAMS_TO`, `DMA_TO`, `SHARED_WITH`, `CAUSED_BY`, `AFFECTS_IF_REMOVED`
- [ ] Write `knowledge-graph/schema/init_db.py` — create Kuzu DB at `knowledge-graph/base/bsp_base.db`, apply schema
- [ ] Write `scripts/build_base_graph.py` — orchestrates full base graph rebuild from open-source seed scripts

### M1.3 — Open-Source Seed Knowledge Ingestion
Source documents: ARM public specs (GIC-600 TRM, AMBA AXI4 spec, CoreSight SoC-600 TRM, Cortex-A55/A720 TRM), Linux kernel documentation (`Documentation/power/`, `Documentation/scheduler/sched-energy.rst`), open GIC driver source.

- [ ] Write `knowledge-graph/base/arm-gic-600.py` — GIC-600 interrupt controller nodes: SPI/PPI/SGI/LPI types, ITS architecture, GICv4 virtual interrupt nodes
- [ ] Write `knowledge-graph/base/arm-amba-axi.py` — AMBA AXI4/AXI4-Stream bus topology, DMA-BUF interconnect nodes
- [ ] Write `knowledge-graph/base/linux-dvfs-eas.py` — Linux CPUFreq OPP model, EAS energy model nodes, C-state definitions from ACPI spec
- [ ] Write `knowledge-graph/base/common-failure-modes.py` — top 30 open-source documented BSP failure patterns (from LKML, Bootlin, Linaro reports)
- [ ] Write `knowledge-graph/custom/README.md` — instructions: how to add MTK/Qualcomm in-house nodes without touching base graph
- [ ] Verify: base graph has ≥ 500 nodes covering GIC, DVFS/EAS, AMBA, and common failure modes

### M1.4 — Document Ingestion Pipeline (for end-user custom knowledge)
- [ ] Write `mcp/tools/spec_extractor/pdf_ingest.py` — PDF → clean text blocks with page/section metadata
- [ ] Write `mcp/tools/spec_extractor/ipxact_parser.py` — Accellera IP-XACT XML → structured JSON (register address, bit fields, reset values, access type)
- [ ] Write `mcp/tools/spec_extractor/register_extractor.py` — heuristic register table extractor for non-IP-XACT PDFs
- [ ] Write `mcp/tools/spec_extractor/validate.py` — spot-check extracted register addresses against known-good values
- [ ] Write `scripts/ingest_custom.py` — CLI entry point: `python ingest_custom.py --input /path/to/TRM.pdf --soc mt6989`

### M1.5 — Kuzu GraphRAG Query Templates
- [ ] Write `knowledge-graph/queries/power_chain.py` — trace supply path: PMIC → PowerDomain → Component
- [ ] Write `knowledge-graph/queries/cross_domain_failure.py` — multi-hop: FailureMode symptom → PowerDomain → thermal → ClockSource violation
- [ ] Write `knowledge-graph/queries/interrupt_path.py` — IRQ source → GIC-600 → ITS → vCPU target
- [ ] Write `knowledge-graph/queries/isp_pipeline.py` — sensor → ISP → DMA-BUF → GPU/NPU data path
- [ ] Benchmark: all four query templates complete in < 500 ms on base graph

### M1.6 — MCP Local Tool Server Setup
- [ ] Write `mcp/server.py` — MCP server binding to `localhost` only, exposes graph query tools and log parsers
- [ ] Write `docs/mcp-setup.md` — how to launch MCP server and configure Claude Code to connect to it
- [ ] Verify: MCP server has zero outbound network calls; all data stays local

**Phase 1 Exit Criteria:**
- [ ] `scripts/install.sh` completes on a clean machine with no server dependencies
- [ ] Base graph ≥ 500 nodes, ≥ 4 domains (GIC, DVFS/EAS, AMBA, failure modes)
- [ ] All four GraphRAG query templates return correct results on test inputs
- [ ] MCP server starts and responds to skill tool calls locally

---

## Phase 2 — Domain Expert Skill Development
**Duration:** Month 3–4 (2026-05-10 → 2026-07-04)
**Goal:** Six domain skills, each grounded in the base knowledge graph, with validated tool-calling via MCP.
**Principle:** All six skills are developed in parallel. Knowledge anchors in `skill.md` must reference open-source specs (ARM TRM section numbers, Linux kernel doc paths) — no proprietary assumptions.

### M2.1 — `power-thermal-expert`
- [ ] Write `skills/power-thermal-expert/skill.md` — anchor to: P=αCV²f (ARM DynamIQ power model), Linux EAS energy model (`sched-energy.rst`), ACPI C-state spec, LPDDR5 JEDEC JESD79-5 deep sleep timing
- [ ] Write `mcp/tools/log_parsers/ftrace_parser.py` — extract C-state residency distribution from `trace-cmd` output
- [ ] Write `mcp/tools/log_parsers/perf_parser.py` — parse `perf stat` output, compute IPC per CPU cluster
- [ ] Write `mcp/tools/log_parsers/thermal_parser.py` — extract thermal throttling events from `dmesg` / `thermal_exynos` / `thermal_mediatek` drivers
- [ ] Write `mcp/tools/log_parsers/dvfs_opp_calc.py` — given OPP table (freq, voltage), compute Perf/Watt efficiency frontier
- [ ] Register `power-thermal-expert` as MCP tool: `analyze_cstate_residency`, `compute_dvfs_efficiency`, `parse_thermal_events`
- [ ] Write ≥ 30 eval cases: DVFS misconfiguration, C-state stuck, LPDDR5 deep sleep failure, EAS calibration drift, PMIC transient response

### M2.2 — `boot-debug-expert`
- [ ] Write `skills/boot-debug-expert/skill.md` — anchor to: ARM CoreSight SoC-600 TRM (ADIv6), AMBA APB power sequencing spec, ARM Cortex-A latch-up prevention guidelines
- [ ] Write `mcp/tools/log_parsers/pmic_log_parser.py` — extract voltage rail ramp events and sequence violations from kernel PMIC driver logs
- [ ] Write `mcp/tools/log_parsers/pll_checker.py` — detect premature clock consumer access before PLL lock from `clk` debug logs
- [ ] Write `mcp/tools/log_parsers/power_island_scanner.py` — detect zombie power island states from `pm_domain` debug output
- [ ] Write ≥ 30 eval cases: wrong supply order (VDD_IO before VDD_CORE), premature PLL access, isolation cell clamp mismatch, ADIv6 QDENY stuck, CoreSight trace link failure

### M2.3 — `multimedia-camera-expert`
- [ ] Write `skills/multimedia-camera-expert/skill.md` — anchor to: Linux V4L2 spec (`Documentation/userspace-api/media/`), DMA-BUF kernel docs, F2FS kernel documentation, MIPI CSI-2 open spec
- [ ] Write `mcp/tools/log_parsers/v4l2_stats_parser.py` — parse V4L2 buffer queue depth and overflow events from `v4l2-ctl --stream-mmap` output
- [ ] Write `mcp/tools/log_parsers/emmc_io_parser.py` — detect F2FS GC and checkpoint stalls from `iostat -x` and `/sys/kernel/debug/f2fs/`
- [ ] Write `mcp/tools/log_parsers/camera_hal_error_decoder.py` — decode Android Camera HAL3 error codes from logcat (covers ≥ 100 AOSP-documented errors)
- [ ] Write ≥ 30 eval cases: camera open fail (I2C timeout, MIPI bandwidth, PMIC sequence), preview stutter (DMA buffer starvation, thermal throttle), recording dropout (F2FS GC), ISP pipeline stall

### M2.4 — `gpu-rendering-expert`
- [ ] Write `skills/gpu-rendering-expert/skill.md` — anchor to: Android GPU Inspector documentation, Perfetto GPU counter docs, OpenGL ES 3.x spec (Depth Pre-pass, fragment discard), Vulkan spec (render pass optimization)
- [ ] Write `mcp/tools/log_parsers/perfetto_gpu_parser.py` — extract GPU task timeline, memory bandwidth counters, thermal throttling events from Perfetto JSON trace
- [ ] Write `mcp/tools/log_parsers/agp_parser.py` — parse Android GPU Inspector `.agi` export: Draw Call count, Overdraw ratio, Fragment Shader ALU utilization
- [ ] Write ≥ 30 eval cases: Overdraw > 3x, Draw Call CPU bottleneck, Fragment Shader memory bandwidth bound, GPU thermal throttle during sustained render

### M2.5 — `interrupt-virtualization-expert`
- [ ] Write `skills/interrupt-virtualization-expert/skill.md` — anchor to: ARM GIC-600 TRM (publicly available), ARM GICv3/v4 Architecture Specification, Linux `irq` subsystem docs, KVM ARM vGIC documentation
- [ ] Write `mcp/tools/log_parsers/irq_stat_parser.py` — parse `/proc/interrupts` snapshots, detect interrupt storm (> 10k/s sustained), per-CPU imbalance
- [ ] Write `mcp/tools/log_parsers/vm_exit_counter.py` — extract VM Exit frequency per interrupt source from KVM perf events (`kvm:kvm_exit`)
- [ ] Write `mcp/tools/log_parsers/its_validator.py` — validate ITS EventID→IntID→target CPU consistency from GIC debug registers dump
- [ ] Write ≥ 30 eval cases: List Register overflow (GICv3), ITS table corruption, VM Exit storm, SGI cross-core delivery latency regression, GICv4 direct injection path failure

### M2.6 — `hardware-spec-extractor`
- [ ] Write `skills/hardware-spec-extractor/skill.md` — guides user through spec ingestion workflow: which files to provide, what the tool will extract, how to verify output before graph injection
- [ ] Extend `mcp/tools/spec_extractor/ipxact_parser.py` to support Accellera IP-XACT 2022 standard (component/design/busInterface hierarchy)
- [ ] Write `mcp/tools/spec_extractor/graph_diff_writer.py` — idempotent Kuzu write: only insert new/changed nodes, skip existing
- [ ] Write output validation: JSON schema check on extracted register definitions before any graph write
- [ ] Write ≥ 30 eval cases: IP-XACT round-trip accuracy, malformed XML recovery, duplicate register detection, multi-peripheral batch import

### M2.7 — Tool Safety Framework
- [ ] Write `mcp/tools/safety_gate.py` — classify every MCP tool call: `READ_ONLY` / `CONFIG` / `DESTRUCTIVE`
- [ ] Enforce in MCP server: `DESTRUCTIVE` tools refuse execution unless `requires_human_approval: true` is set and acknowledged
- [ ] Write pytest unit tests for safety gate covering all three risk levels and boundary cases

**Phase 2 Exit Criteria:**
- [ ] Each skill registered and invocable via `/skill-name` in Claude Code CLI and VS Code
- [ ] Each skill passes ≥ 30 eval cases with human expert score ≥ 4/5
- [ ] MCP tool-calling success rate ≥ 90% (no parse errors, correct output format)
- [ ] Safety gate blocks all `DESTRUCTIVE` calls without approval flag

---

## Phase 3 — ITS Mentor Engine & Blackboard Integration
**Duration:** Month 5–6 (2026-07-05 → 2026-08-29)
**Goal:** Wire the six domain skills into a coordinated, teachable system using Claude Code's native sub-agent capability.

### M3.1 — `bsp-knowledge-mentor` Skill
- [ ] Write `skills/bsp-knowledge-mentor/skill.md` — full system prompt per Appendix 10.1 of dev plan
- [ ] Write `skills/bsp-knowledge-mentor/socratic-templates.yaml` — questioning sequences: symptom confirmation → resource state probe → hypothesis → tool verification
- [ ] Write `skills/bsp-knowledge-mentor/term-dictionary.yaml` — BSP physical ↔ business language ↔ algorithm metrics (bidirectional lookup, ≥ 100 term pairs covering power, multimedia, GPU, interrupt domains)
- [ ] Encode learner-level detection rules in `skill.md` (app / driver / algo / management keyword heuristics)
- [ ] Encode all prohibition rules: no direct fix scripts, no register addresses in non-technical context, no power domain shutdown without verified supply sequence

### M3.2 — Blackboard Multi-Agent Pattern (Claude Code Sub-agents)
- [ ] Implement Blackboard pattern using Claude Code's built-in sub-agent capability — `bsp-knowledge-mentor` spawns domain skill sub-agents, collects hypotheses, runs Arbiter convergence, synthesizes final report
- [ ] Write Blackboard session template (Markdown working document structure per Section 7.1 of dev plan)
- [ ] Implement Arbiter logic within `bsp-knowledge-mentor` prompt: keyword routing → sub-agent priority, confidence threshold for convergence
- [ ] Write `evals/blackboard_eval.py` — feed multi-domain crash log, verify root cause identified with ≥ 2 domain contributions
- [ ] Write end-to-end test: "30-minute recording random reboot" case requiring multimedia + power-thermal + gpu collaboration

### M3.3 — Terminology Translation
- [ ] Expand `term-dictionary.yaml` to cover ≥ 200 term pairs across all six domains
- [ ] Write `mcp/tools/term_translator/translate.py` — bidirectional lookup with context disambiguation, exposed as MCP tool
- [ ] Add translation capability directly into `bsp-knowledge-mentor` skill prompt — inline translation without requiring external bot or channel integration

### M3.4 — Business Impact Translation Engine
- [ ] Write `mcp/tools/impact_translator/bsp_to_business.py` — maps low-level metric deltas to commercial outcomes
  - Template: `{component} {metric} {delta}` → `{product} {user-experience} {delta}` → `vs competitor {X}%`
- [ ] Write impact rules covering: LPDDR5 leakage → battery life, DVFS OPP shift → sustained performance, ISP latency → camera UX, eMMC throughput → recording reliability, GPU throttle → frame rate consistency
- [ ] Expose as MCP tool: `translate_to_business_impact(component, metric, delta, product_type)`

### M3.5 — Cross-Domain Evaluation
- [ ] Write ≥ 20 multi-domain eval cases (each requiring ≥ 3 skill contributions, drawn from open LKML bug reports and Linaro case studies)
- [ ] Extend `evals/run_evals.py` to support Blackboard session replay and accuracy scoring
- [ ] A/B comparison: mentor-guided Blackboard mode vs direct single-skill invocation on same complex cases

**Phase 3 Exit Criteria:**
- [ ] Cross-domain complex case diagnosis accuracy ≥ 75% (expert blind review)
- [ ] Mentor skill correctly identifies learner level in ≥ 90% of test prompts
- [ ] Terminology translation covers ≥ 200 term pairs, ≥ 85% accuracy on test set
- [ ] Blackboard convergence tested on ≥ 20 multi-domain cases without infinite loop

---

## Phase 4 — Knowledge Evolution & User Extensibility
**Duration:** Month 7+ (2026-08-30 onwards)
**Goal:** Users can grow the knowledge graph from their real casework; base graph stays current with open-source evolution.

### M4.1 — Knowledge Sedimentation CLI
- [ ] Write `scripts/ingest_custom.py` — full CLI: parse engineer post-mortem reports (Markdown / plain text) → extract symptom/cause/resolution → write to `knowledge-graph/custom/` as new `FailureMode` nodes
- [ ] Implement Kuzu graph versioning: tag each ingest with date, source file hash, SoC tag
- [ ] Write knowledge gap detector: query topology regions with few `FailureMode` nodes, print coverage report

### M4.2 — Business Impact Report Template
- [ ] Write `templates/optimization-report.md` — structured report template with mandatory business impact section
- [ ] Write `mcp/tools/impact_translator/report_generator.py` — auto-fill business impact section given optimization metrics
- [ ] Validate: ≥ 10 sample reports generated, each with non-empty business impact paragraph

### M4.3 — CI/CD Integration Templates
- [ ] Write `templates/ci-integration/github-actions.yaml` — workflow template: AI-suggested DTS change → build → test → result comment on PR
- [ ] Write `templates/ci-integration/jenkins-pipeline.groovy` — Jenkins reference pipeline (users adapt to their LAVA setup)
- [ ] Write `docs/ci-integration.md` — step-by-step guide for connecting repo to user's CI system

### M4.4 — Base Graph Maintenance
- [ ] Write `scripts/update_base_graph.sh` — fetch latest ARM public spec release notes, flag changed sections for manual review
- [ ] Write `evals/regression_runner.py` — re-run all Phase 2 + 3 eval cases against current graph, report accuracy drift
- [ ] Set up GitHub Actions in this repo: weekly eval regression run on base graph

**Phase 4 Exit Criteria:**
- [ ] `ingest_custom.py` converts a plain-text post-mortem to graph nodes in < 5 minutes
- [ ] 100% of generated optimization reports include business impact translation
- [ ] CI/CD templates pass end-to-end test in GitHub Actions
- [ ] Weekly eval regression runner catches accuracy drops > 5%

---

## Dependency Map

```
M1.1 (scaffold, install.sh, requirements.txt)
  └─► M1.2 (Kuzu schema + init_db)
        └─► M1.3 (open-source seed ingestion)
              └─► M1.5 (GraphRAG query templates)
  └─► M1.4 (custom doc ingestion pipeline)
  └─► M1.6 (MCP server setup)

[Phase 1 complete — base graph live, MCP server running]
  └─► M2.1–M2.6 (domain skills, all parallel)
        └─► M2.7 (safety framework, shared dependency)

[Phase 2 complete — 6 skills registered and validated]
  └─► M3.1 (bsp-knowledge-mentor skill)
        └─► M3.2 (blackboard sub-agent pattern)
  └─► M3.3 (terminology translation)
  └─► M3.4 (business impact engine)
        └─► M3.5 (cross-domain evals)

[Phase 3 complete — full mentor system working]
  └─► M4.1 (knowledge sedimentation CLI)
  └─► M4.2 (report template + generator)
  └─► M4.3 (CI/CD templates)
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
| Install friction (server deps required) | 0 | 0 | 0 | 0 |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-14 | GraphRAG over pure vector RAG | Hardware topology is causal; vector search loses multi-hop dependency chains (PMIC → PowerDomain → CPU → Clock) |
| 2026-03-14 | Phase 1 before Phase 2 | Skills without grounded knowledge graph produce unverifiable hardware claims |
| 2026-03-14 | Kuzu (embedded) instead of Neo4j | Neo4j requires a server; corporate IT commonly blocks self-hosted DBs. Kuzu is Cypher-compatible, embeds in-process, installs via pip |
| 2026-03-14 | ChromaDB (embedded) instead of Qdrant | Same reason as Kuzu — zero server footprint, pip installable |
| 2026-03-14 | Claude Code sub-agents instead of LangGraph | Skills are Claude Code native; sub-agent pattern achieves Blackboard coordination without an external framework dependency |
| 2026-03-14 | Open-source knowledge only in base graph | Skills are for MTK/Qualcomm BSP engineers; their in-house SoC TRMs are proprietary. Base stays open; custom/ layer is user-managed and gitignored |
| 2026-03-14 | CI/CD as templates, not in-repo execution | User CI environments (Jenkins + LAVA) are company-internal; this repo provides reference templates only |

---

*Roadmap v1.1 — reflects zero-server architecture, Claude Code skill format, Kuzu embedded graph, and open-source-first knowledge strategy.*
