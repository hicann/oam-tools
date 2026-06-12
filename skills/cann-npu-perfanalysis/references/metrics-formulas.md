# 性能指标计算公式

> **使用时机**：执行 Phase 1–3 中任何指标计算之前读取本文件。所有公式均基于 `data-schema.md` 中定义的字段。

---

## 一、迭代效率（Dimension 1）

数据来源：`step_trace_time.csv`

### 1.1 基础比例指标

```
computing_ratio          = Computing / Stage
comm_not_overlap_ratio   = Communication(Not Overlapped) / Stage
free_ratio               = Free / Stage
bubble_ratio             = Bubble / Stage
preparing_ratio          = Preparing / Stage

# 通信遮蔽率：越高说明通信被计算遮蔽的比例越大（越好）
overlap_ratio = Overlapped / Communication    # 若 Communication == 0，则 overlap_ratio = 0
```

**预热步检测**（同一 device 相邻步之间对比）：
```
若 |step_N.free_ratio - avg(step_N+1..end.free_ratio)| > 0.20，则 step_N 为疑似预热步
```

### 1.2 多卡负载均衡（Dimension 8）

同一 Step，跨多个 Device_id 对比 `Stage`：
```
max_stage      = max(Stage for all Device_id)
min_stage      = min(Stage for all Device_id)
avg_stage      = mean(Stage for all Device_id)
variance_ratio = (max_stage - min_stage) / avg_stage
```

若某 Device 的 `Free` 显著高于平均值（> avg_free × 2），则判定为**Host Dispatch 慢卡**（表面上是快卡，实为 Host 侧拖慢）。

---

## 二、设备空泡（Dimension 5）

数据来源：`kernel_details.csv`

### 2.1 时间轴构建

```
# 对每个 Step，收集该 Step 内所有 kernel 的时间区间
device_intervals = []
for each kernel row with Step_Id == target_step:
    s = Start_Time_us
    e = Start_Time_us + Duration_us
    if Duration_us > 0:
        device_intervals.append((s, e))
```

### 2.2 区间合并（去重多 Stream 重叠）

```python
def merge_intervals(intervals):
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_ivs[0]]
    for s, e in sorted_ivs[1:]:
        if s <= merged[-1][1] + 1:   # 1μs 容差，合并相邻区间
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged
```

### 2.3 空泡指标计算

```
merged_segments = merge_intervals(device_intervals)
busy_union      = sum(seg[1] - seg[0] for seg in merged_segments)

# Step 窗口：以该 Step 第一个 kernel 的 Start Time 为起点，Stage(μs) 为窗口长度
step_start = min(Start_Time_us for kernels in this step)
step_end   = step_start + Stage_us    # Stage 取自 step_trace_time.csv

prelaunch_gap          = merged_segments[0][0] - step_start           # 首个 kernel 开始前的空闲
tail_gap               = step_end - merged_segments[-1][1]            # 最后一个 kernel 结束后的空闲
internal_bubble_total  = sum(merged_segments[i+1][0] - merged_segments[i][1]
                             for i in range(len(merged_segments) - 1))  # kernel 之间的间隙之和
largest_internal_bubble = max gap between consecutive merged segments (若有)

underfeed_ratio = (prelaunch_gap + tail_gap + internal_bubble_total) / Stage_us
```

**Step 窗口替代方案**（当 `Step Id` 列缺失时）：用 `step_trace_time.csv` 中相邻 Step 的时间戳差估算窗口，或以全局采集区间为单一伪步。

---

## 三、等待锚点检测（Dimension 6）

数据来源：`kernel_details.csv`

```
wait_ratio  = Wait_Time_us / (Duration_us + Wait_Time_us)

is_wait_anchor = (wait_ratio > 0.95) AND (Duration_us < 10.0)
```

**解释**：等待锚点是指 `wait_ratio` 接近 1 但 `Duration` 极短的 kernel。它在按 `total_cost = Duration + Wait` 排名时看起来很"贵"，但实际上自身几乎不执行计算——真正的问题是它前面的操作让设备长时间空转。

**误判防范**：若该 kernel 的 `is_wait_anchor == True`，在热点排名中明确降级并标注"假热点，非真实计算瓶颈"，同时列出其前后紧邻的 kernel 作为上下文。

---

## 四、硬件利用率 / MFU（Dimension 3）

数据来源：`kernel_details.csv`

### 4.1 MFU 计算（V2 Schema，MatMul 类 kernel）

```
# Input Shapes 解析：格式为 "M,K;K,N" 或 "M,K;N,K"（转置无关，FLOPs 相同）
parse_matmul_shapes(input_shapes):
    tensors = input_shapes.split(";")
    A_shape = [int(x) for x in tensors[0].split(",")]
    B_shape = [int(x) for x in tensors[1].split(",")]
    M, K = A_shape[0], A_shape[1]
    N    = B_shape[1] if B_shape[0] == K else B_shape[0]   # 兼容转置
    return M, K, N

FLOPs            = 2 × M × K × N
Duration_s       = Duration_us × 1e-6
Achieved_TFLOPs  = FLOPs / Duration_s / 1e12
MFU              = Achieved_TFLOPs / Peak_TFLOPs   # Peak 取自 hardware-specs.md
```

**批量 MatMul**（Input Shapes = "B,M,K;B,K,N"）：
```
FLOPs = 2 × B × M × K × N
```

### 4.2 MFU 计算（V2 Schema，FusedInferAttentionScore / FlashAttention）

```
# BNSD layout: batch × heads × seq × head_dim
# BSH layout:  batch × seq × (heads × head_dim)
# 均支持，从 Input Shapes 推断

FLOPs = 2 × q_batch × q_heads × q_seq × kv_seq × (q_head_dim + kv_head_dim)

# 若为因果掩码（causal mask）：
FLOPs = FLOPs × 0.5

MFU = (FLOPs / Duration_s / 1e12) / Peak_TFLOPs
```

**注意**：batch=1、单 token 推理（decode）场景下，因 q_seq=1，MatMul MFU 天然极低（< 5%），**不应将此视为硬件故障**，须在报告中注明"推理 decode 单 token，绝对 MFU 低属正常"。

### 4.3 MFU 估算（V1 Schema，低置信度）

```
Achieved_TFLOPs = aic_cube_fops / Duration_us / 1e6   # aic_cube_fops 单位为 FLOPs
MFU             = Achieved_TFLOPs / Peak_TFLOPs
```
V1 估算在报告中须标注"【V1 估算，置信度较低】"。

### 4.4 cube_utilization(%) 的语义

`cube_utilization(%)` = Cube 单元有效执行时间 / kernel 总时间，衡量**流水线效率**（kernel 内部 Cube 有多忙），**不等于 MFU**（MFU 衡量相对硬件峰值的算力利用率）。两者都应报告，含义不同：
- `cube_utilization` 低 → kernel 内部流水线有气泡（可能 MTE 成为瓶颈）
- `MFU` 低 → 算力远低于硬件峰值（可能 shape 太小、batch 不足）

### 4.5 瓶颈类型判定（AI Core kernel）

```
if aic_mte2_ratio > 0.8:      → Memory Bound（HBM/L2 读取是主要瓶颈）
elif aic_mac_ratio > 0.8:     → Compute Bound（Cube 单元是瓶颈）
elif aic_fixpipe_ratio > 0.3: → FixPipe Bound（后处理或激活函数是瓶颈）
else:                         → Latency Bound / Mixed（带宽和算力利用率均低）
```

---

## 五、通信效率（Dimension 4）

数据来源：`communication.json` + `step_trace_time.csv`

### 5.1 遮蔽率（step 级）

```
overlap_ratio          = Overlapped / Communication        # 来自 step_trace_time.csv
comm_efficiency_index  = 1 - comm_not_overlap_ratio        # 越高越好
```

### 5.2 各集合通信操作汇总

从 `communication.json` 按操作类型（AllReduce / AllGather / ReduceScatter）汇总：
```
对每个 step 中的每个 collective op:
    type = extract_type(op_name)    # 从前缀解析
    total_elapse[type] += Elapse Time(ms)
    total_wait[type]   += Wait Time(ms)
    total_size[type]   += sum(Transit Size(MB) across all transports)
```

### 5.3 带宽计算

```
for each transport in [RDMA, HCCS, PCIE, SDMA, SIO]:
    if Transit_Size_MB > 0 and Transit_Time_ms > 0:
        bandwidth_GBps = Transit_Size_MB / 1024 / (Transit_Time_ms / 1000)
    else:
        bandwidth_GBps = "N/A（单 Rank 采集或无数据）"
```

---

## 六、算子层级结构（Dimension 7）

数据来源：`kernel_details.csv`

### 6.1 结构边界检测

以 `FusedInferAttentionScore`（FIA）kernel 作为层边界标记（对 Transformer 类模型）：
```
FIA_kernels = [row for row if "FusedInferAttentionScore" in row.Name]
sorted by Start_Time_us

layer_count = len(FIA_kernels) / FIA_per_layer   # 通常 FIA_per_layer = 1（单卡）
```

若无 FIA，退回使用重复 kernel 名称模式检测：连续出现相同 kernel 名序列作为层重复单元。

### 6.2 模型类型判定

```
if any("MoeGatingTopK" in name or "DispatchFFNCombine" in name
       or "MoeComputeExpertTokens" in name) for name in all_kernel_names:
    model_type = "MoE（混合专家模型）"
elif any("GroupedMatmul" in name):
    model_type = "MoE（GroupedMatmul 路由）或稀疏模型"
else:
    model_type = "Dense（稠密模型）"
```

### 6.3 单层耗时估算

```
for each FIA-delimited layer interval [FIA_i.start, FIA_{i+1}.start):
    layer_kernels = kernels with Start_Time in this interval
    layer_wall_ms = (FIA_{i+1}.start - FIA_i.start) / 1000
    layer_kernel_sum_ms = sum(Duration_us for kernel in layer_kernels) / 1000
    layer_busy_union_ms = compute busy union for layer_kernels
```

---

## 七、AICPU 曝露率（辅助指标）

数据来源：`kernel_details.csv`

```
AI_CPU_kernels = [row for row if row.Accelerator_Core == "AI_CPU" 
                  or row.Type == "AI_CPU"]

for each AI_CPU_kernel:
    # 检查是否与同时段的 AI_CORE kernel 并发（同 step，时间重叠）
    concurrent_core_kernels = [k for k in same_step_kernels
                                if k.Accelerator_Core in ["AI_CORE", "MIX_AIC"]
                                and intervals_overlap(k, ai_cpu_kernel)]
    if concurrent_core_kernels:
        status = "MASKED（被 AI Core 遮蔽，不影响性能）"
    else:
        status = "EXPOSED（暴露在关键路径，直接增加时延）"
```

### 7.1 masked_ratio 精确计算

```
ai_cpu_interval = [start, start + duration]
overlap_with_ai_core = sum(overlap(ai_cpu_interval, core_interval)
                           for core_interval in merged_ai_core_intervals_same_step)
masked_ratio = overlap_with_ai_core / duration

if masked_ratio >= 0.9:
    aicpu_status = "AICPU_MASKED_BUT_UNDESIRABLE"
elif masked_ratio >= 0.2:
    aicpu_status = "AICPU_PARTIALLY_EXPOSED"
else:
    aicpu_status = "AICPU_EXPOSED_NOT_ALLOWED"
```

---

## 八、Host / Device Bound 分类

数据来源：`step_trace_time.csv` + `kernel_details.csv` + 可选 `trace_view.json`

### 8.1 Host-originated risk

```
host_risk_score = 0
if avg_free_ratio > 0.10:
    host_risk_score += 2
if underfeed_ratio > 0.20:
    host_risk_score += 2
if recurring_bubble_pattern:
    host_risk_score += 1
if host_event_overlap_available and max(sync_overlap, comm_overlap, host_visible_coverage) >= 0.20:
    host_risk_score += 1
```

判定：

```
if host_risk_score >= 4:
    overall_bound = "HOST_BOUND"
elif host_risk_score >= 2:
    overall_bound = "HOST_ORIGINATED_RISK"
```

### 8.2 trace_view Host event overlap

对每个 bubble window `[gap_start, gap_end]`：

```
gap_duration = gap_end - gap_start
host_visible_coverage_ratio = union_overlap(host_events, gap_window) / gap_duration
sync_or_h2d_overlap_ratio    = union_overlap(sync_or_h2d_events, gap_window) / gap_duration
comm_marker_overlap_ratio    = union_overlap(comm_marker_events, gap_window) / gap_duration

if sync_or_h2d_overlap_ratio >= 0.20:
    soft_label = "possible_sync_or_h2d"
elif comm_marker_overlap_ratio >= 0.20:
    soft_label = "possible_comm_wait"
elif host_visible_coverage_ratio >= 0.10:
    soft_label = "possible_host_launch_lag"
elif host_visible_coverage_ratio < 0.05:
    soft_label = "possible_untraced_host_blocking"
else:
    soft_label = "insufficient_evidence"
```

### 8.3 Device 子类判定

```
if comm_not_overlap_ratio > 0.30:
    device_bound_type = "DEVICE_COMMUNICATION_BOUND"
elif any(kernel.aic_mte2_ratio > 0.8 or kernel.aiv_mte2_ratio > 0.5 or kernel.aiv_mte3_ratio > 0.5):
    device_bound_type = "DEVICE_MEMORY_BOUND"
elif any(kernel.aic_mac_ratio > 0.8 or kernel.aiv_vec_ratio > 0.5):
    device_bound_type = "DEVICE_COMPUTE_BOUND"
elif many_small_kernels or any(kernel.aiv_scalar_ratio > 0.8):
    device_bound_type = "DEVICE_LATENCY_BOUND"
else:
    device_bound_type = "DEVICE_BOUND_UNCLASSIFIED"
```

### 8.4 Mixed Bound

```
if host_risk_score >= 2 and device_bound_type in [
    "DEVICE_COMPUTE_BOUND", "DEVICE_MEMORY_BOUND", "DEVICE_COMMUNICATION_BOUND", "DEVICE_LATENCY_BOUND"
]:
    overall_bound = "MIXED_BOUND"
    primary = contributor with largest Stage share / severity multiple
    secondary = remaining contributors
```

---

## 九、算子级 Compute / Memory Bound

### 9.1 msprof op PMU 算术强度

数据来源：`OPPROF_*/ArithmeticUtilization.csv` + `Memory.csv`

```
total_flops = sum(aic_cube_fops) + sum(aiv_vector_fops)
total_bytes = (sum(GM_to_UB_datas(KB)) + sum(UB_to_GM_datas(KB))) * 1024
arithmetic_intensity = total_flops / total_bytes

# 若没有芯片理论内存带宽，使用经验阈值 50 FLOPs/Byte
balance_point = peak_tflops * 1e12 / peak_memory_bandwidth_Bps
threshold = balance_point if peak_memory_bandwidth_Bps is known else 50

if arithmetic_intensity < threshold:
    op_bound = "OP_MEMORY_BOUND"
else:
    op_bound = "OP_COMPUTE_BOUND"
```

### 9.2 带宽与冲突辅助判断

```
gm_to_ub_util = mean(GM_to_UB_bw_usage_rate(%))
ub_to_gm_util = mean(UB_to_GM_bw_usage_rate(%))

if gm_to_ub_util < 30 or ub_to_gm_util < 30:
    add_flag("LOW_BANDWIDTH_UTILIZATION")

if aiv_vec_bankgroup_cflt_ratio > 0.10 or aiv_vec_bank_cflt_ratio > 0.10:
    add_flag("BANK_CONFLICT_RISK")
```

### 9.3 kernel_details V2 退化规则

```
if aic_mte2_ratio > 0.8:
    op_bound = "OP_MEMORY_BOUND"
elif aic_mac_ratio > 0.8:
    op_bound = "OP_COMPUTE_BOUND"
elif aiv_scalar_ratio > 0.8:
    op_bound = "OP_SCALAR_BOUND"
elif aic_fixpipe_ratio > 0.3:
    op_bound = "OP_FIXPIPE_BOUND"
else:
    op_bound = "OP_MIXED_OR_UNKNOWN"
```

---

## 十、Wait Pollution / 双热点排名

数据来源：`kernel_details.csv` + 可选 `communication.json` / `trace_view.json`

```
duration_hotspot_score = sum(Duration_us by op/kernel name)
total_cost_score       = sum(Duration_us + Wait_Time_us by op/kernel name)
wait_ratio             = Wait_Time_us / (Duration_us + Wait_Time_us)
```

若 `total_cost_score` 高但 `duration_hotspot_score` 低：

```
if wait_ratio > 0.95 and Duration_us < 10:
    flag = "WAIT_ANCHOR_FALSE_HOTSPOT"
elif wait_interval overlaps communication_window:
    flag = "WAIT_POLLUTION_RISK"
else:
    flag = "WAIT_DOMINATED_HOTSPOT"
```

报告中必须同时输出 `duration_hotspots` 与 `total_cost_hotspots`，并解释二者差异。

---

## 注意事项

1. **多 Stream 并发**：`kernel_sum_ms`（Duration 之和）可能远大于 `wall_ms`（wall time），差值体现多 Stream 的并发收益。不要直接用 `kernel_sum_ms` 推断单 stream 耗时。

2. **Step Id 缺失时**：按时间戳将 kernel 分配到对应 step 窗口（以 step_trace_time.csv 的 Stage 推算窗口边界）。

3. **单步采集**：当 step_trace_time.csv 只有一行时，无法计算步间方差或识别预热步，须在报告中注明"仅单步采集，预热步识别不可用，周期性分析不可用"。
