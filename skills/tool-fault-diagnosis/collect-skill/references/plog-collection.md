# plog 日志采集规范

## 概述

plog（Process Log）是 CANN 框架的运行时日志组件，记录图编译（Graph Compile）、算子调度（Op Schedule）、内存管理、执行时序等框架级别信息。plog 是分析性能瓶颈、图编译失败、算子不支持等问题的主要日志来源。

## 日志位置

| 路径 | 说明 |
|------|------|
| `$HOME/ascend/log/plog/` | 默认用户级 plog 存储路径 |
| `/root/ascend/log/plog/` | root 用户路径 |
| `/var/log/npu/slog/host-0/` | 部分版本的 plog 与 slog 混合存储 |
| 任务工作目录下 `./ascend_work_path/log/` | 通过 `ASCEND_WORK_PATH` 自定义时的路径 |

> 可通过环境变量 `ASCEND_LOG_PATH` 自定义输出路径

## 日志分类

| 日志类型 | 文件命名模式 | 内容 |
|----------|-------------|------|
| 图编译日志 | `plog_compile_*.log` | ATC/GE 编译阶段事件 |
| 运行时日志 | `plog_runtime_*.log` | 算子执行、调度时序 |
| 内存日志 | `plog_memory_*.log` | HBM/UB 内存分配记录 |
| 通用进程日志 | `plog_*.log` | 综合运行日志 |

## 开启详细日志

```bash
# 开启 DEBUG 级别 plog（慎用，日志量大）
export ASCEND_GLOBAL_LOG_LEVEL=0

# 推荐开启 INFO 级别
export ASCEND_GLOBAL_LOG_LEVEL=1

# 开启算子执行 profiling（配合 plog 分析性能）
export ASCEND_PROFILING_MODE=1

# 自定义日志输出路径
export ASCEND_LOG_PATH=/tmp/my_logs/
```

## 采集命令

```bash
# 采集默认路径的 plog
cp -r $HOME/ascend/log/plog/ ./logs/plog/

# 按时间过滤（最近 2 小时）
find $HOME/ascend/log/plog/ -name "*.log" -mmin -120 -exec cp {} ./logs/plog/ \;

# 如果使用了自定义路径
cp -r $ASCEND_LOG_PATH/plog/ ./logs/plog/ 2>/dev/null

# 采集图编译产物（IR 图，用于分析算子融合）
find $HOME/ascend/ -name "*.ir" -o -name "*.dot" 2>/dev/null | head -20 | xargs -I{} cp {} ./logs/plog/ir/

# 查看 plog 日志摘要（最后 100 行）
tail -n 100 $HOME/ascend/log/plog/plog_*.log | less
```

## 关键字段说明

| 字段 | 示例 | 含义 |
|------|------|------|
| `[GE]` | `[GE][INFO]` | Graph Engine 组件前缀 |
| `[GE][COMPILE]` | — | 图编译阶段 |
| `[SCHE]` | — | 调度器日志 |
| `[MEM]` | — | 内存管理日志 |
| `op_name` | `MatMulV2` | 算子名称 |
| `total_time` | `2.54ms` | 算子总耗时 |
| `aicore_time` | `1.23ms` | AICore 执行时间 |

## 日志大小控制

```bash
# 查看 plog 目录大小
du -sh $HOME/ascend/log/plog/

# 清理 7 天前的旧日志（确认不需要后执行）
find $HOME/ascend/log/plog/ -name "*.log" -mtime +7 -delete
```

## 注意事项

- 每次任务运行会生成新的 plog 文件，建议任务结束后立即采集，避免被轮转覆盖
- 性能分析时同时采集 profiling 数据（`$HOME/ascend/log/profiling/`）
- 多进程/多卡训练时，每个 rank 有独立的 plog 文件，注意全部采集
