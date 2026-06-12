# 性能判定阈值表

> **使用时机**：Phase 3 瓶颈诊断时，对照本表将各维度指标转换为严重度等级（正常 / 警告 / 严重）和优先级（P0–P3）。

---

## 一、主判定阈值表

| 维度 | 指标 | 正常（✅） | 警告（⚠️） | 严重（🔴） | 说明 |
|---|---|---|---|---|---|
| **迭代效率** | `free_ratio` | < 5% | 5%–10% | > 10% | Host Dispatch 瓶颈指标 |
| **迭代效率** | `comm_not_overlap_ratio` | < 15% | 15%–30% | > 30% | 真实通信代价指标 |
| **迭代效率** | `overlap_ratio` | > 50% | 20%–50% | < 20% | 通信遮蔽效率，越高越好 |
| **迭代效率** | `bubble_ratio` | < 2% | 2%–5% | > 5% | 流水线气泡（PP 场景） |
| **算子热点** | 单一算子 `Ratio(%)` | < 10% | 10%–20% | > 20% | 热点算子判定 |
| **算子热点** | AI_CPU 核心类型出现 | 无 | 少量 | 大量 | AICPU 回退风险 |
| **硬件利用率** | MatMul MFU | > 40% | 20%–40% | < 20% | 注：推理 decode batch=1 天然低 MFU，不作为严重告警 |
| **硬件利用率** | `cube_utilization(%)` | > 70% | 40%–70% | < 40% | 流水线内部 Cube 利用率 |
| **硬件利用率** | `aic_mte2_ratio` | < 0.5 | 0.5–0.8 | > 0.8 | 权重读取占主导 → Memory Bound |
| **硬件利用率** | `aic_mac_ratio` | > 0.7 | 0.4–0.7 | < 0.4 | Cube 计算占比低 → 非 Compute Bound |
| **通信效率** | RDMA 带宽 | > 1.5 GB/s | 0.5–1.5 GB/s | < 0.5 GB/s | 小包问题 / 网络拥塞 |
| **通信效率** | Wait Time Ratio | < 0.2 | 0.2–0.5 | > 0.5 | 通信中等待其他 Rank 时间占比 |
| **设备空泡** | `underfeed_ratio` | < 5% | 5%–20% | > 20% | 设备整体空闲占比 |
| **设备空泡** | `prelaunch_gap` | < 1ms | 1ms–5ms | > 5ms | 第一个 kernel 下发前的空闲 |
| **设备空泡** | `largest_internal_bubble` | < 1ms 且 < 10%×Stage | 1ms 或 10%–15%×Stage | > 1ms 且 > 15%×Stage | 最大内部间隙 |
| **等待锚点** | `wait_ratio` | < 0.5 | 0.5–0.95 | > 0.95 且 Duration < 10μs | 假热点判定条件 |
| **多卡均衡** | `variance_ratio` | < 10% | 10%–20% | > 20% | 最大-最小 Stage 差 / 平均 Stage |
| **多卡均衡** | 某卡 `Free` 显著偏高 | < avg×1.5 | avg×1.5–2 | > avg×2 | Host Dispatch 慢卡（假快卡） |
| **Bound 总判定** | `host_risk_score` | < 2 | 2–3 | ≥ 4 | Host-originated risk 综合分 |
| **Host evidence** | `sync_or_h2d_overlap_ratio` | < 10% | 10%–20% | ≥ 20% | bubble 与同步/H2D 标记重叠 |
| **Host evidence** | `comm_marker_overlap_ratio` | < 10% | 10%–20% | ≥ 20% | bubble 与通信等待标记重叠 |
| **算子级 Bound** | Arithmetic Intensity | ≥ balance point | 接近 balance point | < balance point | 低于硬件平衡点 → Memory Bound |
| **算子级 Bound** | GM/UB 带宽利用率 | > 50% | 30%–50% | < 30% | 低带宽利用率，检查访存模式 |
| **算子级 Bound** | `aiv_scalar_ratio` | < 0.5 | 0.5–0.8 | > 0.8 | Scalar / Latency Bound 风险 |
| **算子级 Bound** | `aiv_mte2_ratio` / `aiv_mte3_ratio` | < 0.3 | 0.3–0.5 | > 0.5 | Vector kernel 访存占主导 |
| **算子级 Bound** | Bank conflict ratio | < 5% | 5%–10% | > 10% | UB Bank conflict 风险 |

---

## 二、严重度标签（来自 ascend-profiling-anomaly 规则库）

| 标签 | 判定条件 |
|---|---|
| `DEVICE_IDLE_GAP_HEAVY` | `underfeed_ratio ≥ 0.30` 或 `largest_internal_bubble ≥ max(1ms, 10% × Stage)` |
| `PRELAUNCH_GAP_HEAVY` | `prelaunch_gap ≥ max(1ms, 10% × Stage)` |
| `TAIL_GAP_HEAVY` | `tail_gap ≥ max(1ms, 10% × Stage)` |
| `INTERNAL_BUBBLE_HEAVY` | `internal_bubble_total ≥ 20% × Stage` |
| `WAIT_ANCHOR_FALSE_HOTSPOT` | `wait_ratio > 0.95 AND Duration_us < 10.0` |
| `WAIT_POLLUTION_RISK` | 高 wait kernel 的 wait 区间与通信窗口重叠 |
| `AICPU_EXPOSED_RISK` | 存在 AI_CPU kernel 且无并发 AI_CORE 覆盖 |
| `AICPU_MASKED_BUT_UNDESIRABLE` | `masked_ratio >= 0.9` |
| `AICPU_PARTIALLY_EXPOSED` | `0.2 <= masked_ratio < 0.9` |
| `AICPU_EXPOSED_NOT_ALLOWED` | `masked_ratio < 0.2` |
| `COMM_SYNC_RISK` | `Wait Time Ratio > 0.5`（通信中大量时间等待 Rank 同步） |
| `HOST_DISPATCH_BOTTLENECK` | `free_ratio > 0.10` |
| `COMMUNICATION_BOTTLENECK` | `comm_not_overlap_ratio > 0.30` |
| `LOAD_IMBALANCE` | 多卡 `variance_ratio > 0.20` |
| `HOST_BOUND` | `free_ratio > 0.10` 或 `underfeed_ratio > 0.20`，且 Host-originated risk 为主因 |
| `DEVICE_COMPUTE_BOUND` | `aic_mac_ratio > 0.8` 或算术强度高且计算利用率高 |
| `DEVICE_MEMORY_BOUND` | `aic_mte2_ratio > 0.8` 或算术强度低于平衡点 |
| `DEVICE_COMMUNICATION_BOUND` | `comm_not_overlap_ratio > 0.30` 或通信 wait/bandwidth 异常 |
| `DEVICE_LATENCY_BOUND` | 计算/访存利用率均低，小 kernel 多或 `aiv_scalar_ratio > 0.8` |
| `MIXED_BOUND` | Host 与 Device 子类同时超过阈值 |

---

## 三、优先级分类规则（P0–P3）

| 优先级 | 判定条件 | 含义 |
|---|---|---|
| **P0** | 任意单一指标超过严重阈值 **2 倍以上** | 最高优先级，需立即处理；例：free_ratio = 82%（严重阈值 10% 的 8 倍） |
| **P1** | 任意单一指标落入严重范围（未达到 2 倍） | 高优先级；例：comm_not_overlap_ratio = 35% |
| **P2** | 多个指标同时处于警告范围，互相叠加 | 中优先级；例：free_ratio 15% + overlap_ratio 25% 同时出现 |
| **P3** | 单一指标处于警告范围，其他指标正常 | 低优先级，观察跟踪；例：单一算子 Ratio 17% |

**归因语言规范**：
- 测量到的事实 → 陈述句（"free_ratio = 82%，超过严重阈值 10% 的 8 倍"）
- 推断的原因 → 用 `possible_xxx`（"可能由于 Python eager 模式小算子碎片化下发"）
- 证据不足时 → 明确说明"归因证据不足，建议重采集 host stack 数据"
- Bound 诊断必须写清楚 **事实 → 阈值 → 判定理由 → 置信度 → 缺失证据**。
- 没有 `kernel_details.csv` V2 或 msprof op PMU 时，不得输出算子 compute/memory bound，只能输出热点和"证据不足"。

---

## 四、Bound 分类决策表

| 主判定 | 必要证据 | 排除/降级条件 |
|---|---|---|
| `HOST_BOUND` | `free_ratio > 10%` 或 `underfeed_ratio > 20%`，且 Stage 主要被 Free/空泡占用 | 若通信未重叠 >30% 或 PMU 显示设备 kernel 饱和，应降为 `MIXED_BOUND` |
| `DEVICE_COMPUTE_BOUND` | Host 空闲不高；`aic_mac_ratio > 0.8`、MFU/利用率高或 AI 高 | Decode M=1 低 MFU 不作为异常；若 MTE 高则改为 memory |
| `DEVICE_MEMORY_BOUND` | Host 空闲不高；`aic_mte2_ratio > 0.8`、Vector MTE 高、AI 低或带宽利用异常 | 若带宽数据缺失，只能中/低置信 |
| `DEVICE_COMMUNICATION_BOUND` | `comm_not_overlap_ratio > 30%` 或通信 wait ratio >0.5，overlap 低 | `Communication=0` 时禁止输出通信优化建议 |
| `DEVICE_LATENCY_BOUND` | 小 kernel 多、scalar 占比高、计算和带宽利用率均低 | 若 Free 很高，优先判 Host Bound |
| `MIXED_BOUND` | 两类以上证据同时超过阈值 | 必须排序主因/次因 |

---

## 五、预热步识别规则

| 场景 | 判定方式 |
|---|---|
| 第一个 Step 的 `comm_not_overlap_ratio` 比后续步高 **> 20%** | 标记为"疑似预热步（初始 AllReduce 含初始化开销）" |
| 第一个 Step 的 `Computing` 比后续步低 **> 20%** | 标记为"疑似预热步（编译/JIT 预热未完成）" |
| 仅有单步 | 无法判断是否为预热步，注明"单步采集，建议多步验证" |

预热步**不参与**迭代效率均值计算，须单独列出并注明。

---

## 六、特殊场景处理说明

### 推理 Decode 单 Token（batch=1）
- **表现**：MatMul MFU < 5%，这是正常现象，**不判定为 P0/P1**
- **原因**：单 token 时矩阵 M=1，计算量极小，无法充分利用 AI Core
- **处理**：报告中注明"推理 decode 单 token，绝对 MFU 低属正常；建议关注相对效率（cube_utilization）和通信占比"

### 单 Rank 采集（通信带宽全为 0）
- **表现**：`communication.json` 中所有 `Transit Size(MB) = 0`
- **处理**：仅报告 `Elapse Time`，不输出带宽数字，注明"单 Rank 采集，无跨 Rank 通信带宽数据"

### MoE 模型特征识别
- **正常 MoE 特征**：GroupedMatmul、MoeGatingTopKSoftmax、MoeComputeExpertTokens、DispatchFFNCombine、MoeInitRoutingV3 等 MoE 专属算子出现属预期行为
- **不应**将 GroupedMatmul 的高 Ratio(%) 单独标为热点，需结合模型架构说明其为 MoE Expert 计算的正常开销
