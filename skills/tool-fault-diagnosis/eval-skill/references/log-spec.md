# CANN 日志规范

> 本文档定义 Ascend NPU / CANN 8.5.0 各类日志的格式、字段含义和时序关系，用于日志清洗和分析阶段的正确解读。
> 官方参考：[日志简介（社区版 9.0.0-beta.2）](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/maintenref/logreference/logreference_0001.html) / [查看日志（Ascend EP）](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/maintenref/logreference/logreference_0002.html)

## 通用日志格式

### 标准行格式（官方定义）

```
[Level] ModuleName(PID,PName):DateTimeMS [FileName:LineNumber]LogContent
```

**实际示例：**
```
[ERROR] TEFUSION(12940,atc):2021-10-17-05:54:07.599.074 [tensor_engine/te_fusion/pywrapper.cc:33]InitPyLogger Failed to import te.platform.log_util
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `Level` | 日志级别：ERROR / WARNING / INFO / DEBUG | `[ERROR]` |
| `ModuleName` | 产生日志的模块名称 | `TEFUSION`、`GE`、`HCCL` |
| `PID` | 模块进程 ID | `12940` |
| `PName` | 模块进程名称 | `atc` |
| `DateTimeMS` | 日志打印时间，格式 `yyyy-mm-dd-hh:mm:ss.fff.zzz`（年-月-日-时:分:秒:毫秒:微秒） | `2021-10-17-05:54:07.599.074` |
| `FileName:LineNumber` | 调用日志打印接口的源码文件名及行号 | `pywrapper.cc:33` |
| `LogContent` | 各模块具体日志内容 | `InitPyLogger Failed to import te.platform.log_util` |

### 常见模块名称

| ModuleName | 模块 |
|------|------|
| `GE` | Graph Engine（图编译与调度） |
| `TBE` / `TE` / `TEFUSION` | TBE 算子编译器 / TE Fusion |
| `ACL` | ACL 设备管理接口 |
| `HCCL` | 集合通信库 |
| `SCHE` / `RUNTIME` | 任务调度器 / 运行时 |
| `AICPU` | AI CPU 算子执行进程 |
| `HCCP` | HCCL 代理进程 |
| `PROF` | Profiling 模块 |

---

## 日志分类与路径（Ascend EP 形态）

> **日志分类**：应用类日志（AI 应用程序产生）和系统类日志（Device 侧系统运行信息）。
> 系统类日志需用 `msnpureport` 工具导出到 Host 侧查看。

### 应用类日志路径

```
$HOME/ascend/log/
├── debug/
│   ├── device-<id>/
│   │   └── device-<pid>_<timestamp>.log   # Device 侧调试日志（AI CPU、HCCP 等）
│   └── plog/
│       └── plog-<pid>_<timestamp>.log     # Host 侧调试日志（GE/FE/TBE/HCCL/Runtime 等）
├── run/
│   ├── device-<id>/
│   │   └── device-<pid>_<timestamp>.log   # Device 侧运行日志
│   └── plog/
│       └── plog-<pid>_<timestamp>.log     # Host 侧运行日志
└── security/
    ├── device-<id>/
    │   └── device-<pid>_<timestamp>.log   # Device 侧安全日志
    └── plog/
        └── plog-<pid>_<timestamp>.log     # Host 侧安全日志
```

| 路径 | 主要内容 | 关键模块 |
|------|---------|--------|
| `debug/plog/plog-<pid>_*.log` | Host 侧调试日志 | GE、FE、AI CPU、TBE/HCCL（compiler）；AscendCL、GE、Runtime、Driver 用户态（runtime） |
| `run/plog/plog-<pid>_*.log` | Host 侧运行日志 | 同上（运行级别） |
| `debug/device-<id>/device-<pid>_*.log` | Device 侧调试日志 | AI CPU、HCCP 等 Device 侧组件 |
| `run/device-<id>/device-<pid>_*.log` | Device 侧运行日志 | 同上（运行级别） |

> **注意**：Device 侧应用类日志由 `slogd` 进程自动回传到 Host 侧（默认延时 2000ms）。若回传超时则直接在 Device 侧落盘。
> **容器内**不支持查看 Device 侧系统类日志，也不支持通过 `msnpureport` 导出。

### 相关环境变量

| 环境变量 | 作用 | 示例 |
|---------|------|------|
| `ASCEND_GLOBAL_LOG_LEVEL` | 设置全局日志级别（0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR） | `export ASCEND_GLOBAL_LOG_LEVEL=1` |
| `ASCEND_PROCESS_LOG_PATH` | 指定应用类日志落盘路径 | `export ASCEND_PROCESS_LOG_PATH=/data/logs` |
| `ASCEND_SLOG_PRINT_TO_STDOUT` | 同时将日志打印到屏幕（1=开启） | `export ASCEND_SLOG_PRINT_TO_STDOUT=1` |
| `ASCEND_HOST_LOG_FILE_NUM` | 每个进程保留的日志文件数（默认 10） | `export ASCEND_HOST_LOG_FILE_NUM=50` |
| `ASCEND_LOG_DEVICE_FLUSH_TIMEOUT` | Device 侧日志回传到 Host 侧的超时时间（ms，默认 2000） | `export ASCEND_LOG_DEVICE_FLUSH_TIMEOUT=5000` |
| `ASCEND_LOG_SYNC_SAVE` | 日志拥塞时不丢弃日志（1=开启，影响性能） | `export ASCEND_LOG_SYNC_SAVE=1` |
| `ASCEND_WORK_PATH` | 设置单机独享文件（含日志）的存储路径 | `export ASCEND_WORK_PATH=/workspace/rank0` |

---

## plog 日志规范

### 文件命名

```
plog-<pid>_<timestamp>.log
```
示例：`plog-16027_20220618001623878.log`

### 关键日志序列（正常执行）

```
[INFO][GE] Build graph start, graph_id=1
[INFO][GE] Graph optimize success
[INFO][TBE] Start compile op: MatMulV2, shape=[1024,1024]x[1024,512]
[INFO][TBE] Compile op success: MatMulV2, cost=234ms
[INFO][GE] Load graph to device success, graph_id=1
[INFO][SCHE] Dispatch task, task_id=100, stream_id=3, op=MatMulV2
[INFO][SCHE] Task done, task_id=100, retcode=0, time_cost=1.23ms
```

### 关键字段

| 字段名 | 示例 | 含义 |
|--------|------|------|
| `graph_id` | `graph_id=1` | 图唯一标识 |
| `task_id` | `task_id=100` | 任务唯一标识 |
| `stream_id` | `stream_id=3` | 执行流编号（并行流） |
| `op` / `op_type` | `op=MatMulV2` | 算子类型名称 |
| `shape` | `shape=[1024,1024]` | Tensor 维度 |
| `dtype` | `dtype=FP16` | 数据类型 |
| `retcode` | `retcode=0` | 返回码（0=成功） |
| `time_cost` | `time_cost=1.23ms` | 执行耗时 |
| `cost` | `cost=234ms` | 编译耗时 |

---

## msnpureprot 日志规范

### 关键日志序列

```
[INFO][HOST] Send cmd to device, device_id=0, task_id=100, cmd_type=DISPATCH
[INFO][DEVICE-0] Recv cmd, task_id=100, op=MatMulV2
[INFO][DEVICE-0] Op execute done, task_id=100, retcode=0
[INFO][HOST] Recv notify from device, task_id=100, retcode=0
```

### 关键字段

| 字段名 | 含义 |
|--------|------|
| `device_id` | 设备编号（0~7） |
| `cmd_type` | 命令类型（DISPATCH/SYNC/RESET） |
| `retcode` | 设备侧返回码 |

---

## host 日志规范

### dmesg / syslog 关键模式

| 模式 | 含义 |
|------|------|
| `ascend: device 0 reset` | 设备 0 发生复位（严重） |
| `npu driver loaded` | 驱动加载成功 |
| `Out of memory: Kill process` | 宿主机 OOM，进程被杀 |
| `HCCL rank X disconnected` | 通信 rank X 断联 |

---

## 日志时序关系

```
宿主机时间       设备时间（可能有偏移，通常 < 1ms）
    │                   │
    ├── Send cmd ───────►│
    │                   ├── Execute op
    │                   │    (time_cost)
    │◄─── Notify ───────┤
    │
  total_time = send + execute + notify
```

> **注意**：多设备场景下宿主机与设备时钟可能有微小偏移（通常 < 1ms），分析跨设备时序时需考虑此因素。

---

## 日志轮转规则

| 日志类型 | 单文件大小上限 | 保留文件数 | 存储路径 |
|---------|-------------|----------|---------|
| plog | 100 MB | 10 | `$HOME/ascend/log/plog/` |
| slog/msnpureprot | 200 MB | 20 | `/var/log/npu/slog/` |
| HCCL | 50 MB | 5 | `./hccl_logs/` |

> 长时间任务可能发生日志轮转，需采集全部轮转文件。
