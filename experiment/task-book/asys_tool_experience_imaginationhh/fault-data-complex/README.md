# fault-data-complex 说明（案例2：复杂故障）

存放复杂故障算子 `app_complex/complex_op` 的 asys 采集/解析产物。故障设计与工具评测见
[上层 README 第 4 节](../README.md)、[feedback.md 第 7 节](../feedback.md)。

| 子目录 | 来源命令 | 内容 |
|---|---|---|
| `launch/` | `asys launch --task .../complex_op` | 复跑两算子流水，故障现场：plog 含 `fault kernel_name=gather_bad_custom_1`、后半 4 核报错 |
| `analyze/` | `asys analyze -r=aicore_error --path <launch输出>` | 解析结果 info.txt（容器内 dump 未落盘，报 dump 缺失，详见评测） |

> **原始数据未入库**（同 `fault-data/` 处理）：产物体积大、含环境相关历史信息，
> 可由 `bash app_complex/build.sh` + launch/analyze 复现，复现步骤见上层 README「复现步骤」第 5 步。
> README 第 4.2/4.3 节的 plog 报错行、info.txt 内容均为本次实跑结果原文。
