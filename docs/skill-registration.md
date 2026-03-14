# Skill Registration — Claude Code CLI and VS Code

This guide explains how to register BSP Knowledge Skills so they are available as
`/skill-name` commands inside **Claude Code CLI** and the **Claude Code VS Code extension**.

---

## Quick Start

Run the installer script from the repository root. It installs Python dependencies **and**
registers all skills in one step:

```bash
bash scripts/install.sh              # user-level: ~/.claude/skills/
# or
bash scripts/install.sh --project   # project-level: .claude/skills/
```

---

## Manual Registration

### User-level registration (recommended for personal workstations)

Skills registered here are available in **every** Claude Code session, regardless of which
project directory is open.

```bash
# Create the skills directory if it does not exist
mkdir -p ~/.claude/skills

# Symlink each skill (symlinks mean edits to source are reflected immediately)
ln -sf "$(pwd)/skills/bsp-knowledge-mentor/skill.md" ~/.claude/skills/bsp-knowledge-mentor.md
ln -sf "$(pwd)/skills/power-thermal-expert/skill.md" ~/.claude/skills/power-thermal-expert.md
ln -sf "$(pwd)/skills/boot-debug-expert/skill.md" ~/.claude/skills/boot-debug-expert.md
ln -sf "$(pwd)/skills/multimedia-camera-expert/skill.md" ~/.claude/skills/multimedia-camera-expert.md
ln -sf "$(pwd)/skills/gpu-rendering-expert/skill.md" ~/.claude/skills/gpu-rendering-expert.md
ln -sf "$(pwd)/skills/interrupt-virtualization-expert/skill.md" ~/.claude/skills/interrupt-virtualization-expert.md
ln -sf "$(pwd)/skills/hardware-spec-extractor/skill.md" ~/.claude/skills/hardware-spec-extractor.md
```

### Project-level registration (recommended for team repos)

Skills registered here are available **only when Claude Code is opened inside this
repository**. Commit `.claude/skills/` to share them with the whole team.

```bash
mkdir -p .claude/skills

ln -sf "../../skills/bsp-knowledge-mentor/skill.md"            .claude/skills/bsp-knowledge-mentor.md
ln -sf "../../skills/power-thermal-expert/skill.md"             .claude/skills/power-thermal-expert.md
ln -sf "../../skills/boot-debug-expert/skill.md"                .claude/skills/boot-debug-expert.md
ln -sf "../../skills/multimedia-camera-expert/skill.md"         .claude/skills/multimedia-camera-expert.md
ln -sf "../../skills/gpu-rendering-expert/skill.md"             .claude/skills/gpu-rendering-expert.md
ln -sf "../../skills/interrupt-virtualization-expert/skill.md"  .claude/skills/interrupt-virtualization-expert.md
ln -sf "../../skills/hardware-spec-extractor/skill.md"          .claude/skills/hardware-spec-extractor.md
```

---

## Verifying Registration

### Claude Code CLI

Start a Claude Code session and type `/` — all registered skills appear in the autocomplete
list. Invoke one with:

```
/bsp-knowledge-mentor I have a thermal shutdown at 85 °C during camera recording
```

### VS Code Extension

1. Open the repository in VS Code with the **Claude Code** extension installed.
2. Open the Claude Code side panel (Ctrl+Shift+P → *Claude Code: Open Panel*).
3. In the chat input, type `/` to see the skill list.
4. Select a skill or type its name, then describe your BSP problem.

---

## Skill Descriptions

| Skill | Invocation | Purpose |
|---|---|---|
| `bsp-knowledge-mentor` | `/bsp-knowledge-mentor` | Top-level entry point; Socratic teaching engine and Blackboard coordinator |
| `power-thermal-expert` | `/power-thermal-expert` | DVFS, EAS, PMIC, C-states, LPDDR5 thermal analysis |
| `boot-debug-expert` | `/boot-debug-expert` | Power sequencing, PLL lock, CoreSight ADIv6 debug |
| `multimedia-camera-expert` | `/multimedia-camera-expert` | ISP pipeline, V4L2, DMA-BUF, F2FS, MIPI CSI-2 |
| `gpu-rendering-expert` | `/gpu-rendering-expert` | GPU render pipeline, Overdraw, Draw Call profiling |
| `interrupt-virtualization-expert` | `/interrupt-virtualization-expert` | GIC-600, ITS, GICv4 virtual interrupt injection |
| `hardware-spec-extractor` | `/hardware-spec-extractor` | IP-XACT and PDF register map ingestion |

---

## Troubleshooting

### Skill does not appear in autocomplete

- Check that the target `skill.md` file exists: `ls skills/<name>/skill.md`
- Confirm the symlink is valid: `ls -la ~/.claude/skills/<name>.md`
- Reload the Claude Code session after registering new skills.

### Permission denied on `scripts/install.sh`

```bash
chmod +x scripts/install.sh
bash scripts/install.sh
```

### Python dependency installation fails

Ensure you are using Python ≥ 3.11 and pip is up to date:

```bash
python --version  # should print 3.11.x or newer
pip install --upgrade pip
bash scripts/install.sh
```

---

## Related Documentation

- [Custom Knowledge](custom-knowledge.md) — how to add proprietary SoC data
- [MCP Server Setup](mcp-setup.md) — how to configure the local tool server
