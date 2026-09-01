# 独立批判协议（Critique Protocol）

本文件定义正式流程中唯一的**独立语义批判**环节。

确定性脚本能证明 schema、索引、Kernel 覆盖和集合边界，但**不能**判断"这个 op 属于 MLP 还是
Attention"。那是语义判断。所以正式拆解必须有第二个环节：一个**没有产出候选拆解**的批判 LLM，
拿着同一批证据独立复查候选，并把发现写成 `critique_report.json`。

## 1. 角色边界（不可越界）

| 角色 | 做什么 | **禁止**做什么 |
|---|---|---|
| Skill | 组织流程、准备证据、规定输出格式、提供候选提示 | 替 LLM 决定模块归属 |
| 拆解 LLM | 阅读源码，完成模块结构拆解与 trace 归属 | 把 hints 当答案照抄 |
| **批判 LLM** | **独立复查候选，只输出问题** | **直接修改 `analysis_config.json`** |
| 确定性脚本 | 只验证可机械证明的事实 | 对语义归属下结论 |

批判器**只出问题，不出修正后的配置**。`repair` 字段只写"修正方向"，不写可直接粘贴的替换结果：
把答案递过去，下一轮就变成抄写而不是拆解，批判也就失去了独立性。

批判 LLM 必须以**候选是可能错的**为前提工作。它的产出不是"我同意"，而是"我按十一项逐项查过，
这些地方与证据矛盾"。

## 2. 最终批判的干净上下文

最终批判不继承拆解会话。Codex subagent 必须使用 `fork_turns=none`；无法创建干净 subagent 时，
驱动停在 `awaiting_final_critique`，由新窗口处理。批判模型只读取当前阶段
`context_manifest.json.inputs`，不得自行遍历输出目录。

| 输入 | 用途 |
|---|---|
| `analysis_config.json` | 被批判的候选拆解 |
| `source_index.json` + `source_bundle_hash` | 源码文件哈希、类/函数、`__init__`/`forward` 行号范围 |
| `source_snippets.json` | 索引确定的必要 `__init__`/`forward` 函数片段；不重新扫描源码树 |
| checkpoint `config.json` | 实例化参数真值（与源码 Python 默认值**不是**一回事） |
| `model_manifest.json` | 架构标量候选 + source_ref |
| `dataflow_source.json` | AST 解出的数据流真值 |
| `raw_ops.compact.json` | 代表 step 的精简 op 序列 |
| `raw_ops.slice.json`（必要时） | 与检查范围相关的 op 切片 |

`prepare_critique.py` 会把这些打包成 `critique_request.json`，并附上输入 SHA256。完整
`raw_ops.json` 只作为正式报告的哈希 binding，不出现在 LLM `inputs` 中。

以下内容即使保留用于审计，也**禁止**进入最终批判上下文：`iterations/` 中的旧 config、validation、
critique、revision request，旧候选，旧批判，拆解聊天记录，Markdown、HTML、UI JSON、截图和浏览器验收产物。

## 3. 十一项强制检查

以下每一项都必须在 `checks[]` 中出现，**不能合并、不能省略**。无法判断时写 `unknown`
（`unknown` 永远不算通过）。

| ID | 必须查什么 |
|---|---|
| `model_identity_and_variant` | manifest、checkpoint config、源码、候选属于**同一模型同一变体** |
| `module_inventory_complete` | 源码明确调用的主模块在候选中一个不少 |
| `learned_layer_vs_invocation` | 学习到的模型层 ≠ 运行时调用；N 次调用不得写成 N 个层 |
| `config_instantiation_params` | 候选用的层数/专家数/头数等来自 checkpoint config，而非未绑定的 Python 默认值 |
| `forward_call_order` | 候选的节点顺序与 `forward()` 实际调用顺序一致 |
| `residual_parallel_skip_topology` | 残差两端、并行 fork 与**真实 rejoin**、skip 均与源码一致 |
| `trace_module_attribution` | 每个 trace op 的 owner 在语义上正确（不只是"有 owner"） |
| `layer_and_fusion_boundaries` | 层边界、跨层融合算子边界归属正确，不跨层抢占 |
| `runtime_vs_model_classification` | 主计算不得进 runtime/excluded；runtime 节点确实在本次 trace 出现 |
| `op_coverage_and_duplicate_ownership` | 覆盖完整**且**无 op 被多个 owner 认领 |
| `source_ref_authenticity` | 候选里每个 `source_ref` 真实存在、行号有效、且指向它声称的构造 |

### 3.1 为什么"100% 覆盖"不能替代这十一项

覆盖率只证明每个 op **有** owner，不证明 owner **对**。把 Attention 的 MatMul 整段塞进 MLP，
覆盖率仍是 100%，`check_op_coverage.py` 仍然全绿。能发现它的只有拿着 `forward()` 读源码的
批判环节。这也是 `trace_module_attribution` 与 `op_coverage_and_duplicate_ownership` 分成
两项的原因：前者查语义，后者查集合。

## 4. 证据规则

- 每个 `passed` 检查至少一条 `evidence`；每条 evidence 必须有 `explanation`，且至少带
  `source_ref` / `config_path` / `op_indices` 之一。
- 每个 issue 必须同时写清 `claim`（候选声称什么）、`expected`（按证据应当是什么）、
  `observed`（实际发现什么）。三者缺一，说明批判还没成形。
- 每个 `severity: error` issue 必须被**恰好一个** `status: failed` 检查的 `issue_ids` 引用；
  若 issue 写了 `check_id`，两者必须一致。禁止只触发全局阻断却让所有质量维度继续显示满分。
- 拓扑类 issue（残差 / 并行 / 层边界）必须同时给 `source_evidence` 与
  `config_paths`；只写自由文本的结论不予采纳。
- 参数类 issue 必须用 `config_evidence` 指向 checkpoint config 的具体键。
- 证据不足时写 `unknown` 并说明缺什么证据。**禁止**在证据不足时写 `passed`，也禁止
  凭猜测编造 issue。

`validate_critique.py` 会确定性地复核：source_ref 是否真的解析到存在的行、op_indices 是否
在代表 step 范围内、config_paths 是否真的解析得到节点。伪造的定位符会被打回。

## 5. 哈希绑定

`artifacts` 保存正式输入的 SHA256，并绑定 `source_index.json` 以及实际提供给批判器的
`raw_ops.compact.json`、`source_snippets.json`、最终 `context_manifest.json`。任何一个输入变化，旧批判**立即失效**：批判的是已经不存在
的字节，对现在的字节什么都没证明。配置改一行，就必须重新走完整批判，不能只复查上一轮的失败项——
只查失败项会漏掉修正本身引入的新错误。
报告中的 `source_ref` 还必须落在已绑定 `source_snippets.json` 的范围内；源码树中存在但未进入白名单的行
不能作为本次批判证据。

```bash
python scripts/prepare_critique.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --dataflow outputs/dataflow_source.json \
  --checkpoint-config models/<model>/config.json \
  --source-index outputs/source_index.json \
  --raw-ops-compact outputs/raw_ops.compact.json \
  --context-manifest outputs/contexts/final_critique/context_manifest.json \
  -o outputs/critique_request.json

# 新窗口或 fork_turns=none 的批判 LLM 只读 context_manifest.inputs

python scripts/validate_critique.py \
  -q outputs/critique_report.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --dataflow outputs/dataflow_source.json \
  --source-index outputs/source_index.json \
  --raw-ops-compact outputs/raw_ops.compact.json \
  --source-snippets outputs/contexts/final_critique/source_snippets.json \
  --context-manifest outputs/contexts/final_critique/context_manifest.json \
  --source-dir models/<model>
```

## 6. 中间定向批判不是最终批判

中间修改阶段使用 `targeted_critique_request.json`、`targeted_critique_report.json`、
`targeted_critique_validation.json` 和独立 `targeted_critique_report.schema.json`。它只检查本轮改动范围，
输入限于当前候选、源码索引与 hash、issue 相关函数片段、raw op 切片。

- 定向批判不能输出 `passed_at_cap`。
- 定向批判不能进入 `score_breakdown.py` 或最终十一项分项。
- 定向通过只表示改动范围没有阻断项，不表示候选整体通过。
- 候选 SHA256 必须相对最近一次已评估快照发生变化，才允许启动新的定向批判；相同候选不得重复审查。
- 定向报告不能把当前确定性 validation 中仍为 error 的同 ID blocker 标成 `passed`；此类冲突报告以
  `TC_DETERMINISTIC_CONFLICT` 拒绝，不能清除 scope，并直接回到 candidate revision，不再次请求批判。
- 涉及 invocation/template/boundary 的 blocker 必须同时核对首个、代表和末尾 invocation；只核对
  representative 不足以通过。差异必须结合源码分支或调用边界解释，不能只按 op 数猜语义。
- 完整十一项只在候选通过全部预终态确定性门禁和必要的定向批判后执行。
- 若最终十一项发现阻断错误，修正后必须先回到中间阶段，再对修正后的候选 SHA256 重做完整十一项。

受控诊断也不是批判：它只在普通 revision 无法定位候选节点/算子证据或错误属于非候选产物时提出
路径受限的补丁。诊断报告不能声明 `passed`/`passed_at_cap`，不能进入评分，也不能替代 targeted 或
最终十一项批判。应用后的派生候选必须重新运行确定性校验；候选变化后再完成对应 targeted critique。

## 7. 与评分的关系

批判结果进入评分，但**不是**评分本身：

- 任一 `severity: error` 的 issue → 阻断，状态 `needs_revision`。
- 十一项里任一 `failed` 或 `unknown` → 阻断。
- 哈希不匹配 → 阻断（视为没有批判）。
- 批判无阻断问题后，才由 `score_breakdown.py` 按
  `quality_rate × evidence_cap` 给分，见 `breakdown_scoring.md`。

批判通过不等于满分：证据上限由输入决定。缺 checkpoint config 的采集即使批判全过，也只能
`passed_at_cap`（上限 90），这是对证据的诚实描述，不是扣分。

## 8. trace 的地位

trace 只能**单向证伪候选拆解**，而且它证伪的对象是候选，不是源码文件：

| 方向 | 含义 | 判定 |
|---|---|---|
| trace 有、候选没有归属 | 该 op 确实执行过而候选漏了 | **阻断** |
| 候选有、trace 没有 | 未执行分支 / 其他 rank 分片 / 被融合 / 本 step 跳过 | 不是错误（记 info） |
| trace 出现无法被模型结构、runtime 或编译融合解释的计算 | 候选与实际执行矛盾 | **必须阻断** |

层数、专家数这类 trace 无法裁定的标量由源码与 checkpoint config 决定；trace 既不能推翻它们，
也不能因为"没能佐证"而扣分。详见 `structure_analysis_guide.md`。
