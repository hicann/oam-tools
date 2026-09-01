# Mode B: Structure Breakdown from Model Code Only

<!-- Synchronized with the latest Skill 1 implementation. -->

When the working directory contains model source code but no performance data, this skill enters Mode B and outputs `model_structure.json`.

## Conditions

- Model source exists (`*modeling*.py` or an equivalent entry point).
- `kernel_details.csv`, `raw_ops*.json`, and `ASCEND_PROFILER_OUTPUT/` are absent.

If both input classes exist, use Mode A. If only performance data exists, use Mode C (see `mode_c_delegate.md`).

## Output

`outputs/model_structure.json`, using the `analysis_config.json` schema (see section C of `structure_analysis_guide.md`) with these differences:

| Field | Mode A | Mode B |
|---|---|---|
| Top-level `mode` | absent | `"structure_only"` |
| Leaf `op_indices` | required | must be `[]` |
| Node `kernels` | 11 operator classes require `shape_semantic` | omitted because no raw ops exist |
| Node `branches` | absent | optional for statically ambiguous branches |
| `representative_step` | numeric step ID | `null` |

## The `branches` field

When source code contains a conditional topology and static analysis cannot determine which path executes, add `branches` to the parent node. Typical cases include MoE versus dense layers, sliding versus full attention, and optional MTP. Each possible path is represented as a complete subtree.

```json
{
  "name": "<branch_parent_name>",
  "semantic": "<branch meaning>",
  "code_ref": "<source location>",
  "branches": [
    {
      "condition": "<source condition or equivalent Python expression>",
      "name": "<branch name, preferably the source class/function>",
      "semantic": "<branch meaning>",
      "code_ref": "<branch line range>",
      "children": []
    }
  ]
}
```

## Breakdown procedure

1. Read all model source files, including imported submodules.
2. Identify the top-level `ForCausalLM` class and its `forward` call chain.
3. Extract the tree using sections A.1 (node source), A.2 (naming), and A.3 (boundaries) of `structure_analysis_guide.md`.
4. For a conditional branch, select it when configuration makes it statically decidable; otherwise preserve every possibility in `branches`.
5. Leave `op_indices` as empty arrays.
6. Omit `kernels` and `shape_semantic`, because no raw ops are available for verification.
7. Write `outputs/model_structure.json`.
8. Run the structure check; shape and op-coverage checks are skipped in Mode B:

```bash
python scripts/check_structure.py -c outputs/model_structure.json --mode B --json > outputs/issues.json
```

## Equivalence with a Mode A baseline

If the same model has a Mode A `analysis_config.json`, verify that the Mode B tree is a structural superset:

```bash
python scripts/regression_check.py --mode B \
  --baseline run_1/<model>/outputs/analysis_config.json \
  --new outputs/model_structure.json
```

Every Mode A node path should exist in Mode B. Mode B may add reasonable `branches` nodes but must not omit Mode A nodes.

## Excluded outputs

Mode B does not enter review, report generation, or metric computation. Those stages require `op_indices` and raw performance data.
