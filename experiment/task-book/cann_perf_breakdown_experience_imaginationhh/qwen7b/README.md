# Qwen-7B 性能拆解报告 —— imaginationhh

本目录是 **cann-perf-breakdown 技能** 针对 **Qwen-7B** 模型的性能拆解交互式报告产物，作为 task-book 体验提交。

## 模型概况

- 模型：Qwen-7B
- 报告类型：交互式性能分析报告（PTO report）
- 内容：架构图、时间轴、trace 视图、HBM 视图、算子详情

## 目录结构

```text
qwen7b/
├── README.md                       # 本说明
├── README_en.md                    # English README
├── index.html                      # 交互式报告入口（浏览器打开即可查看）
├── app.css / app.js                # 报告主样式与逻辑
├── architecture-data.js            # 架构数据
├── hbm-view.js                     # HBM 视图
├── trace-view.js                   # trace 视图
├── report-config.js                # 报告配置
├── report-data.js                  # 报告数据
├── report-embedded-data.js         # 内嵌数据（file:// 独立报告）
├── design-system/                  # 设计系统（CSS/JS patterns）
│   ├── css/style.css
│   ├── patterns/                   # IDE frame, graphviz, swimlane, timeline, workbench
│   └── tokens/                     # foundation, semantic, components
└── outputs/                        # 分析输出 JSON
    ├── model_architecture_graph.json
    ├── trace_bindings.json
    ├── architecture_overlay_map.json
    ├── hbm_series.json
    ├── kernel_structure_map.json
    ├── trace_index.json
    ├── validation_manifest.json
    └── ...
```

## 怎么看

浏览器打开 `index.html` 即可查看交互式报告（架构图 / 时间轴 / trace 视图 / HBM 视图）。
