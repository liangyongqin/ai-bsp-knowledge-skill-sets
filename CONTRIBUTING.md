# Contributing to BSP Knowledge Skill Sets

This project is in **alpha**. The most valuable contributions right now are not code — they are real-world trial reports from BSP engineers using the skills on actual problems.

---

## For alpha testers: how to give feedback

### The fastest contribution: open an issue

Go to the **Issues** tab and open a new issue. Use one of the templates below.

---

### Template A — Skill response quality

Use this when a skill gave a response that was wrong, incomplete, or missed the root cause.

```
**Skill invoked:** /power-thermal-expert  (or whichever skill)
**Input (what you typed):**
<paste your question or log snippet — remove any proprietary register values>

**What the skill responded:**
<paste or summarise the response>

**What was wrong or missing:**
<what the correct answer should have been, or what key step it skipped>

**Your platform context:** (optional)
Architecture: ARM Cortex-A (big.LITTLE / DSU / etc.)
OS: Linux kernel version
Domain: power / boot / multimedia / GPU / interrupt / register
```

---

### Template B — Skill response was good

Positive signal is as useful as negative. Helps us know what's working.

```
**Skill invoked:** /boot-debug-expert
**Problem type:** PLL lock ordering violation / thermal throttle / camera open fail / etc.
**What worked well:**
<what the Socratic questioning helped you figure out>
**Would have saved me:** (estimate) X minutes / hours
```

---

### Template C — Missing knowledge

Use this when the skill clearly doesn't know something it should — a subsystem, a failure mode, a Linux driver, a specific ARM IP.

```
**Skill:** /interrupt-virtualization-expert
**Missing topic:** KVM ARM PMU virtualisation (perf in guest)
**Why it matters:** We debug guest performance counters regularly
**Open-source reference:** Linux Documentation/virt/kvm/aarch64/... or ARM spec section
```

---

### Template D — Setup / install problem

```
**OS:** Ubuntu 22.04 / macOS 14 / etc.
**Python version:** 3.11.x
**Step that failed:** pip install / build_base_graph.py / install.sh / mcp/server.py
**Error message:** (paste full traceback)
**What you tried:**
```

---

## What we are NOT asking for right now

- Pull requests adding new features — please open an issue first
- Changes to `knowledge-graph/base/` seed scripts without discussion
- New `skill.md` files — the 7 existing skills need validation before expansion

---

## Adding your own SoC knowledge (private, not contributed back)

Your company's SoC data stays local and never enters this repository. The workflow:

```bash
# Inside your company network only
python scripts/ingest_custom.py --input /path/to/TRM.pdf --soc mt6989
python scripts/ingest_custom.py --input /path/to/registers.xml --soc mt6989 --format ipxact
```

`knowledge-graph/custom/` is gitignored. Verify before every push:

```bash
git status   # must show NO files under knowledge-graph/custom/
```

See [docs/custom-knowledge.md](docs/custom-knowledge.md) for details.

---

## Running the test suite before reporting a bug

If you suspect a tool-level issue (not a skill response quality issue), run the integration tests first:

```bash
# From repo root
pytest tests/test_safety_gate.py -v           # 82 tests
pytest tests/test_mcp_integration.py -v       # 54 tests
pytest evals/blackboard_eval.py -v            # 15 tests
```

Include the output in your issue if any test fails.

---

## Versioning and branches

- `main` is the alpha branch — expect breaking changes between weeks
- Tag your issue with the commit SHA you tested: `git rev-parse --short HEAD`

---

## Code of conduct

This is a technical project used by engineers in daily work. Keep issues focused on technical facts. No speculation about hardware vendors or unreleased silicon.
