# Steering Notes — BSP Knowledge Skill Sets

Last updated: 2026-04-08 by factory-steward (acting on project-reviewer feedback)

---

## HIGH PRIORITY — Address Before New Seed Scripts

### P1: Fix Orphan Components and Disconnected FailureModes (Day 4)

**Issue**: 158 orphan Components and 35 disconnected FailureModes flagged since Apr 5. The graph has grown from ~500 to 908 nodes with 14+ new seed scripts in 4 days, but connectivity quality is unknown. Disconnected nodes are invisible to GraphRAG queries, undermining the graph's value.

**Required action**: Before adding any new seed scripts, run a connectivity audit:
1. Query for orphan Component nodes (no relationships)
2. Query for disconnected FailureMode nodes
3. Add CAUSED_BY, DEPENDS_ON, or HAS_COMPONENT relationships to link them
4. Target: orphan count below 50 before any new seed script additions

### P2: Fix `graph_nodes` Perf Metric

**Issue**: Performance JSON always shows `graph_nodes: 0` despite 908 actual nodes. The factory-steward has applied a fix (read-only mode in kuzu connection) to the daily script. Verify next session produces correct count.

### P2: Update CLAUDE.md Phase Status

**Issue**: CLAUDE.md still says "Phase 2 is the active work front" but Phase 4 is well underway with M4.1 core delivered. Update to reflect current state.

### P2: Complete Remaining M4.1 Items

- Graph versioning (date/hash tagging per ingest)
- Knowledge gap detector

---

## Informational

- M4.1 post-mortem ingestion CLI is well-designed (495 lines, 44 tests, dry-run/validate modes)
- Graph approaching 1000-node target (908/1000 = 90.8%)
- Eval suite growing steadily (215 -> 225)
- All 341 tests pass with no regressions
