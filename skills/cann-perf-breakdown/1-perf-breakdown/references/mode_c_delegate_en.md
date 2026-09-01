# Mode C: Performance Data Only, Delegate to cann-npu-perfanalysis

<!-- Synchronized with the latest Skill 1 implementation. -->

When the working directory contains **performance data but no model source**, enter Mode C and delegate to the sibling `cann-npu-perfanalysis` skill for eight-dimensional performance diagnosis. Do not perform model-structure breakdown.

---

## Preconditions

- `kernel_details.csv` or an `ASCEND_PROFILER_OUTPUT/` directory exists.
- Model source (`*modeling*.py` or an equivalent entry point) does not exist.

If model source also exists, use Mode A. If only source exists, use Mode B; see `mode_b_branches.md`.

---

## Delegation

Do not reuse this skill's breakdown workflow in Mode C. Load `skills/cann-npu-perfanalysis/SKILL.md` and its references, then execute that skill. Use a general-purpose subagent when context isolation is required.

### 1. Locate the sibling skill

Confirm that `skills/cann-npu-perfanalysis/SKILL.md` exists in the current repository. If it is missing, report the incomplete dependency. Do not download external code at runtime.

### 2. Start the subagent

Use the Agent tool with `subagent_type=general-purpose` and the following prompt template:

```text
Act as the execution agent for the cann-npu-perfanalysis skill and perform an eight-dimensional diagnosis of the following NPU profiling data.

Skill definition:
- SKILL.md: skills/cann-npu-perfanalysis/SKILL.md
- Reference directory: skills/cann-npu-perfanalysis/references/
  - data-schema.md       # CSV/JSON column dictionary
  - metrics-formulas.md  # Phase 1-2 formulas
  - thresholds.md        # P0-P3 thresholds
  - hardware-specs.md    # Peak TFLOPs by chip

Input data:
- profile directory: <ASCEND_PROFILER_OUTPUT_DIR>
  (contains kernel_details.csv, step_trace_time.csv, op_statistic.csv,
   communication.json, and communication_matrix.json)

Requirements:
1. Follow the Phase 0-4 workflow in SKILL.md exactly: parse, calculate metrics, diagnose bottlenecks, and emit outputs.
2. Detect the V1/V2 schema automatically by checking for the cube_utilization(%) column.
3. Skip dimensions 3/5/6/7 when their files are missing; skip dimension 7 when rows < 500.
4. Obey every item in the SKILL.md NEVER list.

Write these files to the caller's outputs/ directory:
- analysis_data.json  # eight-dimensional structured diagnosis; schema in SKILL.md lines 255-424
- report.md           # human-readable report with P0-P3 bottlenecks
- report.html         # rendered by skills/cann-npu-perfanalysis/references/generate_html.py

Return the three file paths and one sentence with the top-level conclusion.
```

### 3. Process the result

- On success, list `outputs/analysis_data.json`, `report.md`, and `report.html` as Mode C artifacts.
- On failure, such as a missing required profile file, present the subagent error directly and do not fall back.

---

## Relationship to This Skill's Outputs

`cann-npu-perfanalysis` does not break down model structure. It produces performance diagnosis across iteration efficiency, operator hotspots, hardware utilization/MFU, communication efficiency, device bubbles, wait anchors, coarse hierarchy inference, and multi-device balance.

| Dimension | This skill (Mode A) | cann-npu-perfanalysis (Mode C) |
|---|---|---|
| Model structure tree | Complete submodule-level breakdown | Only coarse MoE and layer-count inference |
| Operator-to-source attribution | Exact alignment | Not provided |
| Performance bottleneck diagnosis | Four metrics only | P0-P3 diagnosis |
| Hardware utilization / MFU | Not provided | Provided |
| Communication analysis | Not provided | Provided |
| Multi-device balance | Not provided | Provided |

The modes are complementary. **Mode C and Mode A use different output schemas and must not be compared with a strict diff.**

---

## Dependency Policy

- Use only `skills/cann-npu-perfanalysis/` reviewed and shipped with `oam-tools`.
- Do not clone, pull, or execute code from an external repository at skill runtime.
- When the dependency is missing, report: `Mode C requires skills/cann-npu-perfanalysis/SKILL.md in this repository`.

---

## Outputs Not Produced

Mode C does not produce `analysis_config.json`, `raw_ops*.json`, `{prefix}_report.md`, or `metrics_report.md`. Those are Mode A artifacts. Every Mode C artifact comes from the sibling skill.
