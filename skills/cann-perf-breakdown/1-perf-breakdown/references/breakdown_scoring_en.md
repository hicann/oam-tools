# 模型拆解评分与迭代协议

本协议用于 Mode A 的正式拆解。评分不是代替源码审查，而是把源码、trace 和统一校验器已经产出的证据转换为稳定、可比较的质量门槛。

## 0. 三个独立值（先读这一节）

评分输出三个**分别报告、互不折叠**的值：

| 值 | 含义 | 是否为门禁 |
|---|---|---|
| `quality_rate` | 当前可检查项目的正确率，0～1 | **是**，`>= 0.95` |
| `evidence_cap` | 输入证据允许的最高分 | 否，是上限 |
| `final_score` | `quality_rate × evidence_cap` | **否，仅描述** |

### 0.1 证据上限表（固定）

| 输入 | evidence_cap |
|---|---:|
| 源码 + checkpoint config + trace | 100 |
| 源码 + trace，无 checkpoint config | 90 |
| 源码 + checkpoint config，无 trace | 75 |
| 只有源码 | 65 |
| config + trace，无源码 | 45 |
| 只有 trace | 30 |
| 只有 config | 25 |

上限**只取决于输入有什么**，不因拆解得分高而上移。

**必须区分 checkpoint `config.json` 与源码中的 Python 默认参数**：Python 默认值可能在部署时被
checkpoint 覆盖，所以它**不算**已绑定 checkpoint（`evidence_level=4`）。把默认值当成已绑定参数，
就是让一个无法核实的层数拿到满分。以下三种才算绑定：交付了 `config.json`（level 1）、有真实
加载打印的记录（level 2）、或有与本次采集同源的 source snapshot 使 AST 默认值即实际值（level `2S`）。

### 0.2 为什么不能用 `final_score >= 95` 做门禁

**禁止**重新使用 `final_score >= 95`。上限 90 的输入永远达不到 95，用乘积做门禁等于因为缺一个
拆解者无法控制的输入而永久判其失败——这正是同样正确的拆解在三个采集上得出三个结论的原因。
上限 90 且质量达标的拆解，状态是 `passed_at_cap`，这是**完整通过**，不是打折通过。

---

## 1. 通过条件

`passed_at_cap` 需要**同时**满足三条，缺一不可：

1. **批判无阻断问题**：`critique_report.json` 十一项全为 `passed`（`unknown` 不算通过）、无
   `error` issue、且 `artifacts` 哈希绑定当前输入。
2. **质量达标**：`quality_rate >= 0.95`，且每个可运行核心维度达最低比例。
3. **全部 hard gates 通过**（见 §3）。

历史遗留的可运行正确率口径（`score / runnable_max`）与 `quality_rate` 同义，保留用于兼容旧产物：
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
4. `critique_report.json` 的十一项检查和总状态必须全部为 `passed`，且输入 SHA256 未过期；
   `validate_critique.py` 必须确认报告可采纳且 `detail.clears_candidate=true`。
5. `run_validation.py` 的状态必须为 `passed`；`passed_with_warnings` 和 `exploratory` 只能用于排查，不能生成正式报告。
   数据可用性类问题（`A1`/`MT1`/`MA1`/`SR_EVIDENCE_GAP_FINDING`）一律发 `info`：它们报的是输入缺少某个
   标量的证据，而不是拆解错误，因此不该把状态推离 `passed`。真正的限制由 `evidence_cap` 与
   capture tier 表达；例如无 checkpoint config 的源码 + trace 输入封顶 90，结论可标为
   `verified_unbound_scalars`，但不会因此降低 `quality_rate`。

最终 `status` 表达证据所能支持的结论：`verified`、`verified_unbound_scalars`、`structure_unverified`、`exploratory` 或 `needs_iteration`。`convertible` 与 `passed` 仅为旧消费者兼容字段；正式下游只读取 `passed_at_cap`。门槛是 Skill 的质量基线，迭代时禁止降低。

## 2. 100 分量表

| 维度 | 分值 | 主要证据 |
|---|---:|---|
| 架构完整性 | 25 | architecture/regression（9）+ critique 的 identity/inventory/learned-vs-invocation/config params（16） |
| 数据流与分支正确性 | 30 | dataflow/structure/sublayers（17）+ critique 的 forward order/residual topology/trace attribution（13） |
| Layer/子模块边界 | 20 | structure/coverage/sublayers（8）+ critique 的 layer/fusion boundary 与 runtime/model classification（12） |
| Kernel 精确覆盖 | 20 | 确定性精确覆盖（15）+ critique 的 coverage/duplicate ownership（5） |
| 证据与可追溯性 | 5 | source/code/manifest refs（3）+ critique 的 source-ref authenticity（2） |

十一项 critique 检查在上表中**恰好进入一次**，没有只做全局否决而不反映分项质量，也没有重复计分。
确定性脚本只给它们能机械证明的部分；模块归属与 trace 语义仍由独立批判判断。

`shape_semantic` 与 `trace_scope` 仍可作为可选注解存在于配置中，但不参与评分，也不进入 `run_validation.py` 的正式门禁。

`scripts/score_breakdown.py` 只从结构化产物计算分数，不接受自由填写总分。

## 3. 硬性否决项

下列任一项存在时，无论 `quality_rate` 或 `final_score` 多高，都不得通过：

**十项核心否决项**：

1. trace 主计算 op 没有 owner
2. 同一 op 有多个 owner
3. 主计算 op 被放入 profiler excluded
4. runtime invocation 被写成多个 learned layer
5. 源码明确调用的主模块在候选结果中缺失
6. 候选包含源码无法解释且未声明 deviation 的模块
7. 残差、并行或 skip 拓扑与源码矛盾
8. 伪造或错误 source_ref
9. checkpoint config 与源码/候选属于不同模型变体
10. critique 报告未绑定当前输入文件哈希

**其余否决项**：

- unified validation 不是 `passed`。
- 缺少 `critique_report.json`、批判失败，或 artifact SHA256 与当前 config/raw/manifest/dataflow 不一致。
- `unmapped_ops` 非空，或 coverage 的 unmapped/missing/duplicate/out_of_range 非零。
- v1 迁移结果仍为 `legacy_unverified`。
- Mode A 缺少源码真值或结构节点没有可用 `code_ref`，却声称精确模型映射。
- 校验 issue 已发现学习层数、MTP invocation、Dense/MoE、Q/K/V、残差或 layer 边界冲突。
- `check_dataflow.py` 报出 error 级 D1/D2/D5：源码有残差汇合而配置未声明任何 `branches`（D1）、声明的分支方向反了且没有绕过任何节点（D2）、或源码存在依赖运行期数据的分支而配置未在 `deviations` 中显式声明所走分支（D5）。这三项都是「配置与源码直接矛盾」，不是覆盖率或注解问题。

> 无源码时 `check_dataflow` 不出结论（检查缺席，而非通过）。缺席不构成否决，但也不能充当已校验的证据——正式流程要求 Mode A 提供源码。

不得通过删除主计算 Kernel、扩大 `excluded_profiler_ops`、伪造 source_ref、合并本应独立的分支或降低阈值来消除失败项。

## 4. 分层修正闭环

严格按阶段执行：

1. 首次完整扫描源码并生成 `source_index.json`；首次候选完成后记录 `source_scan_receipt.json`。
   后续重入只重算文件清单与 SHA256，不再解析 AST；仅在 bundle 漂移时废弃 receipt 并重新完整扫描。
2. 运行 `run_validation.py` 的预终态确定性门禁。
3. 中间修正只生成白名单 `revision_request.json`，并运行与改动范围对应的 targeted critique。
   若错误不属于候选或无法形成定向证据，转入一次受控诊断；不得扩大普通 revision 白名单。
4. 候选通过全部预终态确定性门禁和必要的定向批判后，才生成最终 `critique_request.json`。
5. 最终十一项批判通过确定性验收后，`score_breakdown.py` 才使用它评分；成功路径完整批判只运行一次。
6. 最终批判发现阻断项时回到步骤 2；修正后的候选必须以新 SHA256 重做最终十一项，旧报告不得复用。

中间阶段不运行完整批判，也不评分。`targeted_critique_report.json` 使用独立 schema，不能产生
`passed_at_cap`，`score_breakdown.py` 必须以 `GATE_CRITIQUE_NOT_FINAL` 拒绝它。

驱动本身不会调用 AI 修改候选。执行 Skill 的 agent 必须读取并消费 `ai_mapping_request.json`、`critique_request.json` 和 `revision_request.json`，持续完成映射、批判与定向修正；只有通过、达到停止条件或确实缺少新证据时才能结束。

`revision_request.json` 只提供 normalized issue、当前候选、`source_index`/bundle hash、issue 相关函数片段和 raw op 切片，不提供硬编码修复结果。旧 config、validation、critique、revision request 及 Markdown/HTML/UI/截图产物不能出现在当前 LLM 请求的 `inputs` 中。

受控诊断使用独立 `diagnostic_request.json` / `diagnostic_patch.json`。checker 通过通用
`repair_policy` 声明 owner、允许目标/路径、必需证据与 trace selector；中央路由不得识别模型族或
issue ID。补丁只可写派生 `analysis_config` 或 `manifest_hypothesis`，必须绑定请求和基础产物 SHA256，
并经确定性验证/应用后重新进入预终态门禁。原始证据、基础 manifest、校验器与 Skill 代码不可写。
只有驱动在当前轮新生成的确定性 validation/checker 输出可授权 `repair_policy`；LLM critique 中的同名
字段必须忽略，避免批判模型自行扩大 `allowed_targets`。
`insufficient_external_evidence` 与 `tool_defect` 不消耗语义修正额度，也不得进入评分。

进展按六类阻断计数判定：deterministic error、hard gate、unmapped、duplicate、out-of-range、
定向批判阻断项。只有至少一类减少且其他类不增加才算进展；分数变化本身不算进展。

候选与最近一次 iteration 快照的 SHA256 相同时不启动 targeted critique，直接按无进展处理。targeted
报告不能覆盖确定性结论：它若把当前 validation 中仍为 error 的同 ID blocker 判为 `passed`，报告无效
且不得清除预终态 scope。这两个门禁只减少重复审查，不改变评分项或 evidence cap。

`run_breakdown.py` 可将历史快照保存到 `iterations/` 供审计，但这些文件不得被后续请求引用。
每个阶段生成自己的 `contexts/<stage>/context_manifest.json`，`inputs` 是唯一允许模型读取的白名单。

## 4.1 停止条件

终止条件：

1. **达标停止**：`breakdown_score.passed_at_cap == true`（`quality_rate >= 0.95` + 可运行核心维度达最低比例 + 硬性否决项为零 + 批判无阻断问题 + validation `passed`）。不得把上限低于 95 的 `final_score` 误判为需要迭代。
2. **无进展停止**：连续 `--stall-limit` 轮无进展（默认 **2**），状态为 `blocked_no_progress`。
3. **修正上限停止**：语义修正达到 `--max-revisions`（默认 **4**），状态为 `blocked_max_revisions`；
   `--max-iterations` 保留为旧 CLI 兼容别名。

默认启用无进展早停。`--stall-limit 0` 只为旧调用兼容，显式传入时可关闭早停。

`revision_request.json` 给出 `remaining_revisions` 和 `consecutive_no_progress`。达到停止状态后不得继续用同一候选假装迭代。
初始候选失败是进展基线，不消耗修正额度。阻断终态持久化到 `iteration_history.json`；同一 model/CSV/out
组合再次调用时直接返回该终态。首次候选与源码漂移后的新候选都须显式传入匹配的
`--source-bundle-hash`，且 mapping request/context 中的 index SHA256 必须仍匹配，才能记录 scan receipt。

达到 `blocked_max_revisions` 或 `blocked_no_progress` 时，必须在收尾输出中写明六类阻断计数、当前分数（若已进入最终评分）、未达标维度和根因，而不是只报一个状态。

## 5. 输出约定

| 文件 | 含义 |
|---|---|
| `breakdown_score.json` | 当前轮总分、分项分数、硬性否决项和修正动作 |
| `source_index.json` / `source_scan_receipt.json` | 单次源码扫描索引、bundle hash 与扫描收据 |
| `contexts/<stage>/context_manifest.json` | 当前 LLM 请求唯一输入白名单 |
| `targeted_critique_request/report/validation.json` | 中间定向批判，禁止进入评分 |
| `critique_request.json` / `critique_report.json` | 当前候选的批判任务与带证据的问题清单 |
| `critique_validation.json` | 对批判证据的确定性复核；`detail.clears_candidate` 才是放行信号 |
| `iteration_history.json` | 所有轮次的分数、是否提升、历史最佳配置快照 |
| `revision_request.json` | 下一轮只处理当前 normalized issue 与对应源码/op 切片 |
| `iterations/iteration_N_analysis_config.json` | 第 N 轮候选配置快照 |
| `iterations/iteration_N_*critique*.json` | 审计快照；不得进入任何后续 LLM `inputs` |
| `iterations/iteration_N_validation_report.json` | 第 N 轮统一校验结果快照 |
| `iterations/iteration_N_breakdown_score.json` | 第 N 轮评分快照 |
