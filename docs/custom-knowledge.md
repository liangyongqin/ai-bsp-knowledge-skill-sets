# Custom Knowledge — Adding In-House SoC Data

> **See also:** [`knowledge-graph/custom/README.md`](../knowledge-graph/custom/README.md)
> for the definitive guide to the custom knowledge directory.

This page summarises the workflow for BSP engineers who want to ground the AI skills
against their own silicon data (MediaTek, Qualcomm, or any other SoC family).

---

## Why custom knowledge matters

The base graph (`knowledge-graph/base/`) contains open-source knowledge only —
ARM public TRMs, AMBA specs, Linux kernel documentation.  It covers architectural
patterns but has **no silicon-specific register addresses, no internal power trees,
and no historical failure cases** from your products.

Adding custom knowledge:

- Eliminates hallucinations about register addresses and voltage values specific to
  your SoC.
- Enables the Blackboard system to cite your internal case library when diagnosing
  failures.
- Keeps your proprietary data **local and air-gapped** — it never leaves your machine.

---

## Ingestion workflow

### 1. PDF TRM (SoC Technical Reference Manual)

```bash
python scripts/ingest_custom.py --input /path/to/MT6989_TRM.pdf --soc mt6989
```

The script uses `pdfplumber` and `unstructured[pdf]` to extract register tables,
power-domain maps, and clock-tree diagrams, then writes Python ingest scripts into
`knowledge-graph/custom/`.

### 2. IP-XACT XML (preferred for register accuracy)

```bash
python scripts/ingest_custom.py --input /path/to/soc_registers.xml \
    --soc mt6989 --format ipxact
```

IP-XACT provides machine-readable bit-field definitions (Accellera 2022 standard),
giving the highest register extraction accuracy.

### 3. Verify extracted data

```bash
python scripts/ingest_custom.py --verify --soc mt6989
```

Spot-checks extracted register addresses against known-good values defined in
`mcp/tools/spec_extractor/validate.py`.

---

## Precedence and namespacing

Custom nodes are tagged with the `custom` namespace in Kuzu. When the same
node key exists in both `base` and `custom`, **`custom` takes precedence** so
you can override open-source approximations with silicon-accurate values.

---

## Security reminder

The entire `knowledge-graph/custom/` directory (except its `README.md`) is listed
in `.gitignore`.  Verify before every push:

```bash
git status
# should show NO files under knowledge-graph/custom/
```
