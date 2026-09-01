# CANN Performance Breakdown Skills

This directory contains a three-stage workflow from NPU profiling data to an interactive UI report. Use the skills in numeric order:

| Stage | Directory | Purpose |
| --- | --- | --- |
| 1 | [`1-perf-breakdown`](1-perf-breakdown/) | Build the architecture from model source and map profiling operators to structure nodes |
| 2 | [`2-adapt-breakdown-to-ui-json`](2-adapt-breakdown-to-ui-json/) | Convert the breakdown into UI analysis, performance, timeline, and architecture-graph data |
| 3 | [`3-generate-ui-json-report`](3-generate-ui-json-report/) | Generate the interactive UI report from the converted data |

See [`MODEL_BREAKDOWN_TO_UI_WORKFLOW_en.md`](MODEL_BREAKDOWN_TO_UI_WORKFLOW_en.md) for stage handoff, inputs, outputs, and gates. The detailed rules for each stage are defined by its `SKILL.md` and `references/` files.

## Install And Invoke

```bash
git clone --depth 1 https://gitcode.com/cann/oam-tools.git
mkdir -p ~/.codex/skills
cp -a oam-tools/skills/cann-perf-breakdown ~/.codex/skills/
```

Invoke: `Use the $cann-perf-breakdown workflow with <capture-directory> as the input directory and <output-directory> as the output directory.`

## Quick start

```bash
python3 2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --capture-dir <profiling-directory> \
  --model-id <model-id> \
  --out <output-directory>
```

The entry point runs conversion and report generation when the input evidence satisfies the stage gates. If AI mapping or semantic review is required, it writes a request file and pauses; the workflow guide describes how to continue.

## Directory layout

- `1-perf-breakdown/`: architecture extraction, operator attribution, validation, and scoring.
- `2-adapt-breakdown-to-ui-json/`: deterministic conversion to the UI data contract.
- `3-generate-ui-json-report/`: report assets, runtime data, and frontend generation scripts.
- `MODEL_BREAKDOWN_TO_UI_WORKFLOW_en.md`: three-stage workflow navigation.
