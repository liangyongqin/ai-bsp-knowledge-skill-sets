# BSP Knowledge Skill Sets

BSP engineers spend enormous amounts of time hunting through TRMs, re-explaining the same hardware failure to colleagues in other teams, and watching new engineers repeat the same debugging mistakes. There is no shared mental model, and there is no fast path from "symptom in dmesg" to "root cause in the power tree."

This project is seven Claude Code skills that guide BSP engineers through hardware diagnostics using Socratic questioning. The skills are grounded in a local knowledge graph built from ARM public TRMs, AMBA specs, and Linux kernel documentation — 501 nodes covering power domains, clock trees, interrupt routing, ISP pipelines, and common failure modes. No cloud database, no Docker, no IT approval required.

---

> **Alpha software.** Expect rough edges. Skill responses have not yet passed formal human expert review.
>
> Works best with the Claude Code CLI or the VS Code extension with Claude Code.
>
> Without proprietary SoC data: all reasoning uses the 501-node base graph drawn from ARM and Linux open-source specs. Responses will be architecturally correct but not SoC-specific until you add your in-house TRM (see [Adding your SoC data](#adding-your-soc-data)).
>
> Report issues at the GitHub Issues tab.

---

## Architecture

```
Layer 3: /bsp-knowledge-mentor       — ITS teaching engine, Blackboard coordinator
Layer 2: /power-thermal-expert       — DVFS, EAS, PMIC, C-states, LPDDR5, STR/STD
         /boot-debug-expert          — Power sequencing, PLL, CoreSight ADIv6
         /multimedia-camera-expert   — ISP, V4L2, DMA-BUF, MIPI CSI-2, eMMC
         /gpu-rendering-expert       — Render pipeline, Overdraw, Perfetto, Vulkan
         /interrupt-virtualization-expert — GIC-600, ITS, GICv4, KVM
         /hardware-spec-extractor    — IP-XACT 2022, PDF register map ingestion
Layer 1: Knowledge graph (Kuzu, embedded) + MCP tool server (local stdio)
         501 nodes from ARM TRMs, AMBA specs, Linux kernel Documentation/
```

The knowledge graph (Layer 1) runs in-process via Kuzu — no server, no daemon. The MCP tool server runs as a local stdio process and is optional for basic skill use.

---

## Prerequisites

- Python >= 3.11
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`) or VS Code with the Claude Code extension
- git
- No Docker, no external database, no cloud services required

---

## Quickstart

```bash
git clone <repo-url>
cd ai-bsp-knowledge-skill-sets
pip install -r requirements.txt
python scripts/build_base_graph.py      # builds 501-node base graph (~2 min)
bash scripts/install.sh                 # registers all 7 skills in ~/.claude/skills/
```

Then open Claude Code CLI or the VS Code panel and try:

```
/power-thermal-expert   My big cluster is capping at OPP-3 under sustained load even though temperature is fine. How do I debug this?

/bsp-knowledge-mentor   We have a random reboot after 30 minutes of video recording. Here is the dmesg: [paste log]

/boot-debug-expert      System hangs during cold boot. PMIC log shows VDD_CORE comes up but VDD_IO never follows.
```

Skills are registered as symlinks, so edits to `skills/*/skill.md` take effect immediately without re-running `install.sh`.

To register skills at project level instead of user level:

```bash
bash scripts/install.sh --project   # registers to .claude/skills/ in the repo root
```

---

## MCP tool server (optional)

The MCP server exposes graph query tools and log parsers to the skills. Run it in a separate terminal before starting Claude Code:

```bash
python mcp/server.py
```

Run this from the repo root — not from inside `mcp/`. Then configure Claude Code to connect to it. See [docs/mcp-setup.md](docs/mcp-setup.md) for the full configuration steps.

---

## Adding your SoC data

Without proprietary data the skills reason over open-source BSP patterns, which are architecturally representative but not SoC-specific. To add your in-house TRM:

```bash
# Run this inside your company network only — never commit the output to git
python scripts/ingest_custom.py --input /path/to/TRM.pdf --soc mt6989
```

The output writes to `knowledge-graph/custom/`, which is gitignored. Your proprietary register maps and power sequences never enter git history. See [docs/custom-knowledge.md](docs/custom-knowledge.md) for supported formats and options.

---

## Skills reference

| Skill | Invoke | Domain |
|---|---|---|
| `bsp-knowledge-mentor` | `/bsp-knowledge-mentor` | Entry point — Socratic teaching, Blackboard coordinator, terminology translation |
| `power-thermal-expert` | `/power-thermal-expert` | DVFS, EAS, C-states, PMIC, LPDDR5, STR/STD |
| `boot-debug-expert` | `/boot-debug-expert` | Power sequencing, PLL lock, CoreSight ADIv6, power islands |
| `multimedia-camera-expert` | `/multimedia-camera-expert` | ISP pipeline, V4L2, DMA-BUF, MIPI CSI-2, eMMC/F2FS |
| `gpu-rendering-expert` | `/gpu-rendering-expert` | Render pipeline, Overdraw, Draw Call, Perfetto GPU, Vulkan |
| `interrupt-virtualization-expert` | `/interrupt-virtualization-expert` | GIC-600, ITS, GICv4 virtual injection, KVM ARM vGIC |
| `hardware-spec-extractor` | `/hardware-spec-extractor` | IP-XACT 2022 parsing, PDF register extraction, graph diff |

---

## Running tests

```bash
pytest tests/test_safety_gate.py -v            # 82 safety gate tests
pytest tests/test_mcp_integration.py -v        # 54 tool integration tests
pytest evals/blackboard_eval.py -v             # 15 Blackboard structural tests
pytest evals/run_evals.py -v                   # 200 eval case schema validation
```

---

## Security and data sovereignty

- All inference runs locally via Claude Code — no BSP data is sent to third-party servers beyond Anthropic's API
- `knowledge-graph/custom/` is gitignored — proprietary SoC data never enters git history
- The MCP server binds to 127.0.0.1 only — no external network exposure
- DESTRUCTIVE tools require an explicit human approval flag and will refuse to run without it

---

## Documentation

- [Skill Registration](docs/skill-registration.md)
- [MCP Server Setup](docs/mcp-setup.md)
- [Adding Custom Knowledge](docs/custom-knowledge.md)
- [Development Roadmap](ROADMAP.md)
- [Architecture and Design](BSP_KNOWLEDGE_SKILL_SET_DEV_PLAN.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Alpha testers: the most valuable contribution is using a skill on a real BSP problem and opening an issue describing what the response got right and wrong.
