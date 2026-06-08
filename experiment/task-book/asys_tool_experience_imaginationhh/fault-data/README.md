# fault-data 说明

本目录用于存放 asys 三流程的采集/解析产物：

| 子目录 | 来源命令 | 内容 |
|---|---|---|
| `collect/` | `bash collect.sh` | `asys collect` 输出（无复跑场景的运维/故障信息） |
| `launch/` | `bash launch_rerun.sh` | `asys launch` 输出（业务复跑 + 故障现场，含 screen.txt / data-dump / plog） |
| `analyze/` | `bash analyze_aicore_error.sh <launch输出>` | `asys analyze -r=aicore_error` 输出（含 `info.txt`） |

> **关于原始数据**：本次提交未附原始采集日志/Dump（与 msprof demo 的 `perf_data_demo`
> 处理一致——实采产物体积大、含环境相关的历史进程日志，不入库）。三个子目录的产物
> 均可由仓库内脚本一键复现，复现步骤见 [上层 README 的「复现步骤」](../README.md)。
> 各产物的结构与含义（`dfx/log/host/cann/`、`dfx/data-dump/`、辅助 info、`info.txt`）
> 在 [上层 README 第 2、3 节](../README.md) 有完整说明与实跑节选。

复现后典型目录形如：

```
fault-data/
├── collect/asys_output_<ts>/
│   ├── dfx/log/host/cann/{debug,run}/plog/      # Host 侧 CANN 日志
│   ├── dfx/atrace/                              # 调度 trace + stackcore
│   └── {hardware,software,status}_info.txt、health_result.txt
├── launch/asys_output_<ts>/
│   ├── dfx/log/host/screen.txt、user_cmd        # 业务报错 + 可复现命令
│   ├── dfx/log/host/cann/{debug,run}/...        # 含 AI Core Error 报错行
│   └── dfx/data-dump/                           # 异常 Dump（launch 开启）
└── analyze/info_<ts>/.../info.txt               # AI Core Error 解析结果
```
