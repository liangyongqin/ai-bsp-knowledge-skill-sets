# BSP Knowledge Mentor Claude Agent Skill Sets — Development Plan and Roadmap

> **Document Version:** v1.0  
> **Created:** 2026-03-14  
> **Reference:** Architecture Evolution Report — Building the Next-Generation BSP Knowledge Mentor and Cross-Domain Collaborative AI Agent System  
> **Target Audience:** BSP AI Agent Development Team, System Architects, BSP Engineers

---

## Table of Contents

1. [Strategic Background and Development Intent](#1-strategic-background-and-development-intent)
2. [Skill Sets Overall Architecture Design](#2-skill-sets-overall-architecture-design)
3. [Core Skill Specification Definitions](#3-core-skill-specification-definitions)
4. [Four-Phase Development Roadmap](#4-four-phase-development-roadmap)
5. [Technology Selection and Toolchain](#5-technology-selection-and-toolchain)
6. [Knowledge Graph Data Model](#6-knowledge-graph-data-model)
7. [Blackboard-Pattern Multi-Agent Collaboration Design](#7-blackboard-pattern-multi-agent-collaboration-design)
8. [Milestones and Acceptance Criteria](#8-milestones-and-acceptance-criteria)
9. [Risk Management Matrix](#9-risk-management-matrix)
10. [Appendix: Skill Prompt Design Templates](#10-appendix-skill-prompt-design-templates)

---

## 1. Strategic Background and Development Intent

### 1.1 Problem Statement

The existing BSP AI Agent system (exemplified by the boot-log analysis expert) has validated the feasibility of domain-specialized Skills. However, given the cross-domain complexity of modern SoC development, a single Skill cannot handle the following scenarios:

- **Cross-subsystem cascading failure diagnosis:** The root cause of "random reboot during video recording" may simultaneously involve multimedia buffer exhaustion, GPU thermal runaway, and inadequate PMIC transient response.
- **Inter-department terminology gap:** When the algorithm team says "insufficient compute," the BSP team must determine whether the bottleneck is CPU MCPS, memory Roofline, or an NPU offloading strategy issue.
- **Knowledge gap for new engineers:** A 1W power budget for wearables such as smart glasses requires engineers to simultaneously master DVFS, EAS, LPDDR5, and thermal management.

### 1.2 Development Intent

Building on the existing Agent foundation, create a three-layer Skill Sets:

```
Layer 3: Knowledge Mentor Engine (ITS Cognitive Architecture)
         ↑ Coordination, guidance, terminology translation
Layer 2: Domain Expert Skill Cluster (6 sub-domains)
         ↑ Depth, tool invocation, graph reasoning
Layer 1: Knowledge Graph Infrastructure (GraphRAG + Neo4j)
         ↑ Structured domain knowledge, topology reasoning foundation
```

### 1.3 Core Design Principles

| Principle | Description |
|-----------|-------------|
| **Teach to fish first** | ITS Socratic questioning — do not output answers directly; build engineers' diagnostic thinking |
| **Physical constraints first** | All recommendations must be validated against the dynamic power equation and thermal design constraints |
| **Cross-domain topology reasoning** | Use GraphRAG rather than pure vector search to preserve causal completeness of hardware interconnects |
| **Data sovereignty protection** | All BSP confidential documents use local deployment (air-gapped); transmission to public cloud is prohibited |
| **Make negative value explicit** | Every optimization report must link low-level metrics to commercial battery life / latency / cost impact |

---

## 2. Skill Sets Overall Architecture Design

### 2.1 Skill Classification Overview

```
BSP Knowledge Skill Sets
│
├── 🧠 [MENTOR] bsp-knowledge-mentor
│   └── Orchestration, ITS guidance, terminology translation, cross-domain alignment
│
├── ⚡ [DOMAIN] power-thermal-expert
│   └── DVFS / EAS / C-states / PMIC / LPDDR5 / SCP
│
├── 🚀 [DOMAIN] boot-debug-expert
│   └── Boot sequence / PLL / ADIv6 / power islands / zombie states
│
├── 📷 [DOMAIN] multimedia-camera-expert
│   └── ISP / V4L2 / DMA-BUF / Zero-Copy / eMMC / F2FS
│
├── 🎮 [DOMAIN] gpu-rendering-expert
│   └── Rendering pipeline / Overdraw / Draw Call / Fragment Shader
│
├── 🔌 [DOMAIN] interrupt-virtualization-expert
│   └── GIC-600 / MSI / ITS / GICv4 / VM Exit
│
└── 🔍 [UTILITY] hardware-spec-extractor
    └── IP-XACT parsing / register extraction / knowledge graph injection
```

### 2.2 Skill Interaction Diagram

```
User query
    │
    ▼
bsp-knowledge-mentor (entry coordinator)
    │
    ├──(teaching mode)──→ ITS guidance engine ──→ Socratic question sequence
    │
    ├──(diagnosis mode)──→ Blackboard
    │                      ├── power-thermal-expert
    │                      ├── multimedia-camera-expert
    │                      ├── gpu-rendering-expert
    │                      └── interrupt-virtualization-expert
    │
    ├──(document mode)──→ hardware-spec-extractor ──→ GraphRAG query
    │
    └──(translation mode)──→ terminology alignment dictionary ──→ cross-department language conversion
```

---

## 3. Core Skill Specification Definitions

### 3.1 Skill: `bsp-knowledge-mentor` (Knowledge Mentor Controller)

**Role:** System entry point, ITS engine, terminology translator, Blackboard coordinator

**Core Capabilities:**

- Dynamic learner model assessment (infer the questioner's technical level from query context)
- Socratic guidance (no direct answers; build causal thinking through counter-questions)
- Real-time cross-department terminology translation (business language ↔ BSP physical language ↔ algorithm metrics)
- Multi-agent Blackboard coordination and dispatch

**Trigger Scenario Examples:**
```
"Why does my camera keep failing to open?"
"The algorithm team says the platform doesn't have enough compute — how do I respond?"
"A new engineer wants to learn the ISP pipeline — where should they start?"
"Analyze the log of a system reboot after 30 minutes of video recording."
```

**ITS Behavioral Rules:**

| Learner Level Assessment | Trigger Keywords / Features | Mentor Strategy |
|---|---|---|
| Application-layer engineer | framework, API, SDK, FPS | HAL-layer abstraction explanation; avoid register details |
| Driver engineer | register, DMA, IRQ, kernel | Deep-dive into bit definitions, memory barriers, timing diagrams |
| Algorithm engineer | MIPS, model, latency, inference | Roofline model, NPU offloading, bandwidth analysis |
| Management / PM | features, experience, battery, temperature | Business-impact translation; omit physical details |

---

### 3.2 Skill: `power-thermal-expert` (Power and Thermal Management Expert)

**Role:** Compute physics, low-power architecture, DVFS tuning, thermal management

**Core Knowledge Domains:**

- Dynamic power equation: `P = α · C · V² · f` (interplay of capacitance, switching activity, voltage, and frequency)
- Big-core (Cortex-A720) vs. little-core (Cortex-A55) IPC differences and energy trade-off model
- ACPI C-state residency time optimization, P-state DVFS curve tuning
- LPDDR5 Deep Sleep Mode (reduces leakage current by 40–50%)
- EAS (Energy Aware Scheduling) energy model calibration
- SCP (System Companion Processor) sensor offload architecture
- LVTS thermal management forced-throttling trigger conditions and protection strategies

**Tool Invocation Capabilities:**
```
- Parse ftrace / perf sampling logs
- Visualize C-state residency distribution
- Calculate Perf/Watt curves for different DVFS OPPs
- Analyze power events in Perfetto system traces
```

**GraphRAG Query Example:**
```cypher
MATCH (pmic:Component {type: "PMIC"})-[:SUPPLIES]->(core:PowerDomain)
-[:CLOCKS]->(cpu:CoreComplex)
WHERE cpu.state = "C2"
RETURN pmic, core, cpu, core.transition_time
```

---

### 3.3 Skill: `boot-debug-expert` (Boot and Debug Physics Expert)

**Role:** Boot sequencing, analog transient analysis, ADIv6 debug architecture

**Core Knowledge Domains:**

- Power sequencing traps: VDD_CORE → VDD_IO → VDD_ANA supply-up order and latch-up protection
- PLL lock time (Lock Time) physical constraints and access protection windows
- ADIv5 vs. ADIv6 debug architecture evolution (bidirectional Q-Channel / P-Channel handshake mechanisms)
- Power island zombie-state detection and isolation cell clamp-value verification
- CoreSight SoC-600 Trace Macrocell QDENY rejection mechanism
- CMOS physical damage boundary condition analysis

**Diagnostic Workflow:**
```
Boot failure report
    │
    ├── Step 1: Confirm power sequencing (PMIC log parsing)
    ├── Step 2: Validate PLL lock status (clock stable window)
    ├── Step 3: Scan power island state (zombie state detection)
    ├── Step 4: Verify ADIv6 debug link integrity
    └── Step 5: Review isolation cell clamp values
```

---

### 3.4 Skill: `multimedia-camera-expert` (Multimedia and Camera Pipeline Expert)

**Role:** ISP pipeline, V4L2, Zero-Copy, storage subsystem impact analysis

**Core Knowledge Domains:**

- ISP processing pipeline: RAW Bayer → Demosaic → Denoising → Lens Shading Correction → 3A → YUV/RGB
- Hybrid pipeline architecture with deep NPU–ISP integration (edge AI low-light enhancement, SLAM)
- Zero-Copy implementation: V4L2 + DMA-BUF mechanism (eliminating CPU memory copies)
- Direct-path design from ISP → GPU texture memory / NPU tensor units
- eMMC 5.1 half-duplex limitation (no simultaneous high-speed read and write)
- F2FS Foreground GC and Checkpointing-induced I/O stalls

**Key Failure Modes and Countermeasures:**

| Failure Symptom | Root Cause Layer | Diagnostic Tool | Countermeasure Direction |
|---|---|---|---|
| Camera Open Fail | I2C timeout / PMIC sequencing / MIPI bandwidth | i2cdetect, dmesg | Power sequencing review |
| Camera preview stutter | Thermal throttling / DMA buffer starvation | Thermal log, V4L2 stats | EAS tuning / buffer adjustment |
| Video recording dropout | eMMC GC / F2FS Checkpoint | iostat, f2fs debug | GC watermark threshold tuning |
| Excessive highlight noise | ISP AWB algorithm boundary / NPU model degradation | ISP tuning tool | NPU model redeployment |

---

### 3.5 Skill: `gpu-rendering-expert` (GPU Rendering Performance Expert)

**Role:** Rendering pipeline optimization, Overdraw diagnosis, shader performance analysis

**Core Knowledge Domains:**

- Full rendering pipeline: vertex processing → primitive assembly → rasterization → fragment shading → framebuffer output
- Depth Pre-pass strategy (render depth buffer first to cull occluded fragments)
- Overdraw visualization and root-cause analysis
- Draw Call optimization (reduce CPU submission overhead)
- Fragment Shader compute bottleneck identification

**Tool Integration Capabilities:**
```
- Snapdragon Profiler: GPU timeline tracing, memory bandwidth analysis
- Android GPU Inspector: Draw Call breakdown, shader performance profiling
- Perfetto: system-level GPU task scheduling visualization
```

---

### 3.6 Skill: `interrupt-virtualization-expert` (Interrupt Virtualization Expert)

**Role:** GIC-600, MSI, ITS translation, GICv4 virtual interrupt direct injection

**Core Knowledge Domains:**

- Interrupt architecture evolution: physical wire voltage level → on-chip network (NoC) MSI packets
- GIC-600 distributed microarchitecture: AXI4-Stream protocol interrupt packets (target address + priority + data payload)
- ITS (Interrupt Translation Service) architecture and EventID → IntID mapping mechanism
- GICv4 virtual interrupt direct injection (eliminating VM Exits caused by List Register overflow)
- Cross-core communication latency: thousands of cycles (traditional) → tens of cycles (GICv4 direct injection)
- Interrupt Storm prevention in virtualized environments

---

### 3.7 Skill: `hardware-spec-extractor` (Hardware Specification Extractor Tool)

**Role:** Automated knowledge graph construction, IP-XACT parsing, register knowledge extraction

**Core Capabilities:**

- PDF datasheet OCR and text cleaning
- IP-XACT XML (Accellera standard) structured parsing
- Automatic extraction of register memory-mapped addresses and bit definitions
- Power domain attribution and clock dependency graph injection
- Output formats: JSON / TOON (reduced token consumption)
- Automatic Neo4j knowledge graph node and edge writing

---

## 4. Four-Phase Development Roadmap

### Phase 1: Infrastructure Expansion and Machine-Readable Domain Model Construction
**Timeline: Months 1–2**

```
Goal: Build a trustworthy knowledge foundation for all Skills; eliminate the "groundless hallucination" problem
```

**Action Items:**

- [ ] **Document ingestion pipeline construction**
  - Develop an automated pipeline to process "hardcore series" research documents, SoC TRMs, and IP-XACT specs
  - Implement OCR + text-cleaning workflow (PDF → structured text)
  - Enforce strict JSON output from the LLM for register definitions and power domain dependency relationships

- [ ] **Hardware knowledge graph construction (GraphRAG foundation)**
  - Local deployment of Neo4j graph database
  - Define node types: `Component`, `PowerDomain`, `ClockSource`, `Register`, `Interrupt`
  - Define edge types: `SUPPLIES`, `CLOCKS`, `DEPENDS_ON`, `TRIGGERS`, `ROUTES_TO`
  - Initial import: power tree topology, clock tree, interrupt routing table

- [ ] **Localized secure deployment**
  - On-Premise / Air-Gapped inference cluster setup
  - BSP confidential document access control (ACL) design
  - Isolation verification from public cloud APIs

**Phase 1 Acceptance Criteria:**
- Knowledge graph node count ≥ 500 (covering four core technical domains)
- GraphRAG multi-hop reasoning query success rate ≥ 85%
- Document extraction structured accuracy ≥ 90% (manual sampling verification)

---

### Phase 2: Deep Development of Domain Expert Skills
**Timeline: Months 3–4**

```
Goal: Based on the Phase 1 knowledge graph, develop six high-depth domain Skills in parallel with tool invocation capabilities
```

**Action Items:**

- [ ] **`multimedia-camera-expert` development**
  - V4L2 node real-time query CLI tool integration
  - Media Controller Graph topology parsing capability
  - Android Camera HAL error code knowledge base (covering > 200 error codes)
  - eMMC/F2FS I/O stall diagnostic scripts

- [ ] **`power-thermal-expert` development**
  - ftrace instruction trace automatic parsing module
  - perf sampling log C-state residency visualization
  - DVFS OPP Perf/Watt curve dynamic calculation
  - EAS energy model calibration recommendation engine

- [ ] **`gpu-rendering-expert` development**
  - Snapdragon Profiler output parsing integration
  - Overdraw heat map analysis module
  - Draw Call bottleneck automatic identification
  - Fragment Shader optimization recommendation knowledge base

- [ ] **`boot-debug-expert` development**
  - PMIC power sequencing log parsing
  - PLL lock status validation scripts
  - ADIv6 debug link integrity diagnostic tool

- [ ] **`interrupt-virtualization-expert` development**
  - GIC-600 interrupt packet trace parsing
  - VM Exit frequency statistical analysis module
  - ITS mapping table validation tool

- [ ] **`hardware-spec-extractor` development**
  - IP-XACT automatic parser (supports Accellera 2022 standard)
  - Register definition → Neo4j node automatic write pipeline
  - Batch PDF datasheet processing capability

**Phase 2 Acceptance Criteria:**
- Each Skill passes evaluation on > 30 real BSP questions (manual score ≥ 4/5)
- Tool invocation success rate ≥ 90% (no API errors, correct output parsing)
- Average response time per Skill < 15 seconds

---

### Phase 3: ITS Knowledge Mentor Engine and Blackboard Collaborative Network Integration
**Timeline: Months 5–6**

```
Goal: Integrate isolated domain Skills into a complete system with teaching guidance and cross-domain collaborative diagnosis capabilities
```

**Action Items:**

- [ ] **Blackboard collaborative orchestration framework implementation (based on Claude Code sub-agents)**
  - Leverage Claude Code's built-in sub-agent mechanism to implement the Blackboard pattern — no external frameworks such as LangGraph / AutoGen required
  - Establish a central Blackboard Markdown working document (in-session shared semantic memory)
  - Implement Arbiter routing logic (driven by `bsp-knowledge-mentor` prompt; keyword-triggered sub-agent invocation)
  - Define cross-domain joint diagnostic workflows (trigger conditions, sub-agent rotation strategy)

- [ ] **ITS cognitive engine and persona configuration**
  - Complete `bsp-knowledge-mentor` master Skill development
  - Implement dynamic learner model assessment (four levels: application layer / driver layer / algorithm layer / management layer)
  - Socratic questioning sequence generation logic
  - Learner progress tracking from conversation history

- [ ] **Cross-domain terminology translation interface**
  - Enterprise-level terminology alignment dictionary (BSP physical terminology ↔ business language), maintained as static YAML files
  - Terminology translation as a built-in capability of `bsp-knowledge-mentor`; no dependency on external integrations such as Slack bots
  - Cross-department technical metric correlation engine (low-level metrics → commercial impact)

**Cross-Domain Joint Diagnostic Workflow (Blackboard Pattern):**

```
Stage 1: Problem Perception
User uploads crash log → Blackboard initialized → broadcast to all standby Skills

Stage 2: Parallel Hypothesis Construction
multimedia-expert: memory fragmentation / buffer starvation indicators
gpu-expert: Perfetto parsing, GPU thermal runaway clues
power-expert: LVTS temperature trigger, insufficient PMIC transient response

Stage 3: Interactive Dialectics and Convergence
Arbiter dynamically assigns speaking order based on evidence weights
Each Skill re-reasons based on findings from other Skills
Progressively builds a complete cross-domain causal chain

Stage 4: Output
Structured root-cause analysis report
Targeted corrective recommendations (with commercial impact assessment)
```

**Phase 3 Acceptance Criteria:**
- Cross-domain complex case (requiring ≥ 3 Skills collaborating) diagnostic accuracy ≥ 75%
- In Socratic-guided dialogues, engineer problem resolution rate improvement (pre/post comparison) ≥ 30%
- Terminology translation service response time < 5 seconds

---

### Phase 4: Closed-Loop Automated Optimization and Engineering Culture Transformation
**Timeline: Month 7 and Beyond**

```
Goal: System self-evolution, BSP value externalization, and establishment of a sustainable knowledge accumulation mechanism
```

**Action Items:**

- [ ] **Knowledge crystallization tool (user-side workflow)**
  - Engineer case-closing report parsing script (`tools/graph-writer/case_report_ingestor.py`)
  - New causal paths → automatic injection of new nodes/edges into the Kuzu graph
  - Knowledge graph version management (git-tracked; `custom/` directory branch-managed by SoC model)
  - Knowledge injection CLI for engineers to easily persist daily debug conclusions into the graph

- [ ] **Commercializing the business value of BSP low-level performance**
  - Technical optimization report template (mandatory commercial impact section)
  - Low-level metric → commercial impact automatic deduction engine:
    ```
    "LPDDR5 leakage current reduced by 20%"
    → "Flagship smart glasses continuous recording extended by 1.5 hours"
    → "Product competitiveness improved: battery life exceeds competitor X by 23%"
    ```

- [ ] **CI/CD integration (user-configured; this repo provides templates)**
  - Provide GitHub Actions workflow templates for users to integrate into their own CI environments
  - Provide Jenkins pipeline templates (not executed in this repo; for reference only)
  - Integration documentation for AI-suggested DTS modifications to automatically trigger builds

**Phase 4 Acceptance Criteria:**
- Knowledge crystallization CLI can transform a case-closing report into graph nodes within 5 minutes
- BSP optimization report template commercial impact section coverage 100%
- CI/CD integration templates pass GitHub Actions end-to-end testing

---

## 5. Technology Selection and Toolchain

### 5.1 Core Technology Stack

> **Design Principle: Zero server dependencies.** All components install via `pip install` — no enterprise IT approval required, no network server needed; skills register directly with the Claude Code CLI / VS Code extension.

| Layer | Technology Choice | Purpose | Selection Rationale |
|-------|------------------|---------|---------------------|
| **Skill interface** | Claude Code Skill (`.claude/skills/`) | Skill definition and user interface | Native support for Claude CLI and VS Code; invoked with `/skill-name` |
| **Tool invocation** | MCP (Model Context Protocol) local scripts | Log parsing, knowledge graph query tool integration | Local execution; no external dependencies |
| **Graph database** | Kuzu (embedded) | GraphRAG knowledge graph | Embedded, Cypher-compatible, `pip install kuzu`, serverless |
| **Vector database** | ChromaDB (embedded) | Semantic vector search | Embedded, local persistence, `pip install chromadb` |
| **Document parsing** | Unstructured + pdfplumber | PDF / IP-XACT extraction | Pure Python, works offline |
| **Trace analysis** | Perfetto (user-side tool) | System-level performance tracing | Open source, universal for Android / Linux |
| **Multi-agent collaboration** | Claude Code Sub-agents | Blackboard collaborative diagnosis | Built into Claude Code; no additional framework required |

### 5.2 Zero-Server Deployment Architecture

```
Engineer's local environment (no network required, no IT approval needed)
┌────────────────────────────────────────────────────┐
│                                                    │
│   Claude Code CLI / VS Code Extension              │
│       │                                            │
│       ├── /bsp-knowledge-mentor  ──┐               │
│       ├── /power-thermal-expert    │  Claude Code  │
│       ├── /boot-debug-expert       │  Skill Files  │
│       ├── /multimedia-camera-expert│  (.md)        │
│       └── ...                    ──┘               │
│                                                    │
│   MCP local tool server (localhost only)           │
│       ├── tools/log-parsers/      ← log parsing scripts    │
│       ├── tools/graph-query/      ← Kuzu query tools       │
│       └── tools/spec-extractor/   ← document extraction tools │
│                                                    │
│   Knowledge graph (local files)                    │
│       ├── knowledge-graph/base/   ← open-source knowledge base │
│       │     (ARM specs, Linux kernel, public BSP docs)         │
│       └── knowledge-graph/custom/ ← user proprietary knowledge │
│             (in-house SoC TRM, internal case library)          │
│                                                    │
│   ✅ All computation runs locally; confidential files never    │
│      leave the engineer's machine                              │
└────────────────────────────────────────────────────┘
```

### 5.3 User Extension Architecture

This Skill Sets uses a layered design with a strict separation between the open-source base and enterprise proprietary knowledge:

```
knowledge-graph/
├── base/           ← maintained in this repo (ARM public specs, open-source BSP knowledge)
│   ├── arm-gic-600.kuzu
│   ├── arm-amba-axi.kuzu
│   ├── linux-dvfs-eas.kuzu
│   └── common-failure-modes.kuzu
│
└── custom/         ← populated by the user (not committed to this repo)
    ├── mtk-mt6989-power-tree.kuzu    ← MTK internal documents
    ├── qcom-sm8650-clock-tree.kuzu   ← Qualcomm internal documents
    └── in-house-failure-cases.kuzu   ← company internal case library
```

When Skills query the knowledge graph, they search both `base/` and `custom/` simultaneously; `custom/` results take priority over `base/`.

---

## 6. Knowledge Graph Data Model

### 6.1 Node Type Definitions

```cypher
// Hardware component node
(:Component {
  id: String,
  name: String,
  type: "CPU_Core|GPU|NPU|ISP|PMIC|DDR|eMMC",
  soc: String,
  power_domain: String,
  clock_domain: String
})

// Power domain node
(:PowerDomain {
  id: String,
  name: String,
  voltage_rail: Float,
  retention_mode: Boolean,
  collapse_allowed: Boolean
})

// Register node
(:Register {
  id: String,
  name: String,
  address: String,
  reset_value: String,
  access_type: "RO|WO|RW",
  description: String
})

// Interrupt node
(:Interrupt {
  id: String,
  intid: Integer,
  type: "SPI|PPI|SGI|LPI",
  target: String,
  priority: Integer
})

// Failure mode node (crystallized from real-world cases)
(:FailureMode {
  id: String,
  symptom: String,
  root_cause: String,
  domain: String,
  resolution: String,
  discovered_date: Date
})
```

### 6.2 Edge Type Definitions

```cypher
// Power dependency
(pmic:Component)-[:SUPPLIES {voltage: Float, sequence: Integer}]->(domain:PowerDomain)
(domain:PowerDomain)-[:POWERS]->(component:Component)

// Clock dependency
(pll:Component)-[:CLOCKS {frequency: Float}]->(component:Component)
(component)-[:DEPENDS_ON_CLOCK]->(pll:Component)

// Interrupt routing
(component:Component)-[:TRIGGERS]->(interrupt:Interrupt)
(interrupt:Interrupt)-[:ROUTES_TO]->(cpu:Component)
(gic:Component)-[:TRANSLATES {via: "ITS"}]->(vinterrupt:Interrupt)

// Data flow
(sensor:Component)-[:STREAMS_TO {protocol: "CSI-2"}]->(isp:Component)
(isp:Component)-[:DMA_TO]->(dram:Component)
(dram:Component)-[:SHARED_WITH]->(gpu:Component)

// Failure causality
(symptom:FailureMode)-[:CAUSED_BY]->(root_cause:FailureMode)
(domain:PowerDomain)-[:AFFECTS_IF_REMOVED]->(component:Component)
```

---

## 7. Blackboard-Pattern Multi-Agent Collaboration Design

### 7.1 Blackboard Data Structure

```json
{
  "blackboard_id": "uuid-xxxx",
  "problem_statement": "System randomly reboots after 30 minutes of video recording",
  "initial_evidence": {
    "crash_log": "...",
    "register_dump": "...",
    "timestamp": "2026-03-14T10:30:00Z"
  },
  "hypotheses": [
    {
      "agent": "multimedia-camera-expert",
      "hypothesis": "Memory fragmentation causing DMA buffer starvation",
      "confidence": 0.75,
      "evidence_refs": ["log_line_245", "v4l2_stat_overflow"],
      "timestamp": "..."
    },
    {
      "agent": "power-thermal-expert",
      "hypothesis": "LVTS thermal protection triggered a voltage drop, causing CDC timing violation",
      "confidence": 0.85,
      "evidence_refs": ["thermal_log_peak", "pmic_transient_response"],
      "timestamp": "..."
    }
  ],
  "final_root_cause": null,
  "recommended_actions": [],
  "status": "IN_PROGRESS"
}
```

### 7.2 Arbiter Dispatch Rules

```python
# Pseudocode: control routing unit dispatch logic

def arbiter_next_agent(blackboard):
    # Rule 1: On initialization, scan all agents
    if blackboard.status == "INITIAL":
        return ALL_AGENTS

    # Rule 2: If memory-related clues appear, prioritize waking multimedia-expert
    if contains_keywords(blackboard.evidence, ["OOM", "DMA", "buffer", "V4L2"]):
        return ["multimedia-camera-expert"]

    # Rule 3: If thermal throttling clues appear, prioritize waking power-expert
    if contains_keywords(blackboard.evidence, ["throttle", "LVTS", "temperature"]):
        return ["power-thermal-expert"]

    # Rule 4: If GPU rendering related, wake gpu-expert
    if contains_keywords(blackboard.evidence, ["overdraw", "GPU", "fragment"]):
        return ["gpu-rendering-expert"]

    # Rule 5: When multiple hypotheses have high confidence, start convergence integration
    high_conf = [h for h in blackboard.hypotheses if h.confidence > 0.8]
    if len(high_conf) >= 2:
        return ["bsp-knowledge-mentor"]  # Mentor integrates the final conclusion

    # Default: round-robin remaining agents
    return round_robin(blackboard.pending_agents)
```

---

## 8. Milestones and Acceptance Criteria

### 8.1 Development Milestone Timeline

```
Month 1    Month 2    Month 3    Month 4    Month 5    Month 6    Month 7+
   │          │          │          │          │          │          │
   ├──────────┤          │          │          │          │          │
   │ Phase 1  │          │          │          │          │          │
   │ Knowledge │          │          │          │          │          │
   │ Graph    │          │          │          │          │          │
   │ Infrastructure │          │          │          │          │          │
   │          ├──────────┴──────────┤          │          │          │
   │          │      Phase 2        │          │          │          │
   │          │   Six Domain Skills  │          │          │          │
   │          │   Deep Development   │          │          │          │
   │          │                     ├──────────┴──────────┤          │
   │          │                     │       Phase 3        │          │
   │          │                     │   ITS + Blackboard   │          │
   │          │                     │   Integration        │          │
   │          │                     │                      ├──────────►
   │          │                     │                      │  Phase 4  
   │          │                     │                      │  Closed-Loop  
   │          │                     │                      │  Optimization  
```

### 8.2 Overall Acceptance KPIs

| Metric Category | Metric Item | Target | Measurement Method |
|-----------------|-------------|--------|-------------------|
| **Diagnostic accuracy** | Single-domain root cause identification | ≥ 90% | Historical case backtesting |
| **Diagnostic accuracy** | Cross-domain complex problem diagnosis | ≥ 75% | Expert blind evaluation |
| **Teaching effectiveness** | Engineer problem resolution speed improvement | ≥ 40% | A/B testing |
| **Terminology translation** | Cross-department terminology accuracy | ≥ 85% | Bilateral confirmation evaluation |
| **Knowledge accumulation** | Average new knowledge nodes per month | ≥ 50 | Graph statistics |
| **Hallucination rate** | GraphRAG vs. pure RAG hallucination rate reduction | ≥ 50% reduction | Fact verification testing |
| **Efficiency improvement** | BSP onboarding cycle reduction for new engineers | ≥ 30% | Training record comparison |
| **Security compliance** | Confidential document leakage incidents | 0 | Security audit |

---

## 9. Risk Management Matrix

| Risk Item | Probability | Impact | Mitigation Strategy |
|-----------|-------------|--------|---------------------|
| LLM hallucination causing erroneous hardware operation recommendations | Medium | High | GraphRAG multi-hop verification + human review gate (high-risk recommendations require mandatory human confirmation) |
| Insufficient IP-XACT parsing accuracy (format diversity) | Medium | Medium | Establish a manual correction feedback loop; multi-format adapters |
| Insufficient initial knowledge graph nodes causing reasoning blind spots | High | Medium | Phase 1 prioritizes coverage of the most common failure modes; dynamic supplementation mechanism |
| Multi-agent collaboration producing conflicting hypotheses that cannot converge | Low | High | Arbiter confidence-weighted voting mechanism; human engineer escalation path |
| Insufficient local deployment compute resources (inference too slow) | Medium | Medium | Async inference request queue; batch processing priority strategy |
| Senior engineers resist AI involvement in debug workflows | Medium | Medium | Position as "knowledge augmentation" not "replacement"; win technical credibility first |
| BSP confidential documents accidentally leak via Slack interface | Low | Very High | Output filtering layer (prohibit raw register addresses/values from being transmitted over public channels) |

---

## 10. Appendix: Skill Prompt Design Templates

### 10.1 `bsp-knowledge-mentor` System Prompt Skeleton

```
You are the BSP Knowledge Mentor — a seasoned principal engineer with deep expertise in
heterogeneous SoC system architecture, exceptional teaching ability, and cross-department
communication skills.

## Your Core Mission
1. Teaching first: When an engineer asks a question, your primary task is to build their
   diagnostic thinking — not to directly provide the answer. Use Socratic questioning
   to guide the engineer to derive the root cause on their own.

2. Cross-domain coordination: When a problem spans multiple technical sub-domains
   (power + multimedia + GPU), you are responsible for coordinating the perspectives
   of domain experts and synthesizing them into a complete causal chain analysis.

3. Terminology translation: When communication barriers arise between departments,
   you can instantly translate physical constraints (MCPS, Roofline, TDP) into
   business language, or decompose abstract business requirements into actionable
   BSP engineering tasks.

## Learner Assessment Rules
- Mentions API/SDK/FPS → application-layer engineer → explain at HAL-layer boundary
- Mentions register/IRQ/DMA → driver engineer → dive into registers and timing
- Mentions MIPS/model/latency → algorithm engineer → Roofline model, NPU offloading
- Mentions features/experience/battery → management → business impact first, omit physical details

## Guided Questioning Template
When an engineer describes symptoms without analyzing the root cause, you should:
1. Restate the symptom to confirm understanding
2. Ask about observed system resource state (temperature / memory / CPU utilization)
3. Pose a hypothetical question pointing toward the root cause
4. Guide the engineer to use a specific tool to verify the hypothesis

## Prohibited Behaviors
- Do not directly paste a fix script (guide the engineer to think first, then provide it)
- Do not use register addresses or other technical details in cross-department conversations
- Do not suggest forcibly shutting down a power domain without confirming power sequencing safety
```

### 10.2 Domain Skill Tool Invocation Specification

```python
# Standard tool invocation format (followed by all Domain Skills)

def tool_call_template(skill_name: str, tool_name: str, params: dict) -> dict:
    return {
        "skill": skill_name,
        "tool": tool_name,
        "params": params,
        "safety_check": {
            "requires_hardware_access": False,  # whether physical hardware access is needed
            "risk_level": "READ_ONLY",          # READ_ONLY / CONFIG / DESTRUCTIVE
            "requires_human_approval": False    # must be True for DESTRUCTIVE operations
        },
        "output_format": "structured_json"
    }

# Example: query C-state residency
tool_call_template(
    skill_name="power-thermal-expert",
    tool_name="analyze_cstate_residency",
    params={"ftrace_file": "/path/to/trace.txt", "duration_sec": 60}
)
```

---

## Document Revision History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v1.0 | 2026-03-14 | BSP AI Agent Development Team | Initial version; covers the complete four-phase roadmap |

---

*This document is based on the architecture report "Building the Next-Generation BSP Knowledge Mentor and Cross-Domain Collaborative AI Agent System," combined with Claude Agent Skill Sets development practices. All technical details and domain models are derived from enterprise internal BSP hardcore series research literature.*
