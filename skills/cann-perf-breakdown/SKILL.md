---
name: cann-perf-breakdown
description: |
  NPU 性能数据拆解技能。将 kernel_details.csv 中的性能数据按模型结构进行拆解分析。
  触发场景：分析 kernel_details.csv、拆解性能数据到模型层级、分析大模型性能瓶颈、仅模型代码做架构拆解、仅性能数据做诊断（委托 cann-npu-perfanalysis）。
---

# NPU 性能数据拆解技能

将 NPU profiling 输出的 `kernel_details.csv` 按 Transformer 模型结构进行层级拆解，生成结构化的 JSON 和 Markdown/HTML 分析报告。

---

## 适用场景

| 场景 | 说明 |
|------|------|
| 大模型性能分析 | 分析各类 Transformer 模型 |
| 层级耗时拆解 | 拆解 Embedding/Block/Head 各层耗时 |
| Block 内部分析 | 分析 Attention、MLP、Norm 子层 |
| 架构特征识别 | 识别 MLA、MoE、GQA 等架构 |
| 仅模型代码 | 仅做结构拆解，不绑定具体性能数据（多分支用 `branches` 表达） |
| 仅性能数据 | 委托给 `cann-npu-perfanalysis` sibling skill 做 8 维诊断 |

---

## 入口分派（Mode 判定）

启动时检查工作目录，按以下优先级判定模式：

| 条件 | 模式 | 行为 |
|---|---|---|
| 有模型源码（`*modeling*.py` 等） **且** 有 `kernel_details.csv` 或 `raw_ops*.json` | **Mode A** | 完整 5 步流程，输出 `analysis_config.json` + 报告 + 指标 |
| 仅模型源码 | **Mode B** | 仅做结构拆解，输出 `model_structure.json`（schema 沿用 analysis_config.json，`op_indices=[]`，可加 `branches` 字段）。详见 `references/mode_b_branches.md` |
| 仅性能数据（csv 或 `ASCEND_PROFILER_OUTPUT/`） | **Mode C** | 委托 `cann-npu-perfanalysis` sibling skill。详见 `references/mode_c_delegate.md` |

> Mode B 与 Mode C 不进入 Step 3/4/5；Mode A 走完整 5 步。

---

## 工作流（Mode A）

```
Step 1: analyze_kernels.py
        → raw_ops.json + raw_ops_details.json + raw_ops.compact.json
   ↓
Step 2: AI 拆解（投喂 raw_ops.compact.json + 模型源码）
        → analysis_config.json（首版）
   ↓
Step 3: Review（脚本检查 → AI 仅看 issue 列表 → 修正循环）
        → analysis_config.json（终版）
   ↓
Step 4: generate_report.py（默认 MD + HTML）
        → {prefix}_report.md / {prefix}_report.html
   ↓
Step 5: compute_metrics.py
        → metrics_report.md
```

---

### Step 1: 提取单 Step 数据

先枚举所有 step 并选择非 warmup 的代表 step。未显式传 `-s` 时，
`analyze_kernels.py` 会按 kernel_count + kernel 类型分布寻找稳定 step 组；
若该组最早 step 的 kernel_sum 相比后续 step 中位数是明显离群值，则跳过该
warmup/outlier step，并选择后续 step 中最接近中位数的一步。若最早 step 不离群，
保留最早稳定 step。需要强制复现某个 step 时再显式传 `-s`。

```bash
python scripts/analyze_kernels.py \
  -f kernel_details.csv \
  -o outputs/raw_ops.json \
  -d outputs/raw_ops_details.json \
  -m outputs/steps_summary.md \
  --compact-out outputs/raw_ops.compact.json
```

**作用**：从 `kernel_details.csv` 提取单个 step 数据，避免后续分析 token 消耗过大。

| 输出 | 用途 |
|---|---|
| `steps_summary.md` | 所有 step 的 kernel_count、kernel 类型和耗时概览，含自动选步原因 |
| `raw_ops.json` | 自动选择或 `-s` 指定的单 Step kernel 概要，enrich/校验脚本用 |
| `raw_ops_details.json` | 单 Step kernel 详情（含 CSV 全部字段），Step 4/5 报告与指标用 |
| `raw_ops.compact.json` | Step 2 投喂给 AI 的精简视图（删除 `start_time_us`/`duration_us`，连续相同算子折叠）|

每个 operator 含 `org_index`，表示其在 `kernel_details.csv` 中的 0-based 行号。

**可选**：

```bash
python scripts/segment_layers.py -r outputs/raw_ops.json -o outputs/op_segments.json
```

为 Step 2 生成 layer 边界**候选**（基于最长重复子段）。AI 可作为定位参考，最终边界以源码语义为准。

**参考**：`references/kernel_data_guide.md`

---

### Step 2: 拆解模型结构

按 `references/structure_analysis_guide.md` §D.1 执行：

1. 选择代表性 step 与 decoder layer 实例
2. 阅读模型源码，提取模块层级和稳定函数边界
3. 在 op 序列中定位 decoder layer 边界（可参考 `op_segments.json`）
4. 逐层映射 op 到源码模块或函数语义
5. 输出 `analysis_config.json`
6. 运行 enrich：

```bash
python scripts/analyze_kernels.py --enrich \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json
```

字段规范、节点来源规则、命名规则、边界规则、shape_semantic 必填范围（11 类算子 + 统一维度符号 B/T/H/D/...）等**全部细节**见 `references/structure_analysis_guide.md`。SKILL.md 不再重述以避免分歧。

---

### Step 3: Review 拆解结果

按 `references/structure_analysis_guide.md` §D.2 执行：

```bash
python scripts/check_structure.py    -c outputs/analysis_config.json --json > outputs/issues.json
python scripts/validate_shapes.py    -c outputs/analysis_config.json --fail-fast --json >> outputs/issues.json
python scripts/check_op_coverage.py  -c outputs/analysis_config.json -r outputs/raw_ops.json --json >> outputs/issues.json
```

- `issues.json` 为空 → 跳过 AI review，直接进入 Step 4
- 否则拉起 review subagent，**仅投喂** issue 命中的节点片段、对应源码切片（按 `code_ref` 稀疏读）、对应 raw_ops 切片；subagent 修正后回到本步重跑，迭代上限 3 次

---

### Step 4: 生成报告

```bash
python scripts/generate_report.py \
  -r outputs/raw_ops_details.json \
  -c outputs/analysis_config.json \
  -o outputs/{prefix}_report.md \
  --html -d 3
```

| 输出 | 说明 |
|---|---|
| `{prefix}_report.md` | Markdown 分析报告 |
| `{prefix}_report.html` | HTML 分析报告（默认产出） |

---

### Step 5: 计算性能指标

```bash
python scripts/compute_metrics.py \
  -r outputs/raw_ops_details.json \
  -c outputs/analysis_config.json \
  -o outputs/metrics_report.md \
  -d 3
```

**四维基础指标**：

| 指标 | 定义 | 含义 |
|------|------|------|
| `wall_ms` | 最后 kernel 结束 - 首个 kernel 开始 | 实际墙上时钟耗时（含间隙） |
| `busy_union_ms` | 合并后的设备忙碌时间 | 设备实际利用率（去重叠） |
| `kernel_sum_ms` | 所有 kernel 时长的算术和 | 总计算量（忽略重叠） |
| `total_cost_ms` | Σ(duration + wait) | 完整成本（含等待） |

**衍生指标**：`并行度 = kernel_sum_ms / wall_ms`、`bubble_ms = wall_ms - busy_union_ms`、`占比% = wall_ms / step_wall × 100`。

**诊断规则**：

| 条件 | 阈值 | 诊断结论 |
|------|------|----------|
| kernel_sum > wall | > 1.5× | 高流并行度（多流重叠执行） |
| kernel_sum > wall | > 1.2× | 中等流并行 |
| wall > busy_union | > 1.5× | 存在间隙气泡 |
| total_cost > kernel_sum | > 1.3× | 等待时间显著，检查 wait-anchor 热点 |
| busy_union / wall | 80%~95% | 利用率良好 |
| busy_union / wall | < 80% | 利用率偏低 |
| busy_union ≈ wall ≈ kernel_sum | 偏差 < 10% | 干净顺序执行 |

**适用范围**：decoder layer 及子节点、stages、runtime_auxiliary 及子节点。

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `raw_ops.json` | 单 Step kernel 概要（脚本用） |
| `raw_ops_details.json` | 单 Step kernel 详情（Step 4/5 用） |
| `raw_ops.compact.json` | Step 2 投喂 AI 的精简视图 |
| `op_segments.json`（可选） | layer 边界候选 |
| `analysis_config.json` | 拆解配置（Mode A 终版）|
| `model_structure.json` | 仅结构（Mode B）|
| `issues.json` | Step 3 检查结果 |
| `{prefix}_report.md` / `.html` | 分析报告 |
| `metrics_report.md` | 性能指标分析报告 |

---

## 参考资源

| 文件 | 何时查阅 |
|------|----------|
| `references/structure_analysis_guide.md` | Step 2 拆解 + Step 3 Review 全部规则细节 |
| `references/kernel_data_guide.md` | Step 1 — `kernel_details.csv` 字段说明 |
| `references/mode_b_branches.md` | Mode B 多分支表达约定 |
| `references/mode_c_delegate.md` | Mode C 委托 `cann-npu-perfanalysis` 模板 |
| `scripts/analyze_kernels.py` | Step 1 提取与 Step 2 enrich |
| `scripts/segment_layers.py` | layer 边界候选 |
| `scripts/check_structure.py` | Step 3 树结构良构性 |
| `scripts/validate_shapes.py` | Step 3 shape_semantic 一致性 |
| `scripts/check_op_coverage.py` | Step 3 op 全覆盖 |
| `scripts/regression_check.py` | 与 baseline 做结构回归 |
| `scripts/generate_report.py` | Step 4 报告生成 |
| `scripts/compute_metrics.py` | Step 5 指标计算 |
