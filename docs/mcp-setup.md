# MCP Local Tool Server — Setup Guide

The MCP (Model Context Protocol) server exposes graph query tools and log parsers to
Claude Code skills over a **localhost-only** connection.  No external network traffic
is required or permitted.

---

## Starting the server

```bash
# From the repository root (with dependencies installed):
python mcp/server.py
```

By default the server binds to `127.0.0.1` on port `3000`.  Override with environment
variables:

```bash
MCP_HOST=127.0.0.1 MCP_PORT=3000 python mcp/server.py
```

---

## Configuring Claude Code to connect

### Claude Code CLI

Add the server to your Claude Code configuration (`~/.claude/config.json` or
`.claude/config.json` for project-level):

```json
{
  "mcpServers": {
    "bsp-tools": {
      "command": "python",
      "args": ["mcp/server.py"],
      "cwd": "/path/to/ai-bsp-knowledge-skill-sets"
    }
  }
}
```

### VS Code Extension

1. Open VS Code Settings (Ctrl+,).
2. Search for **Claude Code MCP**.
3. Add a new server entry with the same `command`, `args`, and `cwd` as above.
4. Reload the window for the change to take effect.

---

## Available tool categories

| Category | Directory | Tools |
|---|---|---|
| Graph queries | `mcp/tools/graph_query/` | `query_power_chain`, `query_cross_domain`, `query_interrupt_path`, `query_isp_pipeline` |
| Log parsers | `mcp/tools/log_parsers/` | `parse_ftrace`, `parse_perf`, `parse_thermal`, `parse_dmesg`, `parse_v4l2`, `parse_pmic`, `parse_irq` |
| Spec extractors | `mcp/tools/spec_extractor/` | `ingest_pdf`, `parse_ipxact`, `extract_registers`, `validate_registers` |
| Term translator | `mcp/tools/term_translator/` | `translate_term` |
| Impact translator | `mcp/tools/impact_translator/` | `translate_to_business_impact` |

---

## Safety classification

Every tool is classified in `mcp/tools/safety_gate.py`:

| Level | Requires human approval | Examples |
|---|---|---|
| `READ_ONLY` | No | Graph queries, log parsing, term lookup |
| `CONFIG` | No | Writing to `knowledge-graph/custom/` |
| `DESTRUCTIVE` | **Yes** | Hardware state modification, external build triggers |

`DESTRUCTIVE` tools are blocked by the MCP server until the caller explicitly sets
`requires_human_approval: true` in the tool invocation.

---

## Verifying no outbound traffic

The server is designed for air-gapped environments.  Verify there are no outbound
connections after starting it:

```bash
# Linux
ss -tp | grep python

# macOS
lsof -i -n -P | grep python
```

No external IP addresses should appear — only `127.0.0.1`.

---

## Related Documentation

- [Skill Registration](skill-registration.md) — how to register skills in Claude Code
- [Custom Knowledge](custom-knowledge.md) — how to add in-house SoC data
