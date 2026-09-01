# Step 6 — AI 算子映射协议（可执行）

本文件规定 Mode A **Step 6** 中 AI 如何把一个代表性 profiling step 的**全部**算子精确映射到模型结构，产出 schema v2 的 `analysis_config.json`。脚本负责校验，但语义映射由 AI 完成——本协议是该映射的强制操作规程。

> 核心红线：**代表性 step 的每一个 op 都必须获得明确归属**（model / runtime_auxiliary / 严格允许的 excluded）。**禁止**用一个包含几百个索引的 `unmapped_ops` 节点冒充完成。`unmapped_ops` 非空 → 严格校验必然失败。

---

## 0. 你是最终语义拆解者

**你**（拆解 LLM）负责理解源码并做出归属判断。脚本只校验可机械证明的事实，它们**不会**替你
决定任何模块归属。

因此，下面这些输入全部是**证据或候选，不是自动答案**：

| 输入 | 正确用法 | **错误**用法 |
|---|---|---|
| `model_manifest.json` | 架构标量的候选值 + source_ref，供你核对 | 不读源码就照抄层数 |
| `dataflow_source.json` | AST 解出的数据流真值，声明 `branches` 时引用其边 | 当成完整结构树直接转写 |
| `op_segments.json` | 重复区间**候选提示**，帮你定位边界起点 | 把区间边界当层边界 |
| `adapters/<family>.py` 的 `kernel_anchors` | 该族已知别名的**候选提示** | 按固定 kernel 名表自动归属 |

三条硬性要求：

1. **每个结构节点必须输出 `source_ref`**（或 `code_ref`），指向它在源码中的真实位置。
2. **每个 trace op 必须有唯一 owner**——不能没有，也不能有两个。
3. **不确定时必须显式写 `unknown` / `unmapped`**，并说明缺什么证据。**禁止伪造语义**：编一个
   看起来合理的模块名或 source_ref，比留下 `unknown` 更糟——它会通过格式检查，然后把错误结论
   固化进下游报告。

你的产出会被一个**独立批判 LLM** 按 `critique_protocol.md` 的十一项逐条复查，其中包括
`source_ref_authenticity`（引用是否真实存在且指向它声称的构造）。伪造的引用会被发现。

初始拆解只输出 `analysis_config.json`，不得直接编辑 `model_manifest.json`、raw ops、源码索引或 checker。
若后续校验发现错误属于非候选产物，必须由 checker 的通用 `repair_policy` 进入受控诊断；只有
`diagnostic_request.json.allowed_targets` 中的派生路径可以提出补丁。没有显式授权的未知错误只能诊断，
不能自行扩大写权限。
路径授权只采信当前轮确定性 validation/checker 输出；模型生成的 critique 不具备授权能力。

---

## 1. 必备输入（缺一不可）

开始映射前必须先获得并阅读：

| 输入 | 来源 | 用途 |
|---|---|---|
| `model_manifest.json` | Step 2 `extract_model_manifest.py` | 全局架构真值：主层数、Dense/MoE 层号、learned MTP 层号、source_ref |
| `dataflow_source.json` | Step 5 `extract_dataflow.py` | **数据流真值**：`forward()` 的调用顺序、残差汇合（`merges`）、并行 fork（`forks`）、config-gated 变体（`variants`）、无法静态判定的分支（`unsupported`）。声明 `branches` 时必须引用这里的证据 |
| `raw_ops.compact.json` | Step 4 | 初始映射 LLM 的权威 op 输入；保留 index/name/stream/shape，连续相同项用 `first_index..last_index` 无损折叠 |
| `raw_ops.json` | Step 4 | 确定性校验、enrich 和 revision 切片使用；不进入初始 mapping LLM 上下文 |
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
- `layer_group_type` 指向本次 invocation 使用的 structure template key。若同一 learned owner 因 stream/profiler 差异拆成 A/B/C，三个顶层 structure 都必须显式写相同的 `architecture_group_type` 和各自 `runtime_pattern`；禁止把 pattern 加进 architecture.layer_groups。
- `invocation_index`：同一模型层的第几次调用（MTP 迭代 0/1/2）。
- **MTP/spec decoding**：同一个 learned 层被调用 N 次 → N 条 instance，`model_layer_index` **全部相同**，用 `representative_instance_id` 指向模板实例。**禁止**写成 N 个模型层或伪层号。
- **静态索引调用身份**：源码显式调用 `self.blocks[0](...)`、`self.blocks[1](...)` 时，`[0]` 与 `[1]`
  是两个可证伪的 invocation 身份。候选若展开它们，使用与源码下标对应的 `blocks_0`、`blocks_1`；
  不得把 `[1]` 误配给 `blocks_0`。未展开的 `blocks` 仍可表示共享模板；动态下标 `blocks[i]` 不得猜成
  某个静态索引。只有源码存在同 base 的静态整数下标（包括负整数）时，`_<index>` 才是索引别名。

### 2.3 代表结构树只复用定义，不替代实例映射

`structures[<runtime_template_key>]` 存一棵代表性子结构树（用于报告体积压缩）。顶层结构的
`architecture_group_type` 指向 learned owner，`runtime_pattern` 标识采集模板。它**不**承担覆盖：
真正的 op 归属来自 `trace_instances` 的 op_range/op_indices。代表树的叶子可留空 op_indices
（报告用 representative 实例 op 计时）。

代表模板必须同时用**首个、代表和末尾 invocation**反证。三者只要在计算 op 数、关键 kernel 类型或
后继拓扑上存在结构差异，就不能无证据地共用一个模板；只有源码分支或调用边界支持时才拆出特殊
structure，不能仅凭数量为差异猜语义。首尾与代表完全一致时则保持共享模板，避免按运行次数复制结构。

### 2.4 阶段与 runtime 的归属

- decoder layer 之外、属于模型主干的阶段（embedding、final norm、lm_head、MTP scaffold/output）→ `stages`，重复用 `stage_indices` 折叠。
- 不属于模型主干的运行时逻辑（token verify、sampling、输入更新、graph/step init、每次 MTP 迭代的 gather/all-gather 脚手架）→ `runtime_auxiliary`，重复用 `instance_indices` 折叠。
- 实现细节 op（Cast/Reshape/Transpose/DynamicQuant/Dequant*）并入最近的真实模块，不单独成节点（§B.1）。

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
后面紧跟 lm_head。这一段必须由独立批判的 `layer_and_fusion_boundaries` 检查把关。

### 2.5.2 显式声明数据流边（残差 / 并行 / skip）

`children` **只表达包含关系**：相邻两个 child 不构成数据流边，下游（Skill 2 建图、Skill 3 渲染）**禁止**从顺序推导连接。残差、并行支路和 skip 全部活在变量传递里（`hidden, residual = norm(hidden, residual)`），在 `children` 顺序上不留痕迹，所以**没有在 `branches` 里声明的边，在下游就等于不存在**。

对每个 structure，逐条对照 `dataflow_source.json` 里该模块的 `merges` 和 `forks`：

- 每个 `merges[]`（含 `kind: fused_in_call` 的融合 add-norm 与 `kind: in_place_add` 的 `+=`）都必须对应一条 `branches[]`。融合形式没有独立的 Add 算子，只看 op 序列是看不出来的——这正是最容易整层丢失残差的地方。
- 每个 `forks[]`（一个值被 2 个以上消费者读取，包括直接读 `forward()` 入参的情形，如共享专家与路由并列）必须声明为 `kind: parallel` 的分支；若把它们写成相邻 children 且不给 branches，下游会把并行支路渲染成串行链。
- `inputs` 是分叉点，`output` 是汇合点，两者之间的兄弟节点就是被绕过的部分。**方向不能反**：起点取在主路径上（两端相邻、中间没有被绕过的节点）会被 D2 判为方向错误。
- 一端落在**上一次调用**的残差（融合 add-norm 的典型形态）应写成绕回式（`inputs` 位置在 `output` 之后），下游据此识别为跨 invocation 的 carry 而不是层内环。把它写成正向反而会复现 G7 要抓的反向残差缺陷。
- `variants`（config-gated 分支，如量化模式/TP 规模）选中哪一支由部署决定：在 `execution_profiles` 里说明本次采集对应的 profile。
- `unsupported`（依赖运行期数据的分支）无法静态判定：必须在 `deviations[]` 里显式声明本次走的是哪一支及理由，否则 D5 阻断。

对 whole-model `forward()` 也要逐条对照：当一条源码 activation edge 的两端可唯一匹配到两个
不同的顶层 `stages` / `structures` owner 时，必须在顶层 `dataflow.nodes` 和 `dataflow.edges`
声明该边。不得用 `children` 顺序或空 `model_flow` 代替；无法唯一匹配 owner 时保持未判定，不猜边。

每条 `branches[]` 都要带 `source_ref`（或 `code_ref`）指向源码行。`check_dataflow.py` 会把这些声明与 AST 重新推导的图逐条比对；D10 还会阻断源码已证明、候选却未声明的跨顶层 owner 激活边。

### 2.6 收敛条件

`model_mapped + runtime_mapped + excluded == total_ops`，`unmapped == 0`，`duplicate == 0`，`out_of_range == 0`。任一不满足则继续映射，不得提交。

---

## 3. Step 6 提示词模板（可直接投喂给映射 subagent）

```
你是 NPU 性能拆解的算子映射专家。目标：把代表性 step 的全部 <TOTAL> 个算子精确映射到本模型的结构，产出 schema v2 的 analysis_config.json。

输入（均由当前 `ai_mapping_request.json.context_manifest.inputs` 提供，必须全部使用）：
- source_index.json：<路径>             # 源码文件 SHA256、类/函数、__init__/forward 行号范围及 source_bundle_hash
- model_manifest.json：<粘贴或路径>   # 全局架构真值：主层数、Dense/MoE 层号范围、learned 预测层号、source_ref、capabilities
- dataflow_source.json：<路径>         # forward() 的数据流真值：calls/merges/forks/variants/unsupported
- raw_ops.compact.json：<路径>         # 映射权威 op 序列；repeat 项覆盖 first_index..last_index 的全部连续索引
- 模型源码：<model_sources 路径列表>  # 仅首次 mapping 可完整读取；后续 revision 禁止重新扫描
- analysis_config_v2.schema.json：<路径> # 完整候选的正式输出 schema
- ai_mapping_protocol.md / breakdown_scoring.md：<路径> # 当前映射与停止/评分契约

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

输出：完整 analysis_config.json（schema v2）。随后由**未产出该候选的批判 LLM**按
`references/critique_protocol.md` 的分层流程处理：先运行确定性预终态门禁；中间修正只做定向批判；
全部预终态门禁通过后才在干净上下文完成最终十一项检查，再运行 `score_breakdown.py`。只有
`breakdown_score.passed_at_cap == true` 才算完成；不得用 `convertible`、`final_score >= 95`
或 100% Kernel 覆盖替代正式门禁。
```

---

## 4. 与校验的闭环

映射产出后写入 `source_scan_receipt.json`，之后禁止向任何修正或批判 LLM 重新投喂源码树。
首次映射以及源码 bundle 漂移后的重新映射，候选提交给驱动时都必须用 `--source-bundle-hash`
携带当前 `ai_mapping_request.json.source_bundle_hash`。驱动同时校验 mapping request/context 中固化的
`source_index_sha256`，防止候选生成后索引元数据被替换。
每个阶段只读取其 `context_manifest.json.inputs`。若预终态门禁或最终门禁未通过：

- `coverage.unmapped > 0` → 回到 §2.2/§2.4，把 unmapped 索引逐个归属到真实模块或 runtime。
- `coverage.duplicate > 0` → 两个 owner 争抢同一 op，收紧边界。
- `C6` → 有主计算算子被误放 excluded，移回模型节点。
- `architecture` A1–A9 → 架构与 manifest 不符，回到 Step 2/3。
- `dataflow` D1–D10 → 声明的边与源码不符，或源码证明的跨顶层 owner 激活边未声明；回到 §2.5.2 定向修正。D10 只允许修改 `$.dataflow`，不得借机改源码、校验器、`stages` 或 `structures`。
- `critique_report` → 按 issue 的源码函数片段、候选路径与 trace 定位符重新阅读证据，修复 Q/K/V
  分支、残差、layer/fusion 边界、final norm/tail/runtime 等真实错误；批判只指出问题，不给可照抄配置。
- 读取当前 `revision_request.json` 白名单，只修复失败分项与阻断问题；不得读取 `iterations/` 或旧 config/validation/critique/revision request。
- 配置修改后先重新运行确定性校验和与改动范围对应的 targeted critique。定向报告使用独立 schema，不能产生 `passed_at_cap`，不能评分。
- 修正候选再次通过全部预终态门禁后，必须由干净上下文（新窗口或 `fork_turns=none`）对当前 SHA256 完整重做十一项；旧 critique 不得复用。
- 默认最多 4 次语义修正，`stall-limit=2`；进展只指 deterministic error、hard gate、unmapped、duplicate、out-of-range 或定向批判阻断项减少。
- 不得降低 `quality_rate >= 0.95` 或任何分项最低比例，不得用 excluded 隐藏主计算 Kernel，不得删除本应存在的 `branches` 来消除 D2/D3 告警。

探索期可临时用 `--allow-unmapped` 观察分布，但结果状态为 `exploratory`，**不是** `passed`，且报告会显著标注“未验证”，不可作为正式结果。
