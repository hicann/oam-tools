# npu-perf-analysis Skill 评测用例集

本文件包含 5 个标准评测场景，用于验证 `npu-perf-analysis` Skill 的分析正确性。每个用例定义了输入条件、预期输出结构和可验证的关键断言。

---

## 用例 1：MoE 模型预热步识别 + 等待锚点检测

**场景描述**  
分析 Gemma MoE 推理模型的 profiling 数据，需正确识别预热步、MoE 模型特征，以及等待锚点假热点。

**输入**
```
数据路径：prof-data/gemma/ASCEND_PROFILER_OUTPUT/
用户问题：帮我分析这份 NPU profiling 数据，看看有没有性能问题。
```

**预期输出结构**
- 包含"分析上下文"章节：列出文件清单、Schema 版本（V2）、步骤数（3）、设备数（1）
- 包含"迭代效率"章节：含 Step 3/4/5 的时间拆分表格
- 包含"算子热点"章节：Top-10 算子表格
- 包含"等待锚点"章节：列出被标记的 kernel
- 包含"瓶颈诊断"章节：包含 P0–P3 分级
- 包含"优化建议"章节
- 同时生成 Markdown 报告和 HTML 报告

**关键断言**

**断言 1.1** — 预热步标注  
Step 3 的 `CommNO=51.6%` 与 Step 4-5 的 `CommNO≈8-10%` 差距超 20%，报告必须将 Step 3 标注为"疑似预热步，不具代表性"，且不参与正常步均值计算。

**断言 1.2** — 正常步瓶颈判定  
基于 Step 4-5 的平均数据：
- `computing_ratio ≈ 70%`，`free_ratio ≈ 21%`（超过 10% 警告线）
- 报告须注明"Free Time 偏高（约 21%），可能存在轻微 Host Dispatch 延迟"，但因未超过严重阈值 2 倍，不应判定 P0

**断言 1.3** — MoE 模型特征检测  
算子热点章节须出现以下 MoE 特征算子，并说明其为 MoE 架构的正常计算开销：
- `MoeGatingTopKSoftmax` / `MoeComputeExpertTokens` / `GroupedMatmul` / `MoeInitRouting`

**断言 1.4** — 等待锚点检测  
等待锚点章节须包含至少 1 条：
- `AivKernel`：`wait_ratio ≈ 99.96%`，`Duration ≈ 6μs`，`Wait ≈ 16293μs`
- 明确标注"假热点，按 total_cost 排名靠前，但实际计算时间极短，真实原因在上游"

**断言 1.5** — 不错误推荐  
报告的优化建议中，**不应**出现"优化 MatMul 算子实现"或"减少通信量"等明显不对症的建议。

---

## 用例 2：Host Dispatch 严重瓶颈识别

**场景描述**  
分析 Qwen-7B Dense 模型的 profiling 数据，该数据集的特征是 Free Time 极高（约 82%）、无通信操作。

**输入**
```
数据路径：prof-data/qwen7b/ASCEND_PROFILER_OUTPUT/
用户问题：为什么这个模型训练很慢？效率低在哪里？
```

**预期输出结构**
- 维度 4（通信效率）：明确标注"跳过：无通信数据（CommNO=0，Overlap=0）"
- 维度 8（多卡均衡）：明确标注"跳过：仅有单卡数据（Device_id=0）"
- 包含 P0 瓶颈诊断
- 优化建议至少包含一条针对 Host Dispatch 的具体措施

**关键断言**

**断言 2.1** — P0 Host Dispatch 瓶颈  
Step 2-4 的 `free_ratio` 均约 81-83%，报告须输出：
- 优先级：**P0**
- 标签：`HOST_DISPATCH_BOTTLENECK`
- 证据：`free_ratio = 82%（Step 2）/ 81%（Step 3）/ 81%（Step 4）`，超过严重阈值 10% 的 8 倍

**断言 2.2** — 不推荐通信优化  
优化建议中，**绝对不能**出现任何关于"通信"、"AllReduce"、"overlap"的优化建议（该数据集 Communication 全为 0）。

**断言 2.3** — 首要建议指向 Host 侧  
P0 的优化建议须包含以下方向之一：
- 减少算子下发次数（算子融合、图编译）
- 检查 PyTorch eager 模式小算子碎片化
- 使用 torch.compile 或 mindspore 图模式

**断言 2.4** — 算子热点正确列出  
`MatMulV2` 以 `Ratio=66.2%` 排名第一，但报告须区分"绝对热点"与"相对重要性"：在 free_ratio=82% 的情况下，设备实际有效执行时间仅约 18%，MatMul 的真实影响被放大；首要问题是 Host Dispatch，而非 MatMul 本身效率。

---

## 用例 3：多步采集 + 单设备 + 预热步识别

**场景描述**  
分析 DeepSpeed 3.2 的 profiling 数据（Device_id=3，采集了 10 步），需正确识别预热步，并在单设备数据中诊断瓶颈。

**输入**
```
数据路径：prof-data/ds3.2/ASCEND_PROFILER_OUTPUT/
用户问题：分析一下这张卡的训练性能，有没有瓶颈？
```

**预期输出结构**
- 分析上下文须注明：Device_id=3，步骤数=10（Step 10-19）
- 维度 8（多卡均衡）：明确标注"跳过：仅有 Device_id=3 的单设备数据，无法进行多卡对比"
- 迭代效率章节含 10 步数据，且 Step 10 被标注为预热步

**关键断言**

**断言 3.1** — 单设备声明  
报告中必须出现："本次采集仅包含 Device_id=3 的数据，无法进行多卡负载均衡分析"。

**断言 3.2** — 预热步标注  
Step 10 的 `CommNO=68.7%` 与后续步骤（6-13%）差距极大，须标注为"预热步，不参与均值统计"。

**断言 3.3** — 正常步瓶颈双诊断  
基于 Step 11-19（排除 Step 10）：
- `avg_free_ratio ≈ 34%` → **P1 Host Dispatch 瓶颈**（严重阈值 10%，34% 超过 3 倍）
- `avg_comm_not_overlap_ratio ≈ 9.7%` → 接近警告线（15%），判定为 **P2 或观察级**（须引用具体均值）

**断言 3.4** — 通信类型识别  
从 `communication.json`（如存在集合通信数据）或算子名推断，报告须识别出 AllReduce / AllGather / ReduceScatter 三种通信操作类型（ds3.2 是 ZeRO-3 训练框架）。

---

## 用例 4：通信严重瓶颈 + 嵌套目录处理

**场景描述**  
分析 Longcat 长文本 MoE 推理模型，数据目录为嵌套结构（ASCEND_PROFILER_OUTPUT 在子目录内），且通信占总时间 74%，属于严重通信瓶颈。

**输入**
```
数据路径：prof-data/longcat/
用户问题：这个模型的性能瓶颈在哪里？
```

**预期输出结构**
- 分析上下文：注明实际找到的 ASCEND_PROFILER_OUTPUT 子路径
- 维度 1（迭代效率）：含 Step 5 的数据
- 维度 4（通信效率）：含通信时间分布，并注明带宽数据不可用
- 维度 8（多卡均衡）：标注"单步单设备，跳过"

**关键断言**

**断言 4.1** — 嵌套目录自动发现  
Phase 0 须自动扫描子目录并找到：
`liteserver-b9ea-smoke-0_2930608_20260421212924990_ascend_pt/ASCEND_PROFILER_OUTPUT/`  
报告中须注明完整的实际路径。

**断言 4.2** — P0 通信瓶颈  
Step 5 的 `comm_not_overlap_ratio = 74.1%`（严重阈值 30% 的 2.5 倍），报告须输出：
- 优先级：**P0**
- 标签：`COMMUNICATION_BOTTLENECK`
- 证据：CommNO=75467μs，Stage=101889μs，比例=74.1%

**断言 4.3** — 单步声明  
报告须包含："仅采集到 1 个 Step（Step 5），无法进行预热步判断和步间周期性分析"。

**断言 4.4** — 单 Rank 带宽声明  
通信效率章节须包含："`communication.json` 中所有传输介质带宽数据为 0，判断为单 Rank 采集，无法获取跨 Rank 通信带宽。仅报告通信时长信息。"

**断言 4.5** — MoE 特征识别  
层级结构章节须识别出 MoE 算子特征（`FusedInferAttentionScore`、`GroupedMatmul`、`MoeInitRoutingV3`），并注明这是一个 MoE 推理模型。

---

## 用例 5：等待锚点假热点专项分析

**场景描述**  
使用 Gemma 数据集，专项测试等待锚点检测能力：识别出那些按 `total_cost` 排名靠前但实际上是假热点的 kernel，并正确区分真实热点。

**输入**
```
数据路径：prof-data/gemma/ASCEND_PROFILER_OUTPUT/
用户问题：帮我找出 NPU 上最耗时的算子，并判断是否存在假热点。
```

**预期输出结构**
- 维度 2（算子热点）：基于 `op_statistic.csv` 的 Top-10 表格
- 维度 6（等待锚点）：专门的等待锚点列表，包含 wait_ratio 和上下文
- 瓶颈诊断：对热点算子的定性说明，区分假热点和真实热点

**关键断言**

**断言 5.1** — 等待锚点被检测到  
等待锚点章节须列出至少 1 条满足条件的 kernel：
- **AivKernel**：`wait_ratio ≈ 99.96%`，`Duration ≈ 6μs`，`Wait ≈ 16293μs`
- 或 **UpdateModelParam_static_bin**：`wait_ratio ≈ 99.7%`，`Duration ≈ 7.8μs`，`Wait ≈ 2748μs`

**断言 5.2** — 假热点降级  
等待锚点 kernel 在按 `total_cost`（Duration+Wait）排名时可能排名靠前，但报告须明确说明：
"上述 kernel 按 total_cost 排名靠前，但 wait_ratio > 95% 且 Duration < 10μs，判定为等待锚点假热点。其真实计算耗时极短，不是瓶颈所在；实际问题是上游操作导致设备空转。"

**断言 5.3** — 真实热点正确识别  
在算子热点章节，`MatMul`（`Ratio=48.5%`，`Avg=24.4μs`）被标注为**真实热点**（高 Duration、高总时间、无异常 wait_ratio），与等待锚点有明确区分。

**断言 5.4** — 上下文信息提供  
等待锚点的报告须包含该 kernel 前后紧邻的 kernel 名称（用于人工排查上游问题），不能只输出 kernel 名称而无上下文。

---

## 评测评分标准

| 断言类型 | 权重 | 说明 |
|---|---|---|
| 数值精度（±5%以内） | 高 | 计算出的比例/指标与实际数据吻合 |
| 严重度分级正确性 | 高 | P0/P1/P2/P3 的判定符合阈值规则 |
| 不错误推荐 | 高 | 无不对症的优化建议（如对零通信数据推荐通信优化） |
| 缺失数据处理 | 中 | 正确声明跳过的维度及原因 |
| 术语使用准确性 | 中 | 等待锚点/假热点/预热步等术语使用正确 |
| 报告完整性 | 低 | 12 个章节均存在（或有合理跳过说明） |
