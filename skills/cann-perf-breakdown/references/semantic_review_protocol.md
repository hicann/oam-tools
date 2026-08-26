# 模型拆解语义审查协议

确定性脚本能证明 schema、Kernel 覆盖和集合边界正确，但不能仅凭集合判断模型语义正确。正式拆解必须增加 `semantic_review.json`，由执行 Skill 的 AI 在阅读模型源码、配置和代表 step 后填写；脚本负责验证证据、文件版本和结论是否自洽。

## 强制审查项

以下九项必须逐项出现，不能合并或省略：

| ID | 必须确认的内容 |
|---|---|
| `source_model_identity` | manifest、配置和所读源码属于同一模型与变体 |
| `module_inventory_complete` | embedding、所有 decoder 类型、final norm、lm_head、预测模块等均完整 |
| `dataflow_edges_complete` | 结构中的计算先后和输入输出边均与 forward 一致 |
| `branch_topology_correct` | Q/K/V 等并行分支独立，未因相邻或同名 Kernel 错误合并 |
| `residual_paths_correct` | attention/MLP 残差均有正确的两路输入和汇合位置 |
| `layer_boundaries_correct` | Norm、跨层 fused op、每个 invocation 均归入正确层，不跨层抢占 |
| `tail_stages_correct` | final norm、lm_head、sampling/runtime 等尾部阶段归类正确 |
| `runtime_nodes_observed` | runtime 节点确实在本次 Trace 中出现，未按源码臆造执行节点 |
| `code_refs_resolve` | 关键结论使用的源码引用均真实存在且行号有效 |

## 证据规则

- 每个 `passed` 项必须至少有一条 `evidence`。
- 每条证据必须有 `explanation`，并至少提供 `source_ref`、`config_path`、`op_indices` 之一。
- 分支、残差、层边界结论应同时使用源码引用与配置路径或 op 索引，不能只写自由文本。
- `source_evidence` 至少列出一个实际阅读过的 forward/config 源码片段。
- 无法确认时写 `unknown`；发现错误时写 `failed` 并加入 finding。禁止在证据不足时写 `passed`。
- 任一 `failed`/`unknown` 检查，或任一 `error` finding，都会阻断正式评分；`warning` finding 同样阻断，
  唯一例外见下。

### 唯一例外：证据缺口 finding

`source_model_identity` 上的 `warning` finding 报的是**输入不含该标量的证据**（典型情形：采集里没有
checkpoint `config.json`，层数只能取 Python 默认参数），而不是九项语义结论中的任何一项有错。按代码优先
规则，源码是架构真值、trace 不裁定标量，所以它记为证据缺口：验证器发出 `SR_EVIDENCE_GAP_FINDING`
（severity `info`，与 `A1`/`MT1`/`MA1` 同组），不阻断，`detail.evidence_gap_findings` 列出其 id。

**这不是放宽门槛**：未绑定 checkpoint 的上限由 `score_breakdown.py` 的 capture_tier 强制——tier A 把
`source_model_identity` 的 8 分移出分母（`runnable_max` 92 < `MIN_TOTAL_SCORE` 95），结论因此封顶在
`verified_unbound_scalars`，拿不到 `verified`。把它发成 `warning` 反而会让顶层状态变成
`passed_with_warnings` 并被 `GATE_VALIDATION` 判为 `needs_iteration`，即"拆解有错待修"——与事实相反。

例外只覆盖这一个检查上的 `warning`：其他任何检查上的 `warning`，以及这个检查上的 `error`，照旧阻断。

## 文件绑定与迭代

`semantic_review.json.artifacts` 保存 `analysis_config.json`、`raw_ops.json`、`model_manifest.json` 的 SHA256。任何一个文件变化，旧审查立即失效。修改拆解配置后必须重新生成审查请求、重新阅读受影响源码和 Trace，再生成新的审查文件。

先生成请求：

```bash
python scripts/prepare_semantic_review.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir models/<model> \
  -o outputs/semantic_review_request.json
```

AI 按请求中的 `review_template` 填写并保存为 `semantic_review.json`，然后验证：

```bash
python scripts/validate_semantic_review.py \
  -s outputs/semantic_review.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir models/<model>
```

Kernel 100% 覆盖只表示每个 Kernel 有 owner，不表示 Q/K/V、残差或层边界正确；语义审查通过后才允许正式评分和报告生成。
