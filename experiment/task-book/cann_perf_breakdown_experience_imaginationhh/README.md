# cann-perf-breakdown 技能体验 —— DeepSeek-3.2 性能拆解 —— imaginationhh

本目录是 **cann-perf-breakdown 技能**（NPU 性能数据按模型结构拆解）针对 **DeepSeek-3.2（DeepseekV3）** 模型的一次完整拆解产物，作为 task-book 体验提交，演示该技能 Mode A 完整 5 步工作流的端到端输出。

## 模型与 trace 概况

- 模型：DeepseekV3（61 个主层 = 3 dense + 58 MoE，外加 MTP 预测层）
- trace 范围：`rank_local`（rank 0，pipeline stage 0），并行度 TP=16 / CP=1
- 注意：该 trace 非完整模型（仅观测到 6/61 主层），性能数据**不得**外推为完整模型 latency

## 拆解质量

| 指标 | 值 |
|------|------|
| 拆解评分 | **99 / 100**（status: passed，最低阈值 95） |
| 校验状态 | passed_with_warnings（errors=0, warnings=1） |
| Kernel 精确覆盖 | **100.0%**（total_ops=548, unmapped=0, duplicate=0） |
| 架构完整性 | 20/20 |
| 数据流与分支正确性 | 20/20 |
| Layer/子模块边界 | 20/20 |
| 证据可追溯性 | 5/5（code_ref_ratio=0.918） |

详见 `work/breakdown_score.json` 与 `work/readiness.json`（全部检查项 `ok=true`，`blockers=[]`）。

## 目录结构

```text
cann_perf_breakdown_experience_imaginationhh/
├── README.md                       # 本说明
├── breakdown_report.md             # 层级耗时拆解报告（Markdown）
├── breakdown_report.html           # 拆解报告（可视化 HTML）
├── ui-report/                      # 交互式报告与分析数据
│   ├── report/index.html           # 浏览器打开即可查看交互式报告
│   ├── ds3.2_analysis_config.json  # 拆解配置（schema v2）
│   ├── ds3.2_perf_data.json        # 性能数据
│   ├── ds3.2_timeline.json         # 时间轴事件
│   └── trace_view.json             # trace 视图数据
├── ui_facts/                       # 报告所需精简事实数据
│   ├── ds3.2_analysis_config.json
│   ├── ds3.2_perf_data.json
│   └── ds3.2_timeline.json
└── work/                           # 拆解中间产物
    ├── raw_ops.json / raw_ops.compact.json / raw_ops_details.json
    ├── kernel_attribution.json     # kernel 归因
    ├── model_manifest.json         # 模型清单
    ├── node_index.json             # 节点索引
    ├── validation_report.json      # 校验报告
    ├── semantic_review.json        # 语义复核
    ├── breakdown_score.json        # 拆解评分
    ├── readiness.json              # 就绪检查
    ├── graph_consistency.json
    └── steps_summary.md
```

## 生成方式

由 `cann-perf-breakdown` 技能的 Mode A 完整 5 步流程生成：

```text
Step 1: analyze_kernels.py  → raw_ops*.json
Step 2: AI 拆解（raw_ops.compact.json + 模型源码）→ analysis_config.json
Step 3: Review 校验循环      → analysis_config.json（终版）
Step 4: generate_report.py   → breakdown_report.md / .html + ui-report/
Step 5: compute_metrics.py   → metrics
```

输入为 NPU profiling 输出的 `kernel_details.csv` 与 DeepseekV3 模型源码（`modeling_deepseek.py`）。

## 怎么看

- **快速浏览**：直接看 `breakdown_report.md`（层级耗时树）或 `breakdown_report.html`（可视化）。
- **交互式报告**：浏览器打开 `ui-report/report/index.html`（架构图 / 时间轴 / trace 视图）。
