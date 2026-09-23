# msnpureprot 日志采集规范

## 概述

msnpureprot（MindSpore NPU Protocol）是 CANN 框架中用于宿主机与 NPU 设备之间通信的协议层日志。该日志记录算子下发指令、设备响应状态及底层驱动交互信息，是定位算子执行失败、超时或结果异常的关键依据。

## 日志位置

| 路径 | 说明 |
|------|------|
| `/var/log/npu/slog/host-0/` | 宿主机侧协议日志（按日期分目录） |
| `/var/log/npu/slog/device-*/` | 设备侧协议日志（`*` 为设备 ID，0~7） |
| `/usr/local/Ascend/cann-8.5.0/log/` | CANN 框架内部协议日志 |

## 日志级别

| 级别 | 数值 | 说明 |
|------|------|------|
| DEBUG | 0 | 详细通信帧信息 |
| INFO  | 1 | 正常下发与响应 |
| WARNING | 2 | 非致命异常，可能影响性能 |
| ERROR | 3 | 执行失败，需要重点关注 |
| FATAL | 4 | 不可恢复错误 |

## 开启采集

```bash
# 设置日志级别为 INFO（推荐）
export ASCEND_GLOBAL_LOG_LEVEL=1

# 或通过配置文件修改（持久化）
vim /usr/local/Ascend/cann-8.5.0/tools/configure/acl.json
# 修改 "log_level" 字段为 1
```

## 采集命令

```bash
# 采集当前设备所有 msnpureprot 日志
cp -r /var/log/npu/slog/ ./logs/msnpureprot/

# 仅采集最近 1 小时的日志（按修改时间过滤）
find /var/log/npu/slog/ -name "*.log" -mmin -60 -exec cp {} ./logs/msnpureprot/ \;

# 采集特定设备的日志（设备 ID=0）
cp /var/log/npu/slog/device-0/*.log ./logs/msnpureprot/device-0/
```

## 关键字段说明

| 字段 | 示例 | 含义 |
|------|------|------|
| `[taskid]` | `[task:1024]` | 任务唯一标识 |
| `[streamid]` | `[stream:3]` | 执行流编号 |
| `[retcode]` | `retcode=0` | 返回码，非 0 表示异常 |
| `[op_type]` | `MatMul` | 算子类型 |
| `[time_cost]` | `1.23ms` | 执行耗时 |

## 注意事项

- 采集前确认 `/var/log/npu/` 目录权限（通常需要 root 或 HwHiAiUser）
- 日志文件可能较大（单文件可达数 GB），按需使用时间范围过滤
- 采集后建议压缩：`tar -czf msnpureprot_logs.tar.gz ./logs/msnpureprot/`
