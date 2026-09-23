# CANN 故障处理参考

> 本文档基于 CANN 8.5.0（商用版）/ CANN 9.0.0-beta.2（社区版）官方故障处理文档整理，用于日志评估阶段的故障定位与处理。
> 官方参考：[故障处理简介（商用版 8.5.0）](https://www.hiascend.com/document/detail/zh/canncommercial/850/maintenref/troubleshooting/troubleshooting_0001.html) / [AI Core Error 问题现象描述（商用版 8.5.0）](https://www.hiascend.com/document/detail/zh/canncommercial/850/maintenref/troubleshooting/troubleshooting_0002.html)

---

## 故障处理总体流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 收集故障信息                                               │
│    应用类日志（plog）+ Device侧系统日志（msnpureport）+       │
│    环境信息（npu-smi、dmesg、Python堆栈）                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 分析故障原因                                               │
│    自上而下日志分析法：按业务流程逐步缩小到底层故障现象          │
│    从首报错算子开始排查（异步场景下可能出现多算子报错）          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 故障排除 + 记录                                           │
│    排除故障后记录处理要点，给出防范改进措施                    │
└─────────────────────────────────────────────────────────────┘
```

**故障信息类别：**
- **应用类日志**：Host 侧和 Device 侧应用程序产生的用户态日志，常用 `plog-<pid>_*.log`
- **Device 侧系统类日志**：内核态日志和系统进程日志，需用 `msnpureport` 工具导出
- **其他维测信息**：`npu-smi info`、`dmesg`、堆栈信息、coredump 文件

---

## AI Core Error 问题定位专题

### 问题现象

用户应用程序报错退出，屏幕日志错误码为 **EZ9999**，且日志中包含"**there is an aivec error exception**"或"**there is an aicore error exception**"；或者 plog 日志中存在报错日志"**Aicore kernel execute failed**"。

> **说明**：EZ9999 是屏幕层面的通用错误码，真正的诊断信息在嵌套的错误详情中（error code、errorStr、fault kernel_name 等字段）。

**报错示例：**

```
-----------------------------------------
   Ascend Error Message:
-----------------------------------------
EZ9999: Inner Error!
EZ9999: The error from device(chipId:4, dieId:0), serial number is 2,
there is an aivec error exception, core id is 11, error code = 0x10, dump info:
  pc start: 0x1240c46650b8,
  vec error info: 0xd019ddc1a,
  mte error info: 0x2ffeba07af,
  ifu error info: 0x4e5c097530000,
  ccu error info: 0x30c255954a000023,
  cude error info: 0,0,
  aic error mask: 0x65000020bd000288,
  para base: 0x1240c51b1dd0.
[FUNC:ProcessStarsCoreErrorInfo][FILE:device_error_proc.cc][LINE:1100]
  The extend info: errcode:(0x10, 0, 0) errorStr: Illegal instruction,
  which is usually caused by unaligned UUB addresses.
  Aicore kernel execute failed, device_id=4, stream_id=450,
  report_stream_id=2, task_id=442, flip_num=0,
  fault kernel_name=00_131_Grandients/Default/AddN.op56419/program id=2089,
  hash=16296079633597215637.[FUNC:GetError][FILE:stream.cc][LINE:1467]

  rtStreamSynchronize execute failed,
  reason=[The model stream execute failed]
```

### 报错日志字段解读

| 字段 | 说明 | 诊断用途 |
|------|------|---------|
| `chipId` / `dieId` | 报错芯片 ID | 多次报错 chipId 固定 → 硬件故障特征 |
| `serial number` | 报错序号 | 异步场景下取序号最小的为首报错，从首报错开始排查 |
| `core id` | 报错芯片核 ID | core id 固定 → 特定核硬件问题 |
| `error code` | AI Core Error 错误码 | 如 `0x10`=Illegal instruction, `0x800000`=数组越界 |
| `errorStr` | 错误码文字描述 | 直接说明错误类型 |
| `fault kernel_name` | 报错算子 kernel 名称 | **分析的首要入口**，定位到具体算子 |
| `task_id` / `stream_id` | 报错任务和流编号 | 关联 plog 中的算子执行记录 |
| `hash` | 算子 hash | 在编译缓存中定位对应编译产物 |
| `pc start` | 程序计数器起始地址 | 定位算子内部的出错指令位置 |
| `vec error info` | 向量单元错误信息 | AI Vector Core (aivec) 报错时的寄存器 dump |
| `mte error info` | 内存传输单元错误信息 | 数据搬运相关错误 |
| `ifu error info` | 指令取指单元错误信息 | 非零 → 指令缓存校验失败，排查硬件 |
| `ccu error info` | Cube 计算单元错误信息 | AI Cube Core (aicore) 矩阵计算相关错误 |
| `aic error mask` | AI Core 错误掩码 | 标识哪些子单元报错 |
| `para base` | 参数基址 | 地址为 0x0 等异常值 → 内存越界/释放后使用 |
| `aivec error exception` | AI Vector Core 报错 | 向量运算单元异常 |
| `aicore error exception` | AI Cube Core 报错 | 矩阵运算单元异常 |

> **注意**：异步场景下多个算子可能连续报错，须从**首报错算子**（serial number 最小）开始排查。

### 完整定位流程

```
Step 1: 从屏幕日志提取 fault kernel_name
    │   确认报错算子名称，记录 device_id / stream_id / task_id
    ▼
Step 2: 在 plog 中搜索 "Aicore kernel execute failed"
    │   获取完整错误上下文，确认是否多个算子报错
    │   如有多个，按 serial number 排序，从最小的开始
    ▼
Step 3: 收集 Device 侧系统日志
    │   msnpureport -d <device_id> -output ./msnpureport_output/
    ▼
Step 4: 使用 msaicerr 工具分析 AI Core Error
    │   msaicerr -i ./msnpureport_output/ -task_id <task_id> -o ./analysis/
    │   查看 info.txt 中的 Root cause conclusion
    ▼
Step 5: 判断是否固定芯片/核报错
    │   chipId/coreId 固定 → 倾向硬件故障
    │   chipId/coreId 不固定 → 倾向软件/算子问题
    ▼
Step 6: 根据 msaicerr 分析结果判断子类型
    │   按 "常见 AI Core Error 子类型" 表格匹配
    ▼
Step 7: 按子类型进行针对性排查
```

### msaicerr 工具使用详解

msaicerr 专门用于解析 AI Core Error，将二进制错误信息还原为可读的算子错误报告。

```bash
# 基本用法：分析整个 msnpureport 导出目录
msaicerr -i ./msnpureport_output/ -o ./analysis_result/

# 指定 task_id 精确分析（推荐，避免并发任务干扰）
msaicerr -i ./msnpureport_output/ -task_id 442 -o ./analysis_result/

# 查看分析结果
cat ./analysis_result/info.txt
```

**info.txt 输出结构：**

```
********************Root cause conclusion********************
[此处为根因结论，常见结论如下]

# 结论1：精度溢出
"Atomic add has a precision overflow. Check the operator precision."
→ 见 "atomic add 精度溢出" 子类型

# 结论2：地址异常
"The input/output memory address of the operator is abnormal"
→ 见 "算子输入输出数据地址异常" 子类型

# 结论3：其他硬件/软件错误
→ 结合 error code 和 errorStr 进一步分析

************4. Operator Input/Output Memory************
# 检查算子输入输出地址是否在合法范围
input[0] addr: 0x124080042000 end_addr:0x124080042100 size: 0x100
input[1] addr: 0xaaaaaaaa end_addr:0xaaaaaab2 size: 0x8   # [ERROR] out of range
input[2] addr: 0x0 end_addr:0x4 size: 0x4                 # [ERROR] out of range
# addr 为 0x0 或 0xaaaaaaaa 等异常值 → 内存越界/释放后使用
```

**分析结果包含：**
- 报错算子名称和对应源码位置
- AI Core Error 类型（向量/矩阵/内存/指令）
- 硬件寄存器状态（用于硬件故障判定）
- 算子输入输出内存地址合法性检查

### 收集 AI Core Error 问题信息

```bash
# 1. 收集 plog 日志
cp -r $HOME/ascend/log/debug/plog/ ./collected/plog/
cp -r $HOME/ascend/log/run/plog/ ./collected/plog_run/

# 2. 用 msnpureport 导出 Device 侧系统日志
msnpureport -d 0 -output ./collected/device0_syslog/   # -d 指定 device_id

# 3. 手动收集算子编译信息（算子 .o 和 .json 文件）
find ~/.cache/atc/ -name "*.o" -o -name "*.json" | \
    xargs -I{} cp {} ./collected/op_compile/

# 4. 收集环境信息
npu-smi info > ./collected/npu_smi_info.txt
dmesg | tail -200 > ./collected/dmesg.txt

# 5. 收集算子 dump 数据（精度分析需要）
# 在 acl.json 中配置 Dump 后重跑任务
# Dump 文件可用于对比算子输入输出与期望值

# 6. 收集 Profiling 数据（性能分析）
npu-smi info -t board -i 0 > ./collected/board_info.txt
```

### 常见 AI Core Error 子类型

| 子类型 | 典型现象 | 判断依据 | 根因 | 处理方向 |
|--------|---------|---------|------|---------|
| **HBM 比特 ECC 故障** | 固定 chipId 报错 | dmesg 含 `ECC error`；chipId 多次报错不变 | HBM 硬件位翻转 | 联系硬件支持；迁移工作负载到其他芯片 |
| **icache 数据校验故障** | `ifu error info` 非零，固定 core 报错 | core id 多次报错不变；ifu error info 非零 | 指令缓存校验失败 | 排查硬件；考虑算子改写绕过 |
| **AI Core 超时故障** | `EE1002 Execution_Error_Stream_Synchronize_Timeout` | 错误码 EE1002；plog 显示 task dispatch 后无 done 记录 | 算子执行挂起 | 检查算子 tiling；排查死循环逻辑 |
| **AI Core 硬件故障** | 持续固定 chipId/coreId 报错 | 同一位置重复报错；`npu-smi info -t health` 异常 | 芯片损坏 | 联系硬件支持，更换硬件 |
| **索引类算子索引越界** | `error code=0x800000` (数组越界) | error code 为 0x800000 | 算子输入 index 超出 Tensor 范围 | 检查算子输入 index Tensor 数值是否越界 |
| **atomic add 精度溢出** | msaicerr 输出 "Atomic add has a precision overflow" | msaicerr 结论为精度溢出；**且** slog 日志无 "Vm fault failed" 关键字 | FP16/BF16 atomic add 溢出 | 换用 FP32 accumulate；检查学习率；精度调优 |
| **算子输入输出数据地址异常** | msaicerr 输出 "memory address is abnormal" | info.txt 中 input[N] addr 为 0x0 或 0xaaaaaaaa 等异常值 | 内存越界 / 释放后使用 | 离线推理检查应用源码；框架场景联系技术支持 |
| **算子输入 args 下发前后不一致** | 结果随机错误 | msaicerr 无法定位明确错误；问题随机出现 | 多线程竞争 / 内存覆写 | 检查多流并发写入保护 |
| **Dump 数据失败** | Dump 目录无文件 | `EP0001`/`EP0002` 错误码 | Dump 路径/权限/磁盘问题 | 检查 Dump 路径权限和磁盘空间 |

### atomic add 精度溢出详细诊断

当 msaicerr 分析结果显示 "Atomic add has a precision overflow" 时，需进一步确认：

```bash
# 检查 Device slog 日志中是否有 "Vm fault failed"
grep -r "Vm fault failed" ./msnpureport_output/*/slog/dev-os-*/debug/device-os/device-os_*.log
```

- **无 "Vm fault failed"** → 确认是 atomic 精度溢出问题，通过精度调优解决
- **有 "Vm fault failed"** → 实际是内存越界问题，不是精度溢出，需按地址异常排查

> **注意**：Atlas A2 训练/推理系列产品上，由于硬件优化，不会出现 atomic add 精度溢出问题。

### 判断是否为硬件故障

```
判断硬件故障的依据：
1. chipId 是否固定 — 多次报错是否都是同一 chipId
2. core id 是否固定 — 是否总是同一 core 报错
3. npu-smi info -t ecc -i <id> — ECC 错误计数是否持续增长
4. dmesg | grep -i "ecc\|hardware\|pcie" — 是否有硬件相关报错
5. 同一算子在其他芯片上是否正常执行 — 交叉验证
6. npu-smi info -t health -i <id> — 健康状态是否异常
```

```bash
# 快速硬件故障排查脚本
echo "=== ECC 错误计数 ==="
npu-smi info -t ecc -i 0

echo "=== 设备健康状态 ==="
npu-smi info -t health -i 0

echo "=== dmesg 硬件错误 ==="
dmesg | grep -i "ecc\|hardware\|pcie\|ascend.*error" | tail -20

echo "=== HBM 内存状态 ==="
npu-smi info -t memory -i 0
```

---

## 内存 OOM 问题定位专题

### 问题现象

**Device 侧 HBM OOM：**
```
[ERROR][GE] Load graph to device failed: memory not enough
[ERROR][ACL] HBM memory allocation failed, requested=32GB, available=28GB
EL0004: Memory_Allocation_Failure
```

**Host 侧 CPU 内存 OOM：**
```
Out of memory: Kill process <pid> (python)
```

**框架层 OOM：**
```
RuntimeError: [Core] Out of memory. (DT: 2026-04-29)
# torch_npu 报类似 CUDA OOM 的错误信息
```

### 快速判断流程

```
OOM 现象
    │
    ├── Device 侧 HBM OOM?
    │   ├── 日志含 "HBM memory allocation failed" / "EL0004" / "memory not enough"
    │   ├── npu-smi info -t memory 显示 HBM 使用率接近 100%
    │   └── → 减小 batch size / 开启模型并行 / 使用量化 / 开启重计算
    │
    ├── Host 侧 CPU 内存 OOM?
    │   ├── dmesg 含 "Out of memory: Kill process"
    │   ├── 某个 rank 突然消失（进程被杀）
    │   ├── free -h 显示内存不足
    │   └── → 增大宿主机内存 / 减少 num_workers / 减小数据预取缓存
    │
    └── 训练框架层 OOM?
        ├── PyTorch: "RuntimeError: Out of Memory"
        ├── MindSpore: "Out of Memory"
        └── → 检查框架内存配置（如 torch.npu.set_per_process_memory_fraction）
```

### HBM 内存分析工具

```bash
# 实时监控 HBM 使用（指定 device_id）
npu-smi info -t memory -i 0

# CANN 各组件内存统计（需应用进程在运行时）
# 通过设置环境变量让 CANN 打印内存统计
export CANN_MEMORY_DEBUG=1

# 查看 GE 内存分配日志
grep -i "memory\|alloc\|free" $HOME/ascend/log/debug/plog/plog-*.log | \
    grep -i "GE\|ACL" | sort -k5

# 查看 Device 业务进程内存（通过 msnpureport 导出后分析 device syslog）
msnpureport -d 0 -output ./syslog/
grep -i "memory" ./syslog/*.log | grep -i "used\|free\|total"
```

### Host 侧内存分析

```bash
# 查看 OOM Killer 记录
dmesg | grep -i "out of memory\|oom-kill\|killed process"

# 查看进程内存占用排序
ps aux --sort=-%mem | head -20

# 实时监控内存
watch -n 1 free -h

# HCCL 通信 buffer 占用分析
grep -i "hccl.*buffer\|hccl.*memory" $HOME/ascend/log/debug/plog/plog-*.log
```

### asan 工具检测内存错误（Host 侧）

```bash
# 编译时开启 asan（检测越界、use-after-free 等）
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.5
export ASAN_OPTIONS="halt_on_error=0:log_path=/tmp/asan_report"
python train.py

# 查看 asan 报告
cat /tmp/asan_report.*
```

### 典型 OOM 场景与解决方案

| 场景 | 现象 | 根因 | 解决方案 |
|------|------|------|---------|
| 大模型推理图加载 OOM | `Load graph failed`, HBM 100% | 模型参数+激活+KV cache 超 HBM 容量 | 模型并行/量化推理/减小 KV cache |
| 训练激活内存 OOM | 训练中 step 开始时 OOM | 激活内存未复用/未重计算 | 开启 activation checkpointing/recompute |
| HCCL 通信 buffer OOM | 通信阶段 OOM | HCCL 内部 buffer 占用过多 | 减小 buffer_size/减少通信频率 |
| 数据预处理 Host OOM | DataLoader 阶段 Host OOM Kill | num_workers 过多/预取缓存过大 | 减少 num_workers/prefetch_factor |
| 多卡训练某 rank OOM | 某 rank 被 Kill，其余 rank 卡住 | 该 rank 额外分配了内存（如日志/缓存） | 均衡各 rank 内存分配 |

### 内存优化手段速查

```python
# PyTorch + torch_npu 常用优化

# 1. 减小 batch size
batch_size = 8  # 从 32 减小

# 2. 开启梯度检查点（减少激活内存）
from torch.utils.checkpoint import checkpoint
output = checkpoint(model_layer, input)

# 3. 开启混合精度（减少模型内存）
from torch_npu.contrib import transfer_to_npu
# AMP 自动处理

# 4. 设置内存增长模式
torch.npu.set_per_process_memory_fraction(0.9, device=0)

# 5. 手动清理缓存
torch.npu.empty_cache()

# 6. 开启重计算（MindSpore）
# model = mindspore.nn.Recompute(model)
```

```bash
# 环境变量方式优化

# 开启 GE 内存复用
export GE_USE_STATIC_MEMORY=1

# 设置 HCCL buffer 大小
export HCCL_BUFFSIZE=120

# 减少算子编译缓存占用
export ASCEND_OPP_PATH=/usr/local/Ascend/ascend-toolkit/latest/opp
```

---

## 进程中断问题定位专题

### 问题现象

应用程序异常退出（非正常结束），可能伴随 coredump 文件或 Python 异常栈：

```
Segmentation fault (core dumped)
RuntimeError: CANN error, error code: ...
Fatal Python error: Segmentation fault
Aborted (core dumped)
# 有时无明显报错，进程直接消失
```

### 完整定位流程

```
Step 1: 确认进程退出方式
    ├── 进程退出码 → echo $?
    │   139 = SIGSEGV (段错误)
    │   134 = SIGABRT (异常终止)
    │   137 = SIGKILL (被杀，通常是 OOM Killer)
    ├── dmesg 中是否有 OOM Kill / signal 信息
    └── 是否产生 coredump 文件

Step 2: 收集故障信息
    ├── plog 日志 → 最后一条 ERROR 日志定位触发位置
    ├── coredump 文件 → ulimit -c unlimited 开启后收集
    ├── Python 堆栈 → faulthandler 模块
    └── Host 侧 dmesg / syslog

Step 3: 分析 coredump
    ├── 使用 asys 工具: asys analyze -coredump core.xxx
    ├── 或使用 gdb: gdb -c core.xxx <executable>
    └── 查看崩溃时线程堆栈

Step 4: 结合 plog 分析时序
    ├── plog 中最后几条日志判断崩溃阶段
    ├── 是否在 aclrtSetDevice / aclFinalize 等关键接口
    └── 是否有内存相关报错先于崩溃

Step 5: 按典型场景匹配处理
```

### coredump 分析工具

```bash
# 开启 coredump（任务启动前执行）
ulimit -c unlimited

# 查找 coredump 文件
find / -name "core.*" -newer /tmp/task_start_time 2>/dev/null

# 使用 asys 分析（推荐）
asys analyze -coredump core.python.12345

# 使用 gdb 分析
gdb /usr/bin/python3 core.python.12345 -batch \
    -ex "thread apply all bt" -ex "info threads" -ex "quit"

# Python faulthandler（在代码中启用）
import faulthandler
faulthandler.enable()
# 崩溃时会自动打印线程堆栈到 stderr
# 也可输出到文件: faulthandler.enable(file=open('/tmp/crash.log', 'w'))
```

### 典型案例

#### 调用 SetDevice 接口错误导致无可用 Context

**现象**：多线程/多进程场景下程序崩溃，日志出现 `context not available`

**诊断命令**：
```bash
grep -i "context.*not.*available\|SetDevice" plog-*.log
```

**根因**：在错误线程中调用 `aclrtSetDevice`，导致其他线程的 Context 失效

**处理**：确保每个线程独立创建 Context，`aclrtSetDevice` 与 `aclrtCreateContext` 在同一线程中调用

#### rtMemcpyAsync 异步参数校验报错

**现象**：`rtMemcpyAsync execute failed, errorStr=Invalid_Argument`，进程退出

**诊断命令**：
```bash
grep -i "rtMemcpyAsync.*failed\|Invalid_Argument" plog-*.log
```

**根因**：传入的 src/dst 内存地址非法（空指针或已释放内存）

**处理**：在 `rtMemcpyAsync` 调用前校验地址有效性；确认内存生命周期覆盖异步操作完成

#### 算子执行过程中 D2D 拷贝出错

**现象**：`EI0012 Execution_Error_SDMA` 或 `D2D copy failed`

**诊断命令**：
```bash
grep -i "EI0012\|SDMA\|D2D.*failed" plog-*.log
npu-smi info -t board -i 0
dmesg | grep -i "pcie.*error\|sdma"
```

**根因**：PCIe 链路异常或 Device 间通信错误

**处理**：检查 PCIe 链路状态（`npu-smi info -t board`）；查看 dmesg 中的 PCIe 错误

#### 环境变量访问冲突导致应用程序异常终止

**现象**：多进程场景下随机崩溃，堆栈指向 `getenv`/`setenv` 相关调用

**诊断命令**：
```bash
gdb /usr/bin/python3 core.python.xxx -batch -ex "thread apply all bt"
# 堆栈中出现 getenv/setenv 调用
```

**根因**：多线程并发读写环境变量，glibc 的 `getenv` 非线程安全

**处理**：在主线程初始化阶段完成所有 `setenv` 调用；业务线程只读环境变量

#### 析构函数中调用去初始化接口 aclFinalize 导致 coredump

**现象**：程序正常结束但产生 coredump，堆栈在 `aclFinalize`

**诊断命令**：
```bash
gdb /usr/bin/python3 core.python.xxx -batch -ex "bt"
# 堆栈显示在 aclFinalize 或 __gcov_exit 等 cleanup 函数中
```

**根因**：全局/静态对象析构顺序晚于 `aclFinalize`，导致 ACL 已去初始化后仍被访问

**处理**：手动管理 ACL 生命周期，确保在所有 ACL 对象析构 **之后** 调用 `aclFinalize`

#### Signal 11 (SIGSEGV) 段错误

**现象**：进程退出码 139，有 coredump 文件

**诊断命令**：
```bash
echo $?  # 返回 139
ls -la core.*  # coredump 存在
gdb /usr/bin/python3 core.python.xxx -batch -ex "thread apply all bt" -ex "quit"
```

**根因**：空指针解引用 / 内存越界 / 释放后使用

**处理**：gdb 分析 coredump 定位具体代码行；结合 asan 工具检测内存错误

---

## 进程卡住问题定位专题

### 问题现象

应用程序无输出、无超时报错，长时间挂起：

```bash
# 进程存在但无进展
ps aux | grep python
# CPU 使用率 ~0%，但进程未退出

# 训练 loss 长时间不变
[INFO] step=1000, loss=2.345   # 之后无新输出

# plog 最后一条日志停留在很久以前
# 无 ERROR 日志，但最后一条 INFO 日志时间戳在几分钟甚至几十分钟前
```

### 完整定位流程

```
Step 1: 确认卡住状态
    ├── 进程是否存在: ps aux | grep <pid>
    ├── CPU 使用率: top -p <pid>  → ~0% 确认卡住
    ├── 是否有新日志输出: tail -f $HOME/ascend/log/debug/plog/plog-*.log
    └── strace 快速查看: strace -p <pid> -c -f
        （看是否阻塞在某个系统调用）

Step 2: 判断卡住阶段
    ├── plog 最后一条日志内容 → 判断在编译/执行/通信哪个阶段
    ├── 如果在 HCCL 通信阶段 → 检查多卡同步
    ├── 如果在数据加载阶段 → 检查 DataLoader / IO
    └── 如果在算子执行阶段 → 检查是否有 AI Core 超时

Step 3: 导出进程堆栈
    ├── Python 进程: py-spy dump --pid <PID>
    ├── C++ 进程: gdb -p <PID> -batch -ex "thread apply all bt" -ex "quit"
    ├── 推荐: asys stack -pid <PID> -output ./stack/
    └── Python faulthandler: kill -SIGUSR1 <PID> (部分框架支持)

Step 4: 多卡场景特殊排查
    ├── 各 rank 进程状态是否一致（是否某 rank 已退出）
    ├── dmesg 检查 OOM Kill: dmesg | grep -i "kill process"
    ├── 各 rank plog 对比，找到最后完成同步的步骤
    └── 检查 HCCL 超时日志: grep -i "EI0002\|timeout" plog-*.log

Step 5: 根据卡住类型针对性处理
```

### 典型案例

#### fork 方式创建子进程导致应用卡死

**现象**：训练脚本在 `DataLoader` 或 `multiprocessing.Pool` 初始化后卡死

**诊断**：
```bash
# 导出卡住进程的堆栈
py-spy dump --pid <PID>
# 或
asys stack -pid <PID> -output ./stack/

# 如果堆栈显示在 fork/waitpid 等调用，且使用了 ACL Context
```

**根因**：`fork` 方式继承了父进程的 ACL Context/Stream 等状态，子进程操作这些资源导致死锁

**处理**：使用 `spawn` 或 `forkserver` 启动方式：
```python
# PyTorch DataLoader
torch.utils.data.DataLoader(
    dataset,
    num_workers=4,
    multiprocessing_context='spawn'  # 关键设置
)

# 全局设置
torch.multiprocessing.set_start_method('spawn')
```

#### HCCL AllReduce 超时导致所有 rank 卡死

**现象**：多卡训练，所有进程在同一步卡住，120s 后触发 `EI0002 Communication_Error_Timeout`

**诊断步骤**：
```bash
# 1. 检查各 rank 进程状态
for i in $(ps aux | grep "torchrun\|python.*train" | awk '{print $2}'); do
    echo "PID=$i, CPU=$(ps -p $i -o %cpu= | tr -d ' ')%"
done

# 2. 检查是否有 rank 被 OOM Killer 杀掉
dmesg | grep -i "out of memory\|killed process"

# 3. 查看各 rank 最后的日志
for f in plog-*.log; do echo "=== $f ==="; tail -5 "$f"; done

# 4. 检查 HCCL 超时日志
grep -i "EI0002\|timeout\|AllReduce.*timeout" plog-*.log
```

**根因**：某 rank（通常是内存耗尽或主机 OOM Killer 杀死的进程）未完成梯度同步

**处理**：
1. 检查各 rank 宿主机内存 `free -h`
2. 查看是否有 `Out of memory: Kill process` in dmesg
3. 增大超时时间辅助诊断：`export HCCL_EXEC_TIMEOUT=600`
4. 减少 `num_workers` 或数据预取缓存

#### 数据加载卡死

**现象**：训练启动后第一个 step 都无法完成，卡在 DataLoader

**诊断**：
```bash
# 导出堆栈
py-spy dump --pid <PID>
# 堆栈显示在 DataLoader worker 进程的 fork 相关调用
```

**根因**：multiprocessing 方式为 fork，继承了 ACL Context

**处理**：使用 spawn 方式启动 worker 进程：
```python
torch.utils.data.DataLoader(
    dataset, num_workers=4,
    multiprocessing_context='spawn'
)
```

#### 算子执行挂起导致 AI Core 超时

**现象**：单算子或特定算子执行后无返回，最终触发 `EE1002`

**诊断**：
```bash
# plog 显示 task_id 已 dispatch 但无 done 记录
grep -i "dispatch.*task_id=442\|done.*task_id=442" plog-*.log
# 只有 dispatch 没有 done → 算子挂起
```

**根因**：算子内部死循环或 tiling 参数导致超长执行

**处理**：
1. 检查算子 tiling 参数是否合理
2. 使用 Profiling 分析算子执行时间
3. 简化算子输入 shape 排查

#### 分布式初始化阶段卡住

**现象**：训练脚本启动后停留在 `init_process_group` 阶段

**诊断**：
```bash
# plog 无任何 GE/HCCL 日志，说明连图编译都没开始
grep -c "GE\|HCCL" plog-*.log  # 输出 0

# 检查网络连通性
ping <other_node_ip>
nc -zv <other_node_ip> <port>
```

**根因**：rank_table 配置错误/网络不通/端口占用

**处理**：
1. 检查 rank_table 文件中各 rank 的 IP 和端口
2. 确认各节点间网络连通
3. 确认端口未被占用：`netstat -tlnp | grep <port>`

### asys 工具在卡住场景的使用

```bash
# 实时导出卡住进程堆栈
asys stack -pid <PID> -output ./stack_dump/

# 健康检查（检查 Device 硬件和驱动状态）
asys health -d 0

# 综合检测（全面检测软硬件、网络、驱动状态）
asys check -all

# 性能数据采集（分析是否有性能瓶颈）
asys perf -d 0 -duration 60
```

---

## 故障定位工具

### asys 工具

asys 是一站式故障信息收集与分析工具，功能包括：

| 功能 | 命令示例 | 说明 |
|------|---------|------|
| 故障信息收集 | `asys collect -o ./output/` | 一键收集日志、环境信息 |
| 业务复跑+收集 | `asys rerun -cmd "python train.py" -o ./output/` | 复现故障同时收集信息 |
| 健康检查 | `asys health -d 0` | 检查 Device 0 硬件和驱动状态 |
| 综合检测 | `asys check -all` | 全面检测软硬件、网络、驱动状态 |
| AI Core Error 解析 | `asys analyze -aicore -log ./output/` | 解析 AI Core Error 日志 |
| coredump 解析 | `asys analyze -coredump core.xxx` | 解析应用 coredump 文件 |
| trace 文件解析 | `asys analyze -trace ./trace_file` | 解析 trace 文件 |
| stackcore 解析 | `asys analyze -stackcore ./stackcore_file` | 解析堆栈 core 文件 |
| 实时堆栈导出 | `asys stack -pid <PID>` | 导出卡住进程的当前堆栈 |
| 性能数据采集 | `asys perf -d 0 -duration 60` | 采集 Device 0 性能数据 |

### msaicerr 工具

专门用于解析 AI Core Error，能够将二进制错误信息还原为可读的算子错误报告：

```bash
# 基本用法
msaicerr -i ./msnpureport_output/ -o ./analysis_result/

# 指定报错的 task_id 进行精确分析
msaicerr -i ./msnpureport_output/ -task_id 442 -o ./analysis_result/

# 查看分析结果
cat ./analysis_result/info.txt
```

**分析结果包含**：
- 报错算子名称和对应源码位置
- AI Core Error 类型（向量/矩阵/内存/指令）
- 硬件寄存器状态（用于硬件故障判定）
- 算子输入输出内存地址合法性检查

---

## 常用定位操作

### 通过 Device 日志获取故障 ID 并排查 RAS 硬件故障

```bash
# 1. 导出 Device 侧系统日志
msnpureport -d 0 -output ./device_syslog/

# 2. 搜索 RAS 故障 ID
grep -i "fault_id\|ras\|ecc\|hardware" ./device_syslog/*.log

# 3. 通过 npu-smi 查看 ECC 错误计数
npu-smi info -t ecc -i 0
```

### 通过 Device 日志查看资源占用过高的信息

```bash
msnpureport -d 0 -output ./syslog/
grep -E "memory|stream|event|notify" ./syslog/*.log | grep -i "high\|overflow\|exceed"
```

### 通过 Device 日志确认 Host 进程的拉起与结束时间

```bash
msnpureport -d 0 -output ./syslog/
grep -E "process_start|process_end|pid=[0-9]+" ./syslog/*.log
```

### 查看 Python / C++ 应用程序的堆栈

```bash
# Python 进程实时堆栈（py-spy 工具）
pip install py-spy
py-spy dump --pid <PID>

# Python 内置方式（向进程发送信号）
kill -SIGUSR1 <PID>   # 部分框架支持

# C++ 进程实时堆栈（gdb）
gdb -p <PID> -batch -ex "thread apply all bt" -ex "quit"

# 使用 asys 工具（推荐）
asys stack -pid <PID> -output ./stack_dump/
```

---

## 故障案例集索引

以下典型案例已收录于 [cases.md](./cases.md)：

| 案例 ID | 问题类型 | 关键现象 |
|---------|---------|---------|
| CASE-001 | AI Core Error / 精度 | 训练 loss 突变为 NaN（FP16 溢出） |
| CASE-002 | 进程卡住 / HCCL 超时 | 8 卡训练全部 rank 卡死 120s 后超时 |
| CASE-003 | TBE 编译失败 | UB memory overflow（自定义算子 tiling 过大） |
| CASE-004 | HBM OOM | 大模型推理图加载失败 |
| CASE-005 | 精度不达标 | FP16 MatMul 结果差异超阈值 |
| CASE-006 | 日志丢失 | 长时间任务 plog 轮转覆盖早期错误 |
