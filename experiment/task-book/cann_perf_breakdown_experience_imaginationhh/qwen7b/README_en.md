# Qwen-7B Performance Breakdown Report — imaginationhh

This directory contains the interactive performance breakdown report for the **Qwen-7B** model, produced by the **cann-perf-breakdown skill**, submitted as a task-book experience.

## Model Overview

- Model: Qwen-7B
- Report type: Interactive performance analysis report (PTO report)
- Contents: Architecture graph, timeline, trace view, HBM view, operator details

## Directory Structure

```text
qwen7b/
├── README.md                       # This description (Chinese)
├── README_en.md                    # This file (English)
├── index.html                      # Interactive report entry (open in browser)
├── app.css / app.js                # Main styles and logic
├── architecture-data.js            # Architecture data
├── hbm-view.js                     # HBM view
├── trace-view.js                   # Trace view
├── report-config.js                # Report configuration
├── report-data.js                  # Report data
├── report-embedded-data.js         # Embedded data (file:// standalone report)
├── design-system/                  # Design system (CSS/JS patterns)
│   ├── css/style.css
│   ├── patterns/                   # IDE frame, graphviz, swimlane, timeline, workbench
│   └── tokens/                     # foundation, semantic, components
└── outputs/                        # Analysis output JSON
    ├── model_architecture_graph.json
    ├── trace_bindings.json
    ├── architecture_overlay_map.json
    ├── hbm_series.json
    ├── kernel_structure_map.json
    ├── trace_index.json
    ├── validation_manifest.json
    └── ...
```

## How to View

Open `index.html` in a browser to view the interactive report (architecture graph / timeline / trace view / HBM view).
