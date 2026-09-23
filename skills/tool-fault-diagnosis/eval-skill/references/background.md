# CANN 日志分析背景介绍

> 本文档为 LLM 提供分析 Ascend NPU 日志所需的领域背景知识。

## 硬件平台

| 属性 | 值 |
|------|-----|
| 芯片型号 | Ascend NPU |
| 架构 | aarch64 |
| AICore 数量 | 48 |
| UB (Unified Buffer) per Core | 256 KB |
| HBM 带宽 | ~2 TB/s |
| 支持数据类型 | FP32, FP16, BF16, INT8, INT4 |

## 软件栈（CANN 8.5.0）

```
应用层（PyTorch / MindSpore / TensorFlow）
       │
       ▼
  CANN 框架层
  ┌─────────────────────────────────────┐
  │  GE（Graph Engine）图编译与优化      │
  │  HCCL  多卡/多机通信库              │
  │  ACL   设备管理与内存 API            │
  │  TBE   算子编译（Cube/Vector）       │
  └─────────────────────────────────────┘
       │
       ▼
  驱动层（Ascend HDK Driver）
       │
       ▼
  硬件（Ascend NPU）
```

## 关键组件说明

### GE (Graph Engine)
- 负责接收来自框架的计算图，进行图优化（算子融合、内存复用）和图编译
- 日志前缀：`[GE]`
- 关键阶段：`GRAPH_BUILD` → `GRAPH_COMPILE` → `GRAPH_LOAD` → `GRAPH_RUN`

### TBE (Tensor Boost Engine)
- 负责单算子的内核编译，生成 AICore/AIVector 可执行指令
- 编译失败常见原因：shape 不支持、dtype 不匹配、UB 内存溢出
- 日志前缀：`[TBE]` / `[TE]`

### ACL (Ascend Computing Language)
- 提供设备上下文管理、内存分配（HBM）、数据传输（H2D/D2H）
- 错误码以 `ACL_ERROR_` 开头
- 日志前缀：`[ACL]`

### HCCL (Huawei Collective Communication Library)
- 多卡通信原语：AllReduce、AllGather、Broadcast、ReduceScatter
- 依赖 ROCE 或 PCIe 网络，超时默认 120s
- 日志前缀：`[HCCL]`

### msnpureprot
- 协议层，宿主机与 NPU 设备间的消息通信
- 记录算子下发（dispatch）和执行完成（notify）事件

## 常见执行阶段与日志对应

| 阶段 | 日志特征 | 常见问题 |
|------|---------|---------|
| 图编译 | `[GE][COMPILE]` BUILD_GRAPH | shape 推导失败、不支持的算子 |
| 算子编译(TBE) | `[TBE]` compile op | 编译超时、UB 溢出 |
| 图加载 | `[GE]` load graph to device | 内存不足（HBM OOM） |
| 算子执行 | `[SCHE]` dispatch task | 执行超时、返回码非 0 |
| 通信同步 | `[HCCL]` allreduce | 超时、rank 断联 |
| 数据传输 | `[ACL]` memcpy | H2D/D2H 失败 |

## 常见错误类型速查

| 错误现象 | 初步排查方向 |
|---------|-------------|
| 训练 loss 为 NaN | 溢出（FP16 精度问题）、权重初始化异常 |
| 任务挂死无输出 | HCCL 通信死锁、某 rank 崩溃导致其余 rank 等待 |
| OOM (Out of Memory) | HBM 容量不足，需减小 batch size 或启用重计算 |
| 算子不支持 | dtype/shape 超出 TBE 支持范围，需换算子或转换数据类型 |
| 图编译超时 | 图过大或 TBE 编译复杂，可尝试开启编译缓存 |
| 精度不达标 | 算子精度 bug、量化配置错误、通信精度损失 |
