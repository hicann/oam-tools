# Step 6 — AI 算子映射协议（可执行）

本文件规定 Mode A **Step 6** 中 AI 如何把一个代表性 profiling step 的**全部**算子精确映射到模型结构，产出 schema v2 的 `analysis_config.json`。脚本负责校验，但语义映射由 AI 完成——本协议是该映射的强制操作规程。

> 核心红线：**代表性 step 的每一个 op 都必须获得明确归属**（model / runtime_auxiliary / 严格允许的 excluded）。**禁止**用一个包含几百个索引的 `unmapped_ops` 节点冒充完成。`unmapped_ops` 非空 → 严格校验必然失败。

---

## 1. 必备输入（缺一不可）

开始映射前必须先获得并阅读：

| 输入 | 来源 | 用途 |
|---|---|---|
| `model_manifest.json` | Step 2 `extract_model_manifest.py` | 全局架构真值：主层数、Dense/MoE 层号、learned MTP 层号、source_ref |
| `dataflow_source.json` | Step 5 `extract_dataflow.py` | **数据流真值**：`forward()` 的调用顺序、残差汇合（`merges`）、并行 fork（`forks`）、config-gated 变体（`variants`）、无法静态判定的分支（`unsupported`）。声明 `branches` 时必须引用这里的证据 |
| `raw_ops.compact.json` | Step 4 | 精简 op 序列（折叠重复），用于快速识别阶段边界 |
| `raw_ops.json` | Step 4 | 完整 op 序列（index/name/stream/shape），映射与边界定位的权威依据 |
| `op_segments.json`（可选） | `segment_layers.py` | layer 边界**候选**，仅作起点，最终以源码语义为准 |
| 模型源码 | `models/<model>/` | decoder layer / MTP wrapper / lm_head / embedding 的 forward 语义 |

---

## 2. 映射步骤（固定顺序）

### 2.1 先识别完整执行阶段

在完整 op 序列上，用稳定 anchor 切出宏观阶段边界，先粗后细。

**anchor 必须来自本次模型的源码与 manifest，不得套用固定 kernel 名表**。同一语义在不同模型族、不同后端版本下 kernel 名完全不同（融合与否、量化与否、算子库版本），把某个模型族的名字写成通用规则，就是把适配器该做的事写死在协议里。正确做法是：先从 `dataflow_source.json` 读出该模块 `forward()` 的调用顺序，再在 op 序列里找与之对应的稳定重复段；`adapters/<family>.py` 的 `kernel_anchors` 可提供该族的已知别名作为**候选提示**。

按语义（而非名字）寻找这些边界：

- **attention 起点**：每个 decoder invocation 的第一个注意力主 kernel。
- **layer 尾部**：残差归一（可能与下一层入口 norm 融合成一个 kernel，见 §2.5.1）。
- **MoE 标志**：门控 / 路由 / 分组 GEMM / dispatch-combine 通信。
- **lm_head / logits**：末尾的投影 + 词表维通信/Cast。
- **采样 / verify**：argmax 及 spec token 拼接。
- **runtime bookkeeping**：参数更新、warmup 的集合通信。

用 `stream_id` 辅助区分并行阶段（详见 `structure_analysis_guide.md` §B.4）。

### 2.2 再识别每个 decoder / MTP invocation

对每个观测到的 invocation 建一条 `trace_instances[]` 记录：

- 保存**真实** `op_range`（连续）或 `op_indices`（非连续），覆盖该次调用的全部 op。
- `model_layer_index`：能从源码/manifest 证明就填真实层号；**无法证明**时填 `"unknown"`，但 `layer_group_type` 与算子归属仍必须完成。
- `invocation_index`：同一模型层的第几次调用（MTP 迭代 0/1/2）。
- **MTP/spec decoding**：同一个 learned 层被调用 N 次 → N 条 instance，`model_layer_index` **全部相同**，用 `representative_instance_id` 指向模板实例。**禁止**写成 N 个模型层或伪层号。

### 2.3 代表结构树只复用定义，不替代实例映射

`structures[<layer_group_type>]` 存一棵代表性子结构树（用于报告体积压缩）。它**不**承担覆盖：真正的 op 归属来自 `trace_instances` 的 op_range/op_indices。代表树的叶子可留空 op_indices（报告用 representative 实例 op 计时）。

### 2.4 阶段与 runtime 的归属

- decoder layer 之外、属于模型主干的阶段（embedding、final norm、lm_head、MTP scaffold/output）→ `stages`，重复用 `stage_indices` 折叠。
- 不属于模型主干的运行时逻辑（token verify、sampling、输入更新、graph/step init、每次 MTP 迭代的 gather/all-gather 脚手架）→ `runtime_auxiliary`，重复用 `instance_indices` 折叠。
- 实现细节 op（Cast/Reshape/Transpose、动态量化与反量化）并入最近的真实模块，不单独成节点（§B.1）。

### 2.5 excluded 仅限极少数 profiler/bookkeeping

只有真正不含模型数学、纯 profiler/设备记账的 op 才能进 `excluded_profiler_ops`，且必须用有限 `reason_code` 枚举 + `evidence`：

`profiler_marker` / `stream_sync_placeholder` / `cross_step_bookkeeping` / `device_param_update` / `empty_shape_noop`

**禁止**把 MatMul / Attention / Norm / MoE / 通信 / Gather / KV cache / 采样等主计算算子放入 excluded（脚本 C6 会阻断）。

### 2.5.1 融合 add-norm 链的三段归属策略

许多实现的 decoder layer 尾部那个 add-norm kernel，物理上是**下一层的 input_layernorm**（跨层
fusion：本层 residual + 下一层入口归一化融合成一个 kernel）。是否存在这种融合，从
`dataflow_source.json` 的 `merges[].kind == "fused_in_call"` 判断，不要靠 kernel 名猜。

融合把整个主干串成一条 norm 链，链上每个 norm 都把**上一次调用**遗留的 residual 加进来。链有两个
端点，端点的行为和链内不同，必须分三段判定：

1. **链头**（首层入口）：没有上一次调用，`past_residual is None`，融合退化成一个**独立的 norm
   op**。它属于首层自己，不是任何"上一层的尾部"。这一段会让首层 op 数比其他层多一个，所以代表模板
   应取一个"典型"层而非首层，首层差异在 `instance.note` 标注。
2. **链内**（相邻两层之间）：按约定**归入当前层尾部**（命名如 `input_layernorm_next`），使每个
   invocation 的 op 集合连续、不跨界，也不与下一 invocation 的注意力起点重复计数。相应地，该层的
   注意力残差有一端落在上一次调用里，对应的 `branches[]` 要写成绕回式（见 §2.5.2），下游才会识
   别为跨 invocation 的 carry。
3. **链尾**（最后一次被观测到的层之后）：没有下一层，residual 由**外层模块自己调用的 final norm /
   shared_head_norm** 吸收。这个 norm **必须**登记为 `stages` 里的独立阶段（与 §2.4 一致），
   **不得**当作"下一层的 input_layernorm" 挂在最后一层尾部——那一层根本不存在。同时，最后一层的
   代表模板不能复用链内模板：链内模板带 `input_layernorm_next` 子节点，套在链尾层上会让报告显示一
   个不存在的层尾节点。若 schema 不支持实例级结构覆写，就为它建一个单独的 structure（如
   `<Layer>_final`）。它跨出了 structure 边界的那条残差边，写在顶层 `dataflow.edges`（§2.5.2）。

**判定依据是源码调用点 + 后继拓扑，不是 kernel 名、shape 或 stream。** 链尾 norm 与链内 norm 在
trace 里通常完全同形：同 kernel、同 shape、同 stream，且 invocation 的 op 数也不变（少了一个层尾
norm，但外层 norm 补上），因此 **SL6 这类"op 数与模板不符"的确定性检查抓不到链尾错误**（它只抓得到
链头，因为链头确实多一个 op）。唯一能区分的是后继：链内 norm 后面紧跟下一层的注意力起点，链尾 norm
后面紧跟 lm_head。这一段只能由语义审查（`tail_stages_correct`）把关。

### 2.5.2 显式声明数据流边（残差 / 并行 / skip）

`children` **只表达包含关系**：相邻两个 child 不构成数据流边，下游（Skill 2 建图、Skill 3 渲染）**禁止**从顺序推导连接。残差、并行支路和 skip 全部活在变量传递里（`hidden, residual = norm(hidden, residual)`），在 `children` 顺序上不留痕迹，所以**没有在 `branches` 里声明的边，在下游就等于不存在**。

对每个 structure，逐条对照 `dataflow_source.json` 里该模块的 `merges` 和 `forks`：

- 每个 `merges[]`（含 `kind: fused_in_call` 的融合 add-norm 与 `kind: in_place_add` 的 `+=`）都必须对应一条 `branches[]`。融合形式没有独立的 Add 算子，只看 op 序列是看不出来的——这正是最容易整层丢失残差的地方。
- 每个 `forks[]`（一个值被 2 个以上消费者读取，包括直接读 `forward()` 入参的情形，如共享专家与路由并列）必须声明为 `kind: parallel` 的分支；若把它们写成相邻 children 且不给 branches，下游会把并行支路渲染成串行链。
- `inputs` 是分叉点，`output` 是汇合点，两者之间的兄弟节点就是被绕过的部分。**方向不能反**：起点取在主路径上（两端相邻、中间没有被绕过的节点）会被 D2 判为方向错误。
- 一端落在**上一次调用**的残差（融合 add-norm 的典型形态）应写成绕回式（`inputs` 位置在 `output` 之后），下游据此识别为跨 invocation 的 carry 而不是层内环。把它写成正向反而会复现 G7 要抓的反向残差缺陷。
- `variants`（config-gated 分支，如量化模式/TP 规模）选中哪一支由部署决定：在 `execution_profiles` 里说明本次采集对应的 profile。
- `unsupported`（依赖运行期数据的分支）无法静态判定：必须在 `deviations[]` 里显式声明本次走的是哪一支及理由，否则 D5 阻断。

每条 `branches[]` 都要带 `source_ref`（或 `code_ref`）指向源码行。`check_dataflow.py` 会把这些声明与 AST 重新推导的图逐条比对，D1-D7 任一 error 都会阻断正式流程。

### 2.6 收敛条件

`model_mapped + runtime_mapped + excluded == total_ops`，`unmapped == 0`，`duplicate == 0`，`out_of_range == 0`。任一不满足则继续映射，不得提交。

---

## 3. Step 6 提示词模板（可直接投喂给映射 subagent）

```text
你是 NPU 性能拆解的算子映射专家。目标：把代表性 step 的全部 <TOTAL> 个算子精确映射到本模型的结构，产出 schema v2 的 analysis_config.json。

输入（均已提供，必须全部使用）：
- model_manifest.json：<粘贴或路径>   # 全局架构真值：主层数、Dense/MoE 层号范围、learned 预测层号、source_ref、capabilities
- dataflow_source.json：<路径>         # forward() 的数据流真值：calls/merges/forks/variants/unsupported
- raw_ops.json：<路径>                 # 完整 op 序列（index/normalized_name/stream_id/input_shapes/output_shapes）
- raw_ops.compact.json：<路径>         # 折叠视图，用于先看宏观结构
- op_segments.json：<路径，可选>       # 边界候选，仅参考
- 模型源码切片：<按 code_ref 提供 decoder/预测模块/lm_head/embedding forward>

硬性要求：
1. anchor 只能来自本模型源码与 manifest：先读 dataflow_source.json 得到该模块 forward() 的调用顺序，再在 op 序列里找对应的稳定重复段。禁止套用其他模型族的固定 kernel 名表。
2. 每个 decoder/预测模块 invocation 写一条 trace_instances[]，保存真实 op_range/op_indices，覆盖该次调用全部 op。
3. 同一个 learned 层被外层循环调用 N 次（MTP/spec decoding）= 1 个 learned 层 + N 条 invocation（model_layer_index 相同、invocation_index 递增），禁止写成 N 个模型层或伪层号。
4. model_layer_index 无法证明时填 "unknown"，但 layer_group_type、op 归属仍要完成。
5. embedding/final_norm/lm_head/预测模块 scaffold 与 output → stages（重复用 stage_indices）。
6. token verify/sampling/输入更新/step init/每次迭代脚手架 → runtime_auxiliary（重复用 instance_indices）。
7. 仅纯 profiler/bookkeeping 可进 excluded_profiler_ops，必须带 reason_code 枚举 + evidence；主计算算子禁止 excluded。
8. 全部算子必须落入 model/runtime/excluded 之一；unmapped_ops 必须为空。
9. **数据流边必须显式声明**：dataflow_source.json 里每个 merges[]（含 fused_in_call / in_place_add）对应一条 branches[]；每个 forks[] 声明为 kind: parallel。children 只表达包含关系，未声明的边下游不存在。每条 branches[] 带 source_ref 指向源码行。
10. unsupported[]（依赖运行期数据的分支）必须在 deviations[] 里声明本次走哪一支及理由；variants[]（config-gated）在 execution_profiles 里说明本次对应的 profile。
11. 完成后自检：sum(model,runtime,excluded)==<TOTAL> 且 unmapped==0 且无 duplicate/out-of-range；merges 数量 == branches 覆盖的汇合点数量。

输出：完整 analysis_config.json（schema v2）。随后必须按 `references/semantic_review_protocol.md` 生成并完成 `semantic_review.json`，再把它传给 `run_validation.py` 和 `score_breakdown.py`。只有 semantic review、validation 与 score 都为 passed 才算完成；unmapped>0、duplicate>0、语义审查失败、总分或核心分项未达标一律继续映射。
```

---

## 4. 与校验的闭环

映射产出后先完成 `semantic_review.json`（Step 8），再运行 `run_validation.py`（Step 9）和 `score_breakdown.py`（Step 10）。若任一状态不是 `passed`：

- `coverage.unmapped > 0` → 回到 §2.2/§2.4，把 unmapped 索引逐个归属到真实模块或 runtime。
- `coverage.duplicate > 0` → 两个 owner 争抢同一 op，收紧边界。
- `C6` → 有主计算算子被误放 excluded，移回模型节点。
- `architecture` A1–A9 → 架构与 manifest 不符，回到 Step 2/3。
- `dataflow` D1–D7 → 声明的边与源码不符，回到 §2.5.2 逐条对照 `dataflow_source.json`：D1 漏声明残差、D2 分支方向反了、D3 绕过的是源码没调用的节点、D4 并行支路被写成串行链、D5 未声明运行期分支、D6 源码调用的子模块在结构里没有位置、D7 manifest 声明的 capability 找不到对应 fork/join。
- `semantic_review` → 按源码逐项修复 Q/K/V 分支、残差、layer 边界、final norm/tail/runtime；不得用 100% Kernel 覆盖代替语义证据。
- 读取 `iteration_request.json`，从其中的 `base_config_for_revision` 开始，只修复失败分项与阻断问题，然后重新 enrich、校验和评分。
- 配置修改后必须重新运行 `prepare_semantic_review.py` 并生成新 review；旧 SHA256 review 不得复用。
- 不得降低 95 分总门槛或任何分项最低分，不得用 excluded 隐藏主计算 Kernel，不得删除本应存在的 `branches` 来消除 D2/D3 告警。

探索期可临时用 `--allow-unmapped` 观察分布，但结果状态为 `exploratory`，**不是** `passed`，且报告会显著标注“未验证”，不可作为正式结果。
