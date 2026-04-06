# BSP Optimization Report

> **Template version:** 1.0
> **Auto-populated fields** are marked with `{{placeholder}}`. Use `report_generator.py` to fill them from knowledge graph queries and the impact translator.

---

## 1. Executive Summary

**Date:** {{date}}
**Author:** {{author}}
**SoC / Platform:** {{soc_platform}}
**Product type:** {{product_type}}
**Report scope:** {{scope_one_liner}}

### Business Impact at a Glance

| KPI | Before | After | Delta | Business Meaning |
|-----|--------|-------|-------|------------------|
{{#each kpi_summary}}
| {{kpi_name}} | {{before}} | {{after}} | {{delta}} | {{business_meaning}} |
{{/each}}

**Bottom line:** {{executive_summary}}

---

## 2. Technical Root Cause

### 2.1 Symptom Description

{{symptom_description}}

**Reproduction conditions:**
- Device: {{device}}
- Build: {{build_id}}
- Scenario: {{scenario}}
- Frequency: {{frequency}}

### 2.2 Investigation Steps

| Step | Tool / Method | Finding |
|------|---------------|---------|
{{#each investigation_steps}}
| {{step_number}} | {{tool}} | {{finding}} |
{{/each}}

### 2.3 Root Cause Analysis

**Primary root cause:** {{primary_root_cause}}

**Contributing factors:**
{{#each contributing_factors}}
- {{factor}}
{{/each}}

**Knowledge graph path (if applicable):**
```
{{graph_path}}
```

### 2.4 Affected Components

| Component | Domain | Role in Failure | Severity |
|-----------|--------|-----------------|----------|
{{#each affected_components}}
| {{name}} | {{domain}} | {{role}} | {{severity}} |
{{/each}}

---

## 3. Business Impact Assessment

> This section is auto-populated by `report_generator.py` using the 25-rule BSP-to-Business impact translator. Each finding is mapped from a physical BSP metric delta to a KPI that product managers and executives care about.

### 3.1 Impact Details

{{#each impact_items}}
#### {{component}} / {{metric}}

- **Physical change:** {{delta}} {{unit}} ({{direction}})
- **Severity:** {{severity}}
- **Business impact:** {{business_impact}}
- **Magnitude estimate:** {{magnitude_estimate}}
- **Affected KPIs:** {{affected_kpis}}
- **Recommended framing for PM:** {{recommended_framing}}

<details>
<summary>BSP physics explanation</summary>

{{raw_reasoning}}

</details>

{{/each}}

### 3.2 Aggregate Business Assessment

**Overall severity:** {{overall_severity}}

**Product-level impact:**
{{product_level_impact}}

**Competitive context (if applicable):**
{{competitive_context}}

---

## 4. Fix / Optimization Applied

### 4.1 Change Description

{{fix_description}}

### 4.2 Files / Configuration Changed

| File / Config | Change Type | Description |
|---------------|-------------|-------------|
{{#each changes}}
| `{{path}}` | {{change_type}} | {{description}} |
{{/each}}

### 4.3 Verification Results

| Test | Before Fix | After Fix | Pass? |
|------|-----------|-----------|-------|
{{#each verification_results}}
| {{test_name}} | {{before}} | {{after}} | {{pass}} |
{{/each}}

---

## 5. Mitigation Timeline

| Milestone | Target Date | Owner | Status |
|-----------|-------------|-------|--------|
{{#each milestones}}
| {{milestone}} | {{date}} | {{owner}} | {{status}} |
{{/each}}

---

## 6. Lessons Learned

### 6.1 What Went Well

{{#each lessons_positive}}
- {{lesson}}
{{/each}}

### 6.2 What Could Improve

{{#each lessons_negative}}
- {{lesson}}
{{/each}}

### 6.3 Knowledge Graph Updates

The following nodes/relationships were added to the knowledge graph as a result of this investigation:

| Entity Type | Name | Domain | Source |
|-------------|------|--------|--------|
{{#each graph_updates}}
| {{type}} | {{name}} | {{domain}} | This report |
{{/each}}

---

## Appendix A: Example Reports

### A.1 Power Regression — LPDDR5 Leakage

**Symptom:** Standby battery drain increased by 8% between builds A and B.

**Root cause:** LPDDR5 Deep Sleep Mode (DSM) was inadvertently disabled when the memory controller driver was updated for an unrelated timing fix. The `LPDDR5_LP_CTRL` register bit 3 (DSM enable) was cleared during the re-initialization sequence.

**Business impact (auto-generated):**
- LPDDR5 / leakage_current_ma: +4.0 mA increase
- Severity: **high**
- Impact: A +4.00 mA increase in LPDDR5 leakage current reduces idle battery life by approximately 8%, shortening screen-off standby time.
- Affected KPIs: battery_life, standby_time, idle_power

**Fix:** Restore bit 3 in `LPDDR5_LP_CTRL` during the post-training re-init path. Add a boot-time assertion that verifies DSM is enabled after memory training completes.

---

### A.2 Boot Failure — PMIC Sequencing

**Symptom:** Cold boot hang on 1 in 200 power cycles. System reaches BL2 but never enters the kernel.

**Root cause:** VDD_IO rail rises before VDD_CORE has stabilized. On rare PMIC lots with slower LDO ramp, the margin between the two rails shrinks below the latch-up guard band. The GPIO block samples an undefined state, preventing the boot ROM from jumping to BL31.

**Business impact (auto-generated):**
- PMIC / pmic_transient_mv: +150 mV undershoot
- Severity: **high**
- Impact: Intermittent boot failure affects field reliability and return rates (0.5% failure rate = significant RMA cost at volume).
- Affected KPIs: field_reliability, reboot_rate, first_boot_success

**Fix:** Increase PMIC sequencing delay between VDD_CORE and VDD_IO from 200 us to 500 us. Add a software check in BL2 that validates rail voltages before proceeding.

---

### A.3 Camera Pipeline — ISP DMA Stall

**Symptom:** Camera preview freezes for 200-400 ms during 4K video recording when the device is warm (>38C skin temperature).

**Root cause:** Thermal throttling reduces the ISP clock to the lowest OPP, but the DMA buffer watermark was calibrated for the nominal OPP. At the reduced clock, the ISP cannot drain the CSI-2 RX FIFO fast enough, causing a DMA stall that propagates back to the V4L2 buffer queue.

**Business impact (auto-generated):**
- ISP / dma_stall_ms: +200 ms stall
- Severity: **critical**
- Impact: Users see visible preview freezes during recording. At scale, this generates negative app store reviews and camera quality comparisons.
- Affected KPIs: camera_ux, video_recording_reliability, sustained_camera_performance

**Fix:** Add dynamic DMA watermark adjustment that tracks the current ISP OPP. When thermal throttling reduces the clock, scale the watermark proportionally.

---

*Template v1.0 — designed for use with `mcp/tools/impact_translator/report_generator.py`*
