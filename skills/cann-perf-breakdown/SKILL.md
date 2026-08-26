---
name: cann-perf-breakdown
description: |
  NPU 性能数据拆解技能。以模型源码为主证据拆解结构，再把 kernel_details.csv 的性能数据挂到该结构上。
  触发场景：分析 kernel_details.csv、拆解性能数据到模型层级、分析大模型性能瓶颈、仅模型代码做架构拆解、仅性能数据做诊断（委托 cann-npu-perfanalysis）。
  适用于任意 Transformer 模型族，不假定任何特定模型的模块名或 kernel 名。
---

# NPU 性能数据拆解技能

将 NPU profiling 输出的 `kernel_details.csv` 按 Transformer 模型结构进行层级拆解，生成可验证的结构化 JSON 与性能指标。

---

## 适用场景

| 场景 | 说明 |
|------|------|
| 大模型性能分析 | 分析各类 Transformer 模型 |
| 层级耗时拆解 | 拆解 Embedding/Block/Head 各层耗时 |
| Block 内部分析 | 分析 Attention、MLP、Norm 子层 |
| 架构特征识别 | 识别 MLA、MoE、GQA 等架构 |
| 仅模型代码 | 仅做结构拆解，不绑定具体性能数据（多分支用 `branches` 表达） |
| 仅性能数据 | 委托给仓库内的 `cann-npu-perfanalysis` skill 做 8 维诊断 |

---

## 入口分派（Mode 判定）

启动时检查工作目录，按以下优先级判定模式：

| 条件 | 模式 | 行为 |
|---|---|---|
| 有模型源码（`*modeling*.py` 等） **且** 有 `kernel_details.csv` 或 `raw_ops*.json` | **Mode A** | 完整 11 步评分闭环（schema v2），输出 manifest + config + semantic review + validation + score；达标后才输出指标并进入 Stage 2 |
| 仅模型源码 | **Mode B** | 提取并**校验**架构（`model_manifest.json`）后输出结构树 `model_structure.json`（v2，`op_indices=[]`，可加 `branches`）。**不是**空 op tree，须过架构校验。详见 `references/mode_b_branches.md` |
| 仅性能数据（csv 或 `ASCEND_PROFILER_OUTPUT/`） | **Mode C** | 委托仓库内的 `cann-npu-perfanalysis` skill。详见 `references/mode_c_delegate.md` |

> Mode C 不进入结构拆解；Mode A 走完整 11 步；Mode B 至少走 Step 1-3（架构提取+校验+结构树）。

**核心区分（schema v2，详见 `references/structure_analysis_guide.md` §C/§E）**：

- **学习到的模型层**（`architecture.layer_groups` / `prediction_modules`）≠ **运行时调用**（`trace_instances`）。
- MTP/spec decoding：外层循环重复调用**同一个**学习到的 decoder layer，记为“1 learned layer + N invocations”，**禁止**写成 N 个模型层或伪层号 `6,7,8`。
- **`children` 只表达包含关系**，相邻不等于有数据流边。残差、并行支路、skip 一律走变量传递，必须在 `branches` 里显式声明；未声明的边在下游就不存在，**下游禁止猜测补边**。
- **性能数据只覆盖采集到的范围**：未被采集的层不得外推指标。采集范围可选地记在 `trace_scope`（`full_model` / `rank_local` / `pipeline_stage_local` / `unknown`），无证据时留空或写 `unknown`，不得声称 pipeline rank。

**覆盖四分类（严格模式 unmapped 必须为 0）**：

- `mapped_model_ops`：模型模块算子（trace_instances + stages + structures 叶子）。
- `mapped_runtime_ops`：运行时辅助算子（runtime_auxiliary）。
- `excluded_profiler_ops`：**仅**纯 profiler/bookkeeping，`reason_code` 用有限枚举 + `evidence`；主计算算子（MatMul/Attention/Norm/MoE/通信/Gather/KV cache/采样）禁止 excluded。
- `unmapped_ops`：归属未知 = 映射未完成，**严格校验必然失败**（填 reason 不算完成）。
- 探索模式 `--allow-unmapped` 状态为 `exploratory`，绝不为 `passed`，报告显著标注未验证。
- 每个代表 step 的全部 op 必须落入前三类之一；映射规程见 `references/ai_mapping_protocol.md`。
- **100% Kernel 覆盖不等于语义正确**：Q/K/V 分支、残差、层边界和尾部阶段还必须通过 `semantic_review.json` 的源码/Trace 审查。

---

## 工作流（Mode A，11 步评分闭环）

```
Step 1: 发现输入并判定模式
   ↓
Step 2: extract_model_manifest.py（AST 静态提取全局架构真值）
        → model_manifest.json
   ↓
Step 3: validate_architecture.py（校验全局架构，无 manifest 时以 config 自洽为准）
   ↓
Step 4: analyze_kernels.py（提取代表 profiling step）
        → raw_ops.json + raw_ops_details.json + raw_ops.compact.json
   ↓
Step 4b: device_freq.py（AI Core 实测频率；trace 声明值 × 逐 kernel 反推值交叉验证）
        → device_freq.json
   ↓
Step 5: extract_dataflow.py（AST 解析 forward()，得到确定性数据流真值）
        → dataflow_source.json（modules / calls / edges / branches / forks / merges
          / variants / unsupported）
   ↓
Step 6: AI 拆解（按 references/ai_mapping_protocol.md 执行）+ map_trace_instances.py
        把代表 step 的【全部】op 映射到 model / runtime_auxiliary / 严格允许的 excluded
        → analysis_config.json（v2：architecture + trace_instances + structures）
   ↓
Step 7: 生成可复用的代表结构树（structures，每类 layer_group 一棵；子模块 op 归属
        由 AI 按 ai_mapping_protocol.md 完成，check_sublayers.py 校验一致性）
   ↓
Step 8: AI 按 semantic_review_protocol.md 完整审查源码与代表 Trace
        → semantic_review.json（绑定 config/raw_ops/manifest SHA256）
   ↓
Step 9: run_validation.py（统一 schema/structure/architecture/dataflow/coverage/semantic 校验）
        → validation_report.json（要求 status 恰为 passed；`passed_with_warnings` 不算通过）
   ↓
Step 10: score_breakdown.py（固定 100 分名义量表 + 可运行分母 + 分项门槛 + 硬性否决）
        → breakdown_score.json（要求 convertible=true、可运行正确率 >= 95%、
          【全部可运行核心】分项达最低比例、hard_gates passed）
   ↓ 未达标：读取 iteration_request.json，基于历史最佳配置定向修正，回到 Step 8
Step 11: compute_metrics.py（仅在评分通过后）
        → metrics_report.md + metrics_findings.json（咨询性质）
```

评分细则和停止条件见 `references/breakdown_scoring.md`。正式流程必须循环 Step 8-10，直至语义审查、校验和评分全部通过；配置变化后旧审查因 SHA256 不匹配自动失效。

**停止条件（只有两个）**：

1. `breakdown_score.convertible == true`：所有实际可运行的检查正确率 `>= 95%`，全部可运行核心维度达到原最低比例（架构 `22/25`、数据流与分支 `27/30`、层与子模块边界 `18/20`），Kernel 精确覆盖和证据门禁通过，hard_gates 全过。状态按证据层级为 `verified`、`verified_unbound_scalars` 或 `structure_unverified`；`passed` 仅为旧产物兼容值。
2. 评估轮次达到 `--max-iterations`（默认 **10**）仍未达标 → `blocked_max_iterations`。

> `score` 是固定 100 分名义量表上的原始分，`runnable_max` 是当前输入实际能运行的检查分母。缺少 checkpoint/source snapshot 时，不可绑定的 scalar 检查退出分母并降低证据结论上限，而不是把正确拆解永久判失败；是否可进入下游必须读 `convertible`，不得重新写死 `score >= 95`。

默认关闭"连续无提升早停"（`--stall-limit 0`），循环会跑满 10 轮；需要早停再显式传 `--stall-limit N`。

达到 10 轮上限仍未达标时，**必须**输出根因分析：当前分数、每个未达标维度的分差、卡住的语义检查项、以及缺失的证据类型；禁止通过降低门槛、删除主计算 Kernel 或扩大 excluded 来提分。

> 架构阶段（Step 2-3）**必须**完整扫描源码；稀疏源码读只用于 Step 8 之后的 issue 修复。
>
> **通用能力 vs 验证数据**：正式流程对**每个具体 trace** 用 `scripts/run_breakdown.py`
> 驱动确定性步骤 + AI 按 `references/ai_mapping_protocol.md` 生成映射（op 数/顺序随
> batch/seq/next_n/并行而变）。Skill 包内**不保留**模型源码、真实 profiling 数据或测试
> fixture；验证数据由调用方或仓库测试体系从外部提供。

**语义审查与统一校验命令（替代旧的三条 `>>` 拼接）**：

```bash
python scripts/prepare_semantic_review.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir /path/to/model-source \
  -o outputs/semantic_review_request.json
# AI 完整阅读源码与代表 Trace 后，按请求生成 outputs/semantic_review.json

python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir /path/to/model-source \
  --semantic-review outputs/semantic_review.json \
  -o outputs/validation_report.json
# status != passed 时阻断正式报告；--allow-warnings 仅用于校验分诊，
# 会产生 passed_with_warnings，仍不属于正式通过

python scripts/score_breakdown.py \
  -v outputs/validation_report.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --semantic-review outputs/semantic_review.json \
  -o outputs/breakdown_score.json
# convertible != true 时读取 iteration_request.json 定向修正，禁止生成正式报告
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
| `device_freq.json` | AI Core 实测频率与交叉验证结果，下游所有 cycle 派生指标的分母 |

每个 operator 含 `org_index`，表示其在 `kernel_details.csv` 中的 0-based 行号。

### AI Core 频率（Step 4b）

```bash
python scripts/device_freq.py \
  -d outputs/raw_ops_details.json \
  --trace ASCEND_PROFILER_OUTPUT/trace_view.json \
  -o outputs/device_freq.json
```

两个彼此独立的来源，分别上报，不合并：

- `declared`：trace_view.json 里的 `AI Core Freq` 计数器事件。**一次采集通常只有
  两个采样点**，所以它是标称值，不是频率曲线。
- `derived`：逐 kernel 用 `cycles / time / cores` 反推，样本密集，而且它才是下游
  cycle 派生指标真正依赖的那个值。两者冲突时以 `derived` 为准，并在
  `cross_check.agreement` 里显式报出 mismatch，绝不取平均掩盖分歧。

**核数除数是关键**。`aic_total_cycles` 是该 kernel 占用的所有 core 的累加，所以只除
时间得到的是 cores × clock —— 24 核 kernel 会读成约 44 GHz。AIV 计数器在 `MIX_AIC`
kernel 上要优先用 `Mix Block Dim`（向量段与 cube 段的核数不同），用 `Block Dim` 会
正好差 2 倍。

采集里没有计数器不算错误：频率与全部派生字段一律为 `null`，UI 显示不可用。**绝不用
假设频率替代**，那会静默缩放整套指标。DS3.2 实测两个来源一致为 1850 MHz，spread
0.18%，无降频。

### MoE 专家计数（Step 2 产出，供 stage 2 使用）

MoE 模型的 `model_manifest.json` 会带三项 fact，各自带 `source_ref` 指向配置源码行：

| fact | DS3.2 实测 | 用途 |
|---|---|---|
| `n_routed_experts` | 256 | 路由专家总数 |
| `n_shared_experts` | 1 | 共享专家数；**不被 EP 分片**，每个 rank 都有副本 |
| `num_experts_per_tok` | 8 | top-k 路由宽度 |

这三项是**声明值**，来自模型源码 AST，不是从 kernel shape 推断的。**绝不从
`GroupedMatmul` 的权重 shape 反推专家总数** —— 那个首维只是本 rank 的分片
（DS3.2 上是 16），当成总数会把模型规模少报一个 EP 倍数。

专家清单（`<model-id>_expert_inventory.json`，逐个列出全部 257 个专家及其
`data_state`）由 **stage 2 的 `build_expert_inventory.py`** 生成，不在本 skill：
它需要 `kernel_attribution.json` 判定常驻专家数，也需要 `perf_data.json` 取共享专家
的实测耗时，两者都是 stage 2 的产物。本 skill 只负责把上面三项声明值连同 source_ref
准确提取出来。细节见 stage 2 的 SKILL.md「MoE expert inventory」一节。

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

字段规范、节点来源规则、命名规则、边界规则、**显式数据流边的写法**等**全部细节**见 `references/structure_analysis_guide.md`。SKILL.md 不再重述以避免分歧。

`shape_semantic` 是可选注解，不进入正式门禁：它是叠加在 profiler 维度上的解释，缺失并不说明拆解错误。

---

### Step 3: 校验、评分并迭代拆解

按 `references/structure_analysis_guide.md` §D.2 执行：

统一入口输出**单一合法 JSON**（不要再用 `>>` 拼接多个 JSON 文档到 `issues.json`）：

```bash
python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir /path/to/model-source \
  --semantic-review outputs/semantic_review.json \
  -o outputs/validation_report.json
```

- 校验前必须按 `references/semantic_review_protocol.md` 生成与当前输入哈希绑定的 `semantic_review.json`；九项源码/Trace 语义检查一个不少
- 校验后必须运行 `score_breakdown.py`；仅 semantic review 与 validation 通过、且 score 输出 `convertible=true`（可运行正确率与分项比例达标、hard gates 全过）才生成指标并进入 `cann-perf-breakdown-to-ui-json`
- 未达标时读取 `iteration_request.json`，编辑 `base_config_for_revision` 指向的历史最佳候选副本，只修正 `failed_dimensions`、`blocking_issues` 和 `validation_issues` 命中的内容；不得修改 `immutable_best_snapshot`
- 修正后重新 enrich、重新语义审查、校验、评分；旧 review 不得复用；每轮配置和结果保存在 `iterations/`，直至通过
- `run_breakdown.py` 只负责生成请求和确定性门禁，不会自行调用 AI 改配置；执行本 Skill 的 agent 必须消费 `ai_mapping_request.json` / `semantic_review_request.json` / `iteration_request.json` 并继续循环，不能在 `needs_iteration` 时提前结束
- 默认最多评估 10 轮；每轮读 `iteration_request.json` 的 `remaining_iterations` 决定是否继续。默认不早停；只有显式传 `--stall-limit N` 时才会在连续 N 轮无提升后标记 `blocked_no_progress`
- 完整量表、硬性否决项和防刷分规则见 `references/breakdown_scoring.md`
- 单独调试某一维度时可直接运行 `check_structure.py` / `check_dataflow.py` / `check_op_coverage.py`（各自 `--json` 输出单一 JSON，不要 `>>` 追加）
- `validate_shapes.py` 与 `run_validation.py --with-shapes` 仅供排查，不属于正式流程
- `check_manifest_trace.py`（MT1）默认只作 `info`：一次采集可能只覆盖单个 step 或单个 rank，trace 是辅助证据，不能反驳源码读出的结构；确需阻断时显式传 `--fail-on-trace-mismatch`

---

### Step 4: 计算性能指标

```bash
python scripts/compute_metrics.py \
  -r outputs/raw_ops_details.json \
  -c outputs/analysis_config.json \
  -o outputs/metrics_report.md \
  --findings-out outputs/metrics_findings.json \
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

**诊断建议（咨询性质）**：

`--findings-out` 输出 `metrics_findings.json`，把上表的诊断结论结构化为 `findings[{code, severity, metrics, text, advice_l1, next_data, not_applicable}]`，并按 `references/diagnosis_advice.md` 挂上「下一步该看什么数据」的建议。`metrics_report.md` 末尾同时生成按 `code` 聚类的建议段落。

- `code` 取有限枚举：`STREAM_PARALLEL_HIGH` / `STREAM_PARALLEL_MID` / `GAP_BUBBLE` / `WAIT_DOMINANT` / `UTIL_GOOD` / `UTIL_LOW` / `CLEAN_SEQUENTIAL` / `NORMAL` / `NO_DATA`。
- **建议不进任何门禁**：不参与 `validation_report`、`breakdown_score`、`hard_gates`，不影响上文的两个停止条件，不参与迭代循环。文档中 `advisory_only: true` 是契约的一部分，下游读到该文件必须视其为咨询信息。
- 建议只回答「下一步看什么数据」，**不断言根因**；指标本身不足以证明根因。
- `metric_scope == "aggregate"` 的节点（多 invocation 合并）其 gap/利用率/占比只描述该组总体，**不得外推到单实例**；此类建议自动带 `[聚合口径]` 前缀。
- 建议正文的唯一来源是 `references/diagnosis_advice.md`，改建议只改该文档、不改代码；该文档缺失时静默降级为「无建议」，不影响指标产出。

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `raw_ops.json` | 单 Step kernel 概要（脚本用） |
| `raw_ops_details.json` | 单 Step kernel 详情（Step 4/5 用） |
| `raw_ops.compact.json` | Step 2 投喂 AI 的精简视图 |
| `device_freq.json` | Step 4b AI Core 实测频率与交叉验证；下游所有 cycle 派生指标的分母 |
| `model_manifest.json` | Step 2 架构真值；MoE 模型含 `n_routed_experts` / `n_shared_experts` / `num_experts_per_tok` 三项 fact（各带 source_ref）|
| `dataflow_source.json` | Step 5 从 `forward()` 提取的数据流真值；AI 映射与语义审查都必须引用其边 ID |
| `op_segments.json`（可选） | layer 边界候选 |
| `analysis_config.json` | 拆解配置（Mode A 终版）|
| `model_structure.json` | 仅结构（Mode B）|
| `semantic_review_request.json` / `semantic_review.json` | Step 8 的审查请求与源码/Trace 语义审查结论；绑定三项输入 SHA256 |
| `validation_report.json` | Step 9 统一校验结果（单一 JSON，`status`/`error_count`/`checks`/`issues`）|
| `breakdown_score.json` | Step 10 的 100 分量化评分、分项结果、硬性否决项与修正动作 |
| `iteration_history.json` | 每轮分数、是否提升及历史最佳配置快照 |
| `iteration_request.json` | 未达标时下一轮的定向修正输入；通过后不再使用 |
| `iterations/` | 每一轮 config、validation 和 score 的不可混淆快照 |
| `metrics_report.md` | 性能指标分析报告（含按 code 聚类的诊断建议段落） |
| `metrics_findings.json` | 结构化诊断 + L1 建议，`advisory_only: true`；**不进任何门禁** |

---

## 参考资源

| 文件 | 何时查阅 |
|------|----------|
| `references/structure_analysis_guide.md` | Step 2 拆解 + Step 3 Review 全部规则细节 |
| `references/kernel_data_guide.md` | Step 1 — `kernel_details.csv` 字段说明 |
| `references/mode_b_branches.md` | Mode B 多分支表达约定 |
| `references/mode_c_delegate.md` | Mode C 委托 `cann-npu-perfanalysis` 模板 |
| `references/diagnosis_advice.md` | 诊断码 → L1 建议对照表；建议正文的唯一来源，咨询性质不进门禁 |
| `scripts/extract_model_manifest.py` | Step 2 架构真值提取 → `model_manifest.json`（取 modeling 实际 import 的 config 类；可达时以 checkpoint `config.json` 覆盖默认参数，不可达则降级为 `low` 并记 gap） |
| `scripts/validate_architecture.py` | Step 3 全局架构校验（层号完整/互斥、Dense/MoE、MTP、partial trace）；manifest 为低置信度时 A1/A4 降为 warning，避免门禁强制执行错误层数 |
| `scripts/check_manifest_trace.py` | manifest 层数 × trace per-layer kernel 数交叉校验（MT1），并反推 trace 支持的层数 |
| `scripts/analyze_kernels.py` | Step 4 提取与 enrich |
| `scripts/device_freq.py` | Step 4b AI Core 实测频率 → `device_freq.json`（trace 声明值 × 逐 kernel 反推值交叉验证）|
| `scripts/extract_dataflow.py` | **Step 5 数据流真值提取**：AST 解析 `forward()` 得到调用顺序、残差汇合（含 fused add-norm 与 `+=`）、并行 fork、config-gated 变体；data-dependent 分支记为 `unsupported` 而不猜测 |
| `scripts/check_dataflow.py` | **D1-D7 校验**：配置声明的边必须与源码一致（漏声明残差 / 方向反了 / 绕过了源码没调用的节点 / 并行支路被串行化 / 未声明的数据依赖分支）；无源码时不出结论 |
| `scripts/detect_trace_scope.py` | 可选：trace scope / 并行归属检测。`trace_scope` 已非必填字段，仅在需要标注采集范围时使用 |
| `scripts/segment_layers.py` | layer 边界候选 |
| `references/ai_mapping_protocol.md` | **Step 6 AI 映射规程 + 提示词模板（全 op 归属，禁止 unmapped 冒充）** |
| `references/semantic_review_protocol.md` | **Step 8 源码/Trace 语义审查：Q/K/V、残差、层边界、尾部与 runtime** |
| `references/breakdown_scoring.md` | **Step 10 固定评分体系、硬性否决项、迭代与停止规则** |
| `scripts/map_trace_instances.py` | Step 6 观测 invocation → `trace_instances` 精确映射 |
| `scripts/check_structure.py` | 树结构良构性（v1/v2） |
| `scripts/validate_shapes.py` | 可选排查：shape_semantic 一致性。**不在正式门禁内**，需 `run_validation.py --with-shapes` 才运行 |
| `scripts/check_op_coverage.py` | 精确 op 覆盖（union，非数量外推） |
| `scripts/check_sublayers.py` | 代表结构树子模块一致性（父=子 union、无重叠、主节点有真实 op、模板⊆代表实例） |
| `scripts/prepare_semantic_review.py` / `validate_semantic_review.py` | 生成带哈希的审查请求，并确定性校验证据与输入一致性 |
| `scripts/run_breakdown.py` | **通用 forward-eval 驱动**：缺映射时停在 `awaiting_ai_mapping`，缺失或过期审查时停在 `awaiting_semantic_review`；不伪造 passed |
| `scripts/run_validation.py` | Step 9 统一校验入口，输出单一 JSON |
| `scripts/score_breakdown.py` | Step 10 确定性评分入口，输出 breakdown_score.json |
| `scripts/migrate_config.py` | v1 → v2 迁移（标记 `legacy_unverified`） |
| `scripts/regression_check.py` | 结构回归 + 对 manifest 的语义架构回归（MA1-MA3） |
| `scripts/compute_metrics.py` | Step 11 指标计算 + 结构化诊断/建议（`--findings-out`） |
| `schemas/*.schema.json` | model_manifest / analysis_config_v2 / semantic_review / validation_report / breakdown_score 的严格 schema |
| `adapters/*.py` | 模型族架构提取差异封装（deepseek/gemma/qwen/longcat） |
