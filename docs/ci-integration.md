# CI/CD Integration Guide

This document explains how to integrate the BSP Knowledge Skill Sets test and evaluation pipeline into your CI/CD system. The goal is to catch regressions in skill quality, knowledge graph integrity, and tool safety before they reach production.

---

## Test Pyramid

The project has four layers of automated validation, from fastest to slowest:

```
┌─────────────────────────────────────────────┐
│  Eval Regression (200+ cases, ~30s)         │  ← Skill quality: schema, domain coverage
├─────────────────────────────────────────────┤
│  Blackboard Eval (15 tests, ~5s)            │  ← Multi-agent coordination correctness
├─────────────────────────────────────────────┤
│  MCP Integration (54 tests, ~10s)           │  ← Tool calling: safety gate, graph queries
├─────────────────────────────────────────────┤
│  Safety Gate Unit (82 tests, ~2s)           │  ← Fast: risk classification, approval logic
└─────────────────────────────────────────────┘
```

### Layer 1: Safety Gate Unit Tests

**What it tests:** Risk level classification (READ_ONLY / CONFIG / DESTRUCTIVE), approval gating logic, unknown tool handling.

```bash
python3 -m pytest tests/test_safety_gate.py -v
```

- 82 tests, runs in ~2 seconds
- No database or MCP server required
- Run on every commit

### Layer 2: MCP Integration Tests

**What it tests:** End-to-end tool calling through the MCP server, graph query correctness, log parser output format, safety gate enforcement at the server level.

```bash
python3 -m pytest tests/test_mcp_integration.py -v
```

- 54 tests, runs in ~10 seconds
- Requires the base knowledge graph (built by `scripts/build_base_graph.py`)
- Run on every PR

### Layer 3: Blackboard Eval Tests

**What it tests:** The 5-step Blackboard protocol (Activate → Contribute → Synthesize → Validate → Present), Arbiter dispatch routing, cross-domain hypothesis convergence, structured report format.

```bash
python3 -m pytest evals/blackboard_eval.py -v
```

- 15 tests, runs in ~5 seconds
- Tests structural correctness of the Blackboard pattern, not LLM output quality
- Run on every PR that modifies `skills/bsp-knowledge-mentor/`

### Layer 4: Eval Regression Suite

**What it tests:** Schema validation for all 200+ eval cases across all 7 skills, domain tag coverage, keyword minimum thresholds.

```bash
python3 -m pytest evals/run_evals.py -v
```

- 200+ cases validated, runs in ~30 seconds
- Requires the base knowledge graph
- Run on every PR; weekly scheduled run recommended for drift detection

### Full Regression Report

For a comprehensive snapshot (saves scorecard to `evals/scorecards/`):

```bash
python3 evals/regression_runner.py
```

---

## Graph Integrity Validation

Before running evals, validate that the knowledge graph is structurally sound:

```bash
# Check for orphan nodes, dangling relationships, schema violations
python3 scripts/graph_maintenance/validate_graph.py

# Get node/relationship counts and coverage gaps
python3 scripts/graph_maintenance/graph_stats.py

# Identify expansion priorities (missing FailureMode links, sparse rels)
python3 scripts/graph_maintenance/knowledge_gap_detector.py
```

Use `validate_graph.py` as a CI gate — it exits with status 0 on PASS and status 1 on FAIL (critical issues). Warnings (e.g., orphan nodes) do not cause failure but should be reviewed.

---

## GitHub Actions Setup

A reference workflow template is provided at `templates/ci-integration/github-actions.yaml`.

### Step-by-step

1. Copy the template into your repository:

   ```bash
   mkdir -p .github/workflows
   cp templates/ci-integration/github-actions.yaml .github/workflows/bsp-ai-ci.yaml
   ```

2. The workflow runs on every pull request to `main` and on manual dispatch.

3. The pipeline does the following:
   - Installs Python 3.11 and project dependencies
   - Initializes the Kuzu schema
   - Builds the base knowledge graph (~2 minutes)
   - Starts the MCP server in the background
   - Runs the eval suite
   - Uploads scorecards as artifacts

### Adding Safety Gate and Integration Tests

Add these steps before the eval suite step:

```yaml
      - name: Run safety gate tests
        run: python3 -m pytest tests/test_safety_gate.py --tb=short -q

      - name: Run MCP integration tests
        run: python3 -m pytest tests/test_mcp_integration.py --tb=short -q

      - name: Run Blackboard eval tests
        run: python3 -m pytest evals/blackboard_eval.py --tb=short -q

      - name: Validate graph integrity
        run: python3 scripts/graph_maintenance/validate_graph.py
```

### Weekly Scheduled Regression Run

Add a cron trigger for scheduled regression checks:

```yaml
on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Every Monday at 06:00 UTC
  workflow_dispatch:
```

---

## Jenkins Setup

A reference pipeline is provided at `templates/ci-integration/jenkins-pipeline.groovy`.

### Step-by-step

1. Create a new Jenkins pipeline job pointing to `templates/ci-integration/jenkins-pipeline.groovy` in your SCM.

2. Adjust the `PYTHON` environment variable if your Jenkins agent uses a different Python path.

3. The pipeline runs the same stages as the GitHub Actions workflow: install → schema init → build graph → start MCP → run evals.

4. Scorecards are archived as build artifacts.

### Adding Graph Validation

Add a stage before the eval suite:

```groovy
        stage('Validate graph') {
            steps {
                sh "${PYTHON} scripts/graph_maintenance/validate_graph.py"
            }
        }
```

---

## Pre-Commit Hook (Optional)

For local development, you can run the safety gate tests as a pre-commit hook:

```bash
# .git/hooks/pre-commit (make executable with chmod +x)
#!/bin/sh
python3 -m pytest tests/test_safety_gate.py -q --tb=line
```

This catches safety gate regressions before they reach CI.

---

## Environment Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | >= 3.11 | Required for Kuzu embedded DB |
| pip packages | See `requirements.txt` | `kuzu`, `chromadb`, `pytest`, `mcp`, etc. |
| Disk | ~200 MB | For the base knowledge graph + dependencies |
| Network | None | All components are local; no cloud services needed |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'mcp'"

The MCP server must be run from the repository root, not from inside `mcp/`. The local `mcp/` directory shadows the installed `mcp` SDK package.

```bash
# Correct
python3 mcp/server.py

# Wrong
cd mcp && python3 server.py
```

### "Database not found" errors

Run `python3 scripts/build_base_graph.py` to create the base graph. For a clean rebuild: `python3 scripts/build_base_graph.py --clean`.

### Graph validation warnings

Warnings (orphan nodes, disconnected FailureModes) do not fail the pipeline but indicate connectivity gaps. Run `python3 scripts/graph_maintenance/knowledge_gap_detector.py` to identify priorities and add relationships in a new seed script.

### Eval case schema failures

Eval cases must have the required fields: `input`, `expected_output`, `domain`, `skill`, `keywords`. Check the failing case file against `evals/cases/case_001.json` for the expected format.
