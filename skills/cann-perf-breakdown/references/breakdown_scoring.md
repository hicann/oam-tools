# 模型拆解评分与迭代协议

本协议用于 Mode A 的正式拆解。评分不是代替源码审查，而是把源码、trace 和统一校验器已经产出的证据转换为稳定、可比较的质量门槛。

## 1. 通过条件

一次拆解只有同时满足以下条件才可转换为正式下游报告：

1. 可运行检查正确率 `score / runnable_max >= 95%`。`score` 仍位于固定 100 分名义量表，不能单独作为门禁；输入确实缺失而无法运行的检查只退出 `runnable_max`，并通过证据结论降级明确披露。
2. **每个可运行核心维度**都达到原最低比例：

   | 维度 | id | 满分 | 最低分 |
   |---|---|---:|---:|
   | 架构完整性 | `architecture_integrity` | 25 | 22 |
   | 数据流与分支正确性 | `dataflow_branch_correctness` | 30 | 27 |
   | Layer/子模块边界 | `layer_submodule_boundaries` | 20 | 18 |
   | Kernel 精确覆盖 | `kernel_exact_coverage` | 20 | 20 |
   | 证据与可追溯性 | `evidence_traceability` | 5 | 4 |

   **两道门必须都能独立生效**：核心分项最低比例和总正确率分别检查，某项被真实输入缺口判为不可运行时不得把它记为满分，也不得让它把正确拆解永久挡死。Kernel 覆盖与证据项始终可运行，仍按原门槛执行。

   原“Shape 与语义一致性”和“Trace 实例与 scope”两项已删除，其 20 分并入数据流（+10）与架构（+5）以及 Kernel 覆盖（+5）。删除原因：`shape_semantic` 缺失、以及一次采集只覆盖单个 step，描述的是**输入里有什么**，而不是**拆解对不对**——这两项给“不可能出错的证据”发分，既无法否证也无法区分好坏。取而代之的两项都可由源码机器校验。

   扣分粒度为每个 `warning` 扣该检查权重的 20%（`WARNING_STEP`）。此前 quality 只取 {1.0, 0.6, 0.0}，任一 warning 即扣 40%，使“27/30”这类分数门槛实际等价于“零 warning”——看似分级实为二元。现在单个 warning 可容忍，成堆 warning 不可。
3. 所有硬性否决项为零。
4. `semantic_review.json` 的九项检查和总状态必须全部为 `passed`，且输入 SHA256 未过期。
   唯一例外是 `source_model_identity` 上的证据缺口 `warning` finding：它报的是输入不含该标量，
   而非语义结论有错，记为 `info` 不阻断（见 `semantic_review_protocol.md`「唯一例外」一节）。
   该情形的上限由下述 capture_tier 机制强制，不靠 validation 状态兼职。
5. `run_validation.py` 的状态必须为 `passed`；`passed_with_warnings` 和 `exploratory` 只能用于排查，不能生成正式报告。
   数据可用性类问题（`A1`/`MT1`/`MA1`/`SR_EVIDENCE_GAP_FINDING`）一律发 `info`：它们报的是输入缺少某个
   标量的证据，而不是拆解错误，因此不该把状态推离 `passed`。真正的上限由 capture_tier 施加——tier A
   把 `source_model_identity` 的 8 分移出分母，`runnable_max` 92 低于 95，结论封顶
   `verified_unbound_scalars`。若改用 `warning`，这类采集会被 `GATE_VALIDATION` 判成
   `needs_iteration`，把"输入缺证据"误报成"拆解待修"。

最终 `status` 表达证据所能支持的结论：`verified`、`verified_unbound_scalars`、`structure_unverified`、`exploratory` 或 `needs_iteration`。前三者 `convertible=true`；`passed` 仅为 pre-tier 历史兼容值。门槛是 Skill 的质量基线，迭代时禁止降低。

## 2. 100 分量表

| 维度 | 分值 | 主要证据 |
|---|---:|---|
| 架构完整性 | 25 | architecture/regression + `source_model_identity`/`module_inventory_complete` |
| 数据流与分支正确性 | 30 | **`check_dataflow.py` 的 D1-D7**（源码 `forward()` 与配置声明边的一致性）+ structure/sublayers + Q/K/V 分支与残差语义审查 |
| Layer/子模块边界 | 20 | structure/coverage/sublayers + layer/tail/runtime/code-ref 语义审查 |
| Kernel 精确覆盖 | 20 | model/runtime/excluded 对代表 step 的精确并集，要求 missing/duplicate/out-of-range/unmapped 全为零 |
| 证据与可追溯性 | 5 | source_of_truth、code_ref、manifest source_ref 和 evidence_gaps |

数据流成为最高权重维度（30），因为它是唯一既最容易出错、又能被源码确定性判定的部分：`forward()` 就是数据流图，声明与源码不符可以机器判定，不需要依赖 AI 自述。

`shape_semantic` 与 `trace_scope` 仍可作为可选注解存在于配置中，但不参与评分，也不进入 `run_validation.py` 的正式门禁。

`scripts/score_breakdown.py` 只从结构化产物计算分数，不接受自由填写总分。

## 3. 硬性否决项

下列任一项存在时，即使总分达到 95 也必须重新拆解：

- unified validation 不是 `passed`。
- 缺少 `semantic_review.json`、审查失败，或 artifact SHA256 与当前 config/raw/manifest 不一致。
- `unmapped_ops` 非空，或 coverage 的 unmapped/missing/duplicate/out_of_range 非零。
- v1 迁移结果仍为 `legacy_unverified`。
- Mode A 缺少源码真值或结构节点没有可用 `code_ref`，却声称精确模型映射。
- 校验 issue 已发现学习层数、MTP invocation、Dense/MoE、Q/K/V、残差或 layer 边界冲突。
- `check_dataflow.py` 报出 error 级 D1/D2/D5：源码有残差汇合而配置未声明任何 `branches`（D1）、声明的分支方向反了且没有绕过任何节点（D2）、或源码存在依赖运行期数据的分支而配置未在 `deviations` 中显式声明所走分支（D5）。这三项都是「配置与源码直接矛盾」，不是覆盖率或注解问题。

> 无源码时 `check_dataflow` 不出结论（检查缺席，而非通过）。缺席不构成否决，但也不能充当已校验的证据——正式流程要求 Mode A 提供源码。

不得通过删除主计算 Kernel、扩大 `excluded_profiler_ops`、伪造 source_ref、合并本应独立的分支或降低阈值来消除失败项。

## 4. 闭环迭代

每一轮严格执行：

1. 基于源码、manifest、raw_ops 和 `dataflow_source.json` 生成候选 `analysis_config.json`。
2. 运行 enrich，生成 `semantic_review_request.json`；AI 完整核对源码与 Trace 后填写 `semantic_review.json`。
3. 运行 `run_validation.py` 和 `score_breakdown.py`。
4. 若通过，才运行 report/metrics。
5. 若未通过，读取 `iteration_request.json`，只针对 `blocking_issues`、`failed_dimensions` 和 `required_actions` 修正配置，然后从第 2 步重新执行。

每次 `analysis_config.json` 发生变化都必须重新审查。旧 review 哈希失效时，驱动停在 `awaiting_semantic_review`，该候选不会作为低分轮次写入历史。

驱动本身不会调用 AI 修改候选。执行 Skill 的 agent 必须读取并消费 `ai_mapping_request.json`、`semantic_review_request.json` 和 `iteration_request.json`，持续完成映射、审查与定向修正；只有通过、达到停止条件或确实缺少新证据时才能结束。

`run_breakdown.py` 会将每轮输入与评分保存到 `iterations/`，并维护 `iteration_history.json`。下一轮编辑 `iteration_request.json.base_config_for_revision` 指向的候选副本；`immutable_best_snapshot` 只读、不得原地修改。候选分数下降时，不得把下降版本当作新的基线。

## 4.1 停止条件

只有两个终止条件：

1. **达标停止**：`breakdown_score.convertible == true`（可运行正确率 `>= 95%` + 可运行核心维度达最低比例 + 硬性否决项为零 + validation/semantic review 均 `passed`）。结论状态说明证据层级，不得把 `verified_unbound_scalars` 的名义分数低于 95 误判为需要迭代。
2. **轮次上限停止**：评估轮次达到 `--max-iterations`（默认 **10**）仍未达标，状态为 `blocked_max_iterations`。

默认**不再**因"连续两轮无提升"提前退出：`--stall-limit` 默认为 `0`（关闭早停），循环会一直跑到达标或第 10 轮。需要早停时显式传 `--stall-limit N`（例如 `--stall-limit 3`），此时连续 N 轮既没超过历史最佳分数、也没减少阻断项/失败维度才会标记 `blocked_no_progress`。

分数相同时，阻断项或失败维度减少也算有效进展。每轮的 `iteration_request.json` 会给出 `remaining_iterations` 和 `consecutive_non_improving_rounds`，agent 必须据此继续迭代，不能在 `needs_iteration` 时提前结束，也不能用无限重复同一候选来假装迭代。

达到 `blocked_max_iterations` 时，必须在收尾输出中写明：当前分数、每个未达标维度的分差、以及**为什么拆解仍不正确**的根因（缺哪类证据、哪个语义检查过不去），而不是只报一个分数。

## 5. 输出约定

| 文件 | 含义 |
|---|---|
| `breakdown_score.json` | 当前轮总分、分项分数、硬性否决项和修正动作 |
| `semantic_review_request.json` / `semantic_review.json` | 当前候选的审查任务与带证据结论 |
| `iteration_history.json` | 所有轮次的分数、是否提升、历史最佳配置快照 |
| `iteration_request.json` | 下一轮只需处理的失败维度、阻断问题与约束 |
| `iterations/iteration_N_analysis_config.json` | 第 N 轮候选配置快照 |
| `iterations/iteration_N_semantic_review.json` | 第 N 轮语义审查快照 |
| `iterations/iteration_N_validation_report.json` | 第 N 轮统一校验结果快照 |
| `iterations/iteration_N_breakdown_score.json` | 第 N 轮评分快照 |
