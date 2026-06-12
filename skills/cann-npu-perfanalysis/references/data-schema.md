# Profiling 数据文件字段说明

> **使用时机**：执行任何 CSV / JSON 读取之前必须先读本文件，了解各列的语义和计量单位，避免误用字段。

---

## 一、step_trace_time.csv（11 列）

记录每个训练/推理迭代的时间拆分，是迭代效率分析的主要来源。

| 列名 | 单位 | 含义 |
|---|---|---|
| `Device_id` | — | NPU 设备编号（多卡时有多行） |
| `Step` | — | 迭代编号（从 3 起通常含预热步） |
| `Computing` | μs | 设备真实执行计算 kernel 的时间（AI Core / AI CPU / AICPU 均含，不含通信重叠部分） |
| `Communication(Not Overlapped)` | μs | **未被计算遮蔽**的通信时间（真实通信代价，直接计入迭代耗时） |
| `Overlapped` | μs | 与计算**并发执行**的通信时间（已被遮蔽，不额外占用迭代时间） |
| `Communication` | μs | 总通信时间 = `Communication(Not Overlapped)` + `Overlapped` |
| `Free` | μs | NPU 处于空闲的时间，原因是 Host 侧未及时下发 kernel（Host Dispatch 瓶颈指标） |
| `Stage` | μs | 迭代总耗时（wall time），约等于 `Computing + Communication(Not Overlapped) + Free + Bubble + Preparing` |
| `Bubble` | μs | 流水线气泡（Pipeline Parallelism 场景下），非 PP 场景为 0 |
| `Communication(Not Overlapped and Exclude Receive)` | μs | 排除点对点 Receive 后的未重叠通信时间（用于更精确的集合通信分析） |
| `Preparing` | μs | 迭代开始前的准备/同步时间 |

**关键语义区分：**
- `Free Time` ≠ `device bubble`：前者是 step 级聚合（Host 未及时下发），后者是 kernel 级间隙（两个 kernel 之间的设备空闲）；成因不同，优化路径不同
- `Communication(Not Overlapped)` 是真正的通信瓶颈指标，`Communication`（总通信）包含了已被遮蔽的部分，不能直接用来判断通信代价
- `Stage` 是实际耗时，可用于多卡负载均衡对比

---

## 二、op_statistic.csv（9 列）

记录整个采集窗口内各算子类型的聚合统计，**不是 per-step**。

| 列名 | 单位 | 含义 |
|---|---|---|
| `Device_id` | — | NPU 设备编号 |
| `OP Type` | — | 算子类型名称（如 MatMul、RmsNorm、GroupedMatmul） |
| `Core Type` | — | 执行核心类型：`AI_CORE`（Cube 核）/ `AI_VECTOR_CORE`（Vector 核）/ `MIX_AIC`（混合 AI Core）/ `MIX_AIV`（混合 AI Vector）/ `AI_CPU`（CPU 侧回退）/ `COMMUNICATION`（HCCL 通信） |
| `Count` | 次 | 整个采集窗口内该算子类型的执行次数 |
| `Total Time(us)` | μs | 所有执行的 Duration 之和（不含 Wait Time） |
| `Min Time(us)` | μs | 单次最短 Duration |
| `Avg Time(us)` | μs | 平均 Duration |
| `Max Time(us)` | μs | 单次最长 Duration（Max/Avg >> 1 说明存在异常慢执行） |
| `Ratio(%)` | % | 该算子类型占**所有算子 Total Time 之和**的比例（注意：不是占 Stage 的比例） |

**注意：** `Ratio(%)` 是 kernel 维度的时间占比，由于多 stream 并发，`sum(Total Time)` 可能远大于实际 Stage 耗时。不要直接用 `Ratio(%)` 推断对 wall time 的贡献，需结合 `step_trace_time.csv` 交叉验证。

**AI_CPU 出现即为告警**：正常情况下算子应运行在 AI_CORE 或 AI_VECTOR_CORE，若 `Core Type = AI_CPU` 说明存在 AICPU 回退，会暴露在设备执行时间线上。

---

## 三、kernel_details.csv（两套 Schema 版本）

最细粒度的 kernel 级别 profiling 数据，每行对应一次 kernel 调用。

### 版本检测规则
读取 CSV 头部：
- **存在 `cube_utilization(%)` 列** → **V2 Schema**（支持详细流水线利用率分析）
- **不存在该列** → **V1 Schema**（仅支持基础 MFU 估算）

### 公共列（V1 和 V2 均有）

| 列名 | 单位 | 含义 |
|---|---|---|
| `Step Id` | — | 所属迭代编号（对应 step_trace_time 的 Step 列） |
| `Device_id` | — | NPU 设备编号 |
| `Model ID` | — | 图编号 |
| `Task ID` | — | 任务 ID |
| `Stream ID` | — | 所属 stream（多 stream 并发时用于分组） |
| `Name` | — | kernel 名称（包含算子类型信息，如 `MatMul`、`HcomAllReduce`） |
| `Type` | — | kernel 类别（如 `AI_CORE`、`AI_CPU`、`HCCL`） |
| `OP State` | — | 算子状态：`dynamic`（动态 shape）/ `static`（静态 shape） |
| `Accelerator Core` | — | 执行核心类型（`AI_CORE` / `AI_VECTOR_CORE` / `MIX_AIC` / `MIX_AIV`） |
| `Start Time(us)` | μs | kernel 在设备上的绝对开始时间戳（用于构造时间轴、计算空泡） |
| `Duration(us)` | μs | kernel 在设备上的实际执行时长（不含等待） |
| `Wait Time(us)` | μs | kernel 在队列中等待（未执行）的时间；若 wait 远大于 duration，可能是等待锚点 |
| `Input Shapes` | — | 输入张量 shape，格式如 `"M,K;K,N"` 或为空（shape 未记录） |
| `Output Shapes` | — | 输出张量 shape |
| `Input Data Types` | — | 输入数据类型（如 `float16;float16`） |
| `Input Formats` | — | 输入内存格式（如 `ND;ND`） |
| `Block Dim` | — | AI Core 块数（并行度） |
| `HF32 Eligible` | — | 是否可使用 HF32 |

### V2 专有列（AI_CORE 类 kernel）

| 列名 | 单位 | 含义 |
|---|---|---|
| `aicore_time(us)` | μs | AI Core 有效执行时间 |
| `aic_total_cycles` | 周期 | AI Core 总周期数 |
| `aic_mac_time(us)` | μs | Cube（矩阵乘）单元执行时间 |
| `aic_mac_ratio` | 0–1 | MAC 时间占 aicore_time 的比例；高 → Compute Bound |
| `aic_scalar_time(us)` | μs | 标量单元执行时间 |
| `aic_scalar_ratio` | 0–1 | 标量时间占比 |
| `aic_mte1_time(us)` | μs | MTE1（L1→L0 数据搬移）时间 |
| `aic_mte1_ratio` | 0–1 | MTE1 时间占比 |
| `aic_mte2_time(us)` | μs | MTE2（L2/HBM→L1 读取）时间 |
| `aic_mte2_ratio` | 0–1 | MTE2 时间占比；高 → Memory Bound（权重读取瓶颈） |
| `aic_fixpipe_time(us)` | μs | FixPipe（后处理：格式转换、激活）时间 |
| `aic_fixpipe_ratio` | 0–1 | FixPipe 时间占比 |
| `aic_icache_miss_rate` | % | 指令缓存缺失率 |
| `cube_utilization(%)` | % | Cube 单元有效执行时间占 kernel 总时间的比例（流水线效率，非 MFU） |

### V2 专有列（AI_VECTOR_CORE 类 kernel）

| 列名 | 单位 | 含义 |
|---|---|---|
| `aiv_time(us)` | μs | Vector Core 有效执行时间 |
| `aiv_total_cycles` | 周期 | Vector Core 总周期数 |
| `aiv_vec_time(us)` | μs | 向量计算时间 |
| `aiv_vec_ratio` | 0–1 | 向量计算占比 |
| `aiv_scalar_time(us)` | μs | 标量计算时间 |
| `aiv_scalar_ratio` | 0–1 | 标量计算占比 |
| `aiv_mte2_time(us)` | μs | GM→UB（全局内存到统一缓冲区）读取时间 |
| `aiv_mte2_ratio` | 0–1 | 内存读取占比 |
| `aiv_mte3_time(us)` | μs | UB→GM（统一缓冲区到全局内存）写入时间 |
| `aiv_mte3_ratio` | 0–1 | 内存写入占比 |
| `aiv_icache_miss_rate` | % | Vector Core 指令缓存缺失率 |

### V1 专有列

| 列名 | 含义 |
|---|---|
| `aic_mac_fp16_ratio` | FP16 MAC 占比（V1 的粗粒度版本） |
| `aic_mac_int8_ratio` | INT8 MAC 占比 |
| `aic_cube_fops` | AI Core Cube 单元完成的浮点运算数（用于 V1 MFU 估算） |
| `aiv_vec_fp32_ratio` | Vector Core FP32 计算占比 |
| `aiv_vec_fp16_ratio` | Vector Core FP16 计算占比 |
| `aiv_vector_fops` | Vector Core 完成的浮点运算数 |

**注意**：V1 schema 下 MFU 只能用 `aic_cube_fops / Duration_us` 估算，置信度低于 V2，需在报告中明确标注。

---

## 四、operator_details.csv（9 列）

记录 PyTorch 算子维度的 Host 侧与设备侧时间拆分，用于 Host-Device 时间归因。

| 列名 | 单位 | 含义 |
|---|---|---|
| `Name` | — | PyTorch 算子名称（如 `aten::matmul`、`aten::_to_copy`） |
| `Input Shapes` | — | 输入张量 shape（可为空） |
| `Call Stack` | — | Python 调用栈（用于定位代码行） |
| `Host Self Duration(us)` | μs | 在 Host CPU 上自身执行时间（不含子调用） |
| `Host Total Duration(us)` | μs | 在 Host CPU 上含子调用的总执行时间 |
| `Device Self Duration(us)` | μs | 在 NPU 设备上自身执行时间 |
| `Device Total Duration(us)` | μs | 在 NPU 设备上含子调用的总执行时间 |
| `Device Self Duration With AICore(us)` | μs | 仅 AI Core 部分的设备自身时间 |
| `Device Total Duration With AICore(us)` | μs | 仅 AI Core 部分的设备总时间 |

**使用场景**：当 `Host Self Duration` 显著高于 `Device Self Duration` 时，说明该算子存在 Host Bound 风险（Host 计算未被设备执行隐藏）。`Device Duration = 0` 的行通常为纯 Host 侧操作（内存分配、复制等）。

---

## 五、communication.json（嵌套 JSON）

记录每个 step 内所有集合通信操作的详细时序和带宽信息。

### 顶层结构
```json
{
  "step3": {
    "p2p": {},
    "collective": {
      "<op_name>": { ... }
    }
  },
  "step4": { ... }
}
```

### 操作名格式
```
HcomAllReduce_<hash>_<sequence>@<group_id>
HcomAllGather_<hash>_<sequence>@<group_id>
HcomReduceScatter_<hash>_<sequence>@<group_id>
hcom_allReduce_<hash>_<sequence>@<group_id>
```
从前缀提取操作类型：`HcomAllReduce` → AllReduce，`HcomAllGather` → AllGather，`HcomReduceScatter` → ReduceScatter。

### 每个操作的内部结构

**`Communication Time Info`**（时间信息）：

| 字段 | 单位 | 含义 |
|---|---|---|
| `Start Timestamp(us)` | μs | 通信操作开始时间戳 |
| `Elapse Time(ms)` | ms | 通信操作总耗时（wall time） |
| `Transit Time(ms)` | ms | 数据在网络中实际传输的时间 |
| `Wait Time(ms)` | ms | 等待其他 Rank 就绪的时间 |
| `Synchronization Time(ms)` | ms | 同步栅栏时间 |
| `Idle Time(ms)` | ms | 通信期间的空闲时间 |
| `Wait Time Ratio` | 0–1 | Wait Time / Elapse Time |
| `Synchronization Time Ratio` | 0–1 | Sync Time / Elapse Time |

**`Communication Bandwidth Info`**（带宽信息，按传输介质分组）：

各介质（RDMA / HCCS / PCIE / SDMA / SIO）均包含：

| 字段 | 单位 | 含义 |
|---|---|---|
| `Transit Size(MB)` | MB | 通过该介质传输的数据量 |
| `Transit Time(ms)` | ms | 该介质的传输时间 |
| `Bandwidth(GB/s)` | GB/s | 实测带宽（= Transit Size / Transit Time） |
| `Large Packet Ratio` | 0–1 | 大包占比（小包多则带宽效率低） |

**重要提示**：若所有介质的 `Transit Size(MB)` 均为 0 或 `Bandwidth(GB/s)` 均为 0，说明这是**单 Rank 采集**，无跨 Rank 通信数据，此时只能报告 `Elapse Time`，不应报告带宽数字。

---

## 六、communication_matrix.json

结构与 `communication.json` 相同（按 step 嵌套），记录 Rank 对之间的流量矩阵。

- **单 Rank 采集时**：`collective` 和 `p2p` 均为空对象 `{}`
- **多 Rank 采集时**：包含各 Rank 对的通信数据（可用于识别热点链路和负载不均）

---

## 七、trace_view.json（可选）

Chrome Trace Format，记录 Host 与 Device 的时间线事件。用于 Host/Device Bound 软归因和 wait pollution 交叉验证。

| 字段 | 单位 | 含义 |
|---|---|---|
| `ph` | — | 事件类型，常见 `X` 为完整事件 |
| `ts` | μs | 事件开始时间戳 |
| `dur` | μs | 事件持续时间 |
| `name` | — | 事件名称，如 `ProfilerStep#N`、`aten::to`、`aclrtMemcpy`、`HcomAllReduce` |
| `cat` | — | 事件类别，如 `cpu_op`、`python_function`、`user_annotation`、`kernel`、`communication`、`AscendCL` |
| `pid` / `tid` | — | 进程 / 线程 / stream 标识 |
| `args` | — | 附加信息，可能包含 Call Stack、Input Shapes 等 |

**Host evidence 分类：**

| 事件族 | 匹配示例 | 诊断含义 |
|---|---|---|
| sync/H2D | `aten::to`、`aten::_to_copy`、`aclrtMemcpy*`、`aclrtSynchronize*`、`HostToDevice` | 可能是同步或 Host↔Device 拷贝导致设备空闲 |
| communication marker | `c10d`、`Hccl`、`hcom`、`StreamWaitEvent`、`Notify_Wait` | 可能是通信等待或同步 |
| host launch | `cpu_op`、`python_function`、`AscendCL@*` | 可能是 Host 下发延迟、Python 调度或 runtime API 开销 |

若 `trace_view.json` 缺失，不得给出确定 Host 根因，只能基于 `free_ratio` / `underfeed_ratio` 给出 Host-originated risk 或 soft label。

---

## 八、msprof op 输出（OPPROF_*，可选）

`msprof op --kernel-name=<kernel>` 会生成 `OPPROF_<timestamp>/`，用于单 kernel PMU 级分析。

| 文件 | 用途 |
|---|---|
| `OpBasicInfo.csv` | 算子名称、类型、`Task Duration(us)`、`Block Dim` |
| `ArithmeticUtilization.csv` | Cube/Vector FLOPs、Cube/Vector 占比 |
| `Memory.csv` | GM→UB、UB→GM 数据量、带宽、带宽利用率 |
| `MemoryL0.csv` / `MemoryUB.csv` | L0/UB 读写带宽细节 |
| `PipeUtilization.csv` | 计算/搬运流水线占比 |
| `ResourceConflictRatio.csv` | UB Bank Group / Bank conflict / 资源冲突率 |
| `L2Cache.csv` | L2 Cache 命中率 |

关键字段：

| 文件 | 字段 | 含义 |
|---|---|---|
| `ArithmeticUtilization.csv` | `aic_cube_fops`、`aiv_vector_fops` | FLOPs，用于算术强度 |
| `ArithmeticUtilization.csv` | `aic_cube_ratio`、`aiv_vec_ratio` | Cube / Vector 计算占比 |
| `Memory.csv` | `GM_to_UB_datas(KB)`、`UB_to_GM_datas(KB)` | GM↔UB 数据量 |
| `Memory.csv` | `GM_to_UB_bw_usage_rate(%)`、`UB_to_GM_bw_usage_rate(%)` | 带宽利用率 |
| `ResourceConflictRatio.csv` | `aiv_vec_bankgroup_cflt_ratio`、`aiv_vec_bank_cflt_ratio` | Bank conflict 风险 |

**优先级**：若存在 msprof op 输出，算子级 compute/memory bound 以 PMU 数据为高置信证据；否则退化为 `kernel_details.csv` V2 的 `aic_*` / `aiv_*` ratio。

---

## 九、目录结构说明

### 标准结构（gemma / qwen7b / ds3.2）
```
<model>/ASCEND_PROFILER_OUTPUT/
├── kernel_details.csv
├── op_statistic.csv
├── operator_details.csv
├── step_trace_time.csv
├── communication.json
├── communication_matrix.json
├── trace_view.json        （大文件，本 Skill 仅按需使用）
├── api_statistic.csv
└── *.db                   （SQLite 分析数据库，可选）
```

### 嵌套结构（longcat 风格）
```
<run_id>/
├── ASCEND_PROFILER_OUTPUT/    ← Phase 0 自动扫描子目录找到此处
│   ├── kernel_details.csv
│   └── ...
├── FRAMEWORK/
├── logs/
└── PROF_*/
```
Phase 0 发现嵌套结构时，应扫描 1–2 级子目录寻找 `ASCEND_PROFILER_OUTPUT`，找到后以该目录为分析根目录，并在报告中注明实际路径。
