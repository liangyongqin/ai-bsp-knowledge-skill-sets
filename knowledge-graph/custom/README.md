# Custom Knowledge — User-Managed SoC Data

This directory holds **proprietary, in-house** SoC knowledge nodes that augment the open-source base graph.
It is intentionally excluded from version control (see root `.gitignore`).

## What belongs here

| File pattern | Content |
|---|---|
| `<soc-codename>_power_tree.py` | Proprietary PMIC supply chains, voltage rails, sequencing rules |
| `<soc-codename>_clock_tree.py` | PLL configuration, clock-domain gating hierarchy |
| `<soc-codename>_irq_table.py` | SPI/PPI/LPI assignment tables from your internal TRM |
| `<soc-codename>_registers.py` | Register address space, bit-field definitions |
| `case_library/*.py` | Anonymised post-mortem failure cases for knowledge sedimentation |

## How to add custom knowledge

1. Prepare your in-house TRM (PDF or IP-XACT XML).
2. Run the ingestion CLI:

   ```bash
   python scripts/ingest_custom.py --input /path/to/TRM.pdf --soc mt6989
   # or for IP-XACT:
   python scripts/ingest_custom.py --input /path/to/soc.xml --soc mt6989 --format ipxact
   ```

3. Verify extracted nodes:

   ```bash
   python scripts/ingest_custom.py --verify --soc mt6989
   ```

4. The ingestion script writes new nodes and edges directly into this directory as Python
   ingest scripts, then appends them to the Kuzu database at
   `knowledge-graph/base/bsp_base.db` under the `custom` namespace.

## Precedence rule

When the same node key exists in both `base/` and `custom/`, the **`custom/` value takes
precedence**. This allows you to override open-source approximations with your silicon-accurate
data without modifying the committed base graph.

## Security reminder

> **Never commit this directory.** The `.gitignore` at the repository root excludes
> `knowledge-graph/custom/*` (this README is the only committed file here). Verify with
> `git status` before every push that no custom data appears as a staged change.
