# msprof 性能采集实操 Demo

一套 msprof 上手示例,演示昇腾 NPU 上四种性能数据采集方式。用最简
**TinyMLP**(4 层 Linear + GELU,输入 `[32,1024]`)作负载,把 msprof 跑通、看懂输出;
真正使用时把负载换成你自己的模型即可(代码里标了 `← 换成你的模型`)。

## 四种方式

| # | 目录 | 方式 | 适用场景 |
|---|---|---|---|
| 01 | [01_cmdline](01_cmdline/README.md) | msprof 命令行(黑盒,不改代码) | 有个能跑的程序,想快速看一眼 |
| 02 | [02_api_AscendC](02_api_AscendC/README.md) | AscendC 自定义算子(核函数直调) | 写了算子,想看硬件利用率 |
| 03 | [03_api_pyAcl](03_api_pyAcl/README.md) | pyACL 加载 .om 离线模型 | 要部署离线模型 |
| 04 | [04_pyTorch](04_pyTorch/README.md) | torch_npu.profiler API | 在跑 PyTorch,想要 step 级数据 |

> 四种脚本都可实跑;运行后性能数据会落在各方式的输出目录,本仓库不附带实采数据。

## 目录结构

```
msprof_experience_demo/
├── README.md
├── 01_cmdline/          src/model.py + run.sh           命令行黑盒采集
├── 02_api_AscendC/      src/(add_kernel.cpp + main.cpp …) + build.sh + run.sh   算子编译+采集
├── 03_api_pyAcl/        src/(export_onnx.py + infer.py) + build_model.sh + run.sh   ONNX→om→推理
└── 04_pyTorch/          src/model_with_profiler.py + run.sh   profiler API 插桩
```

每个子目录都有自己的 README,讲清该方式的细节和「如何用到你的模型」。

## 环境

- Atlas A2 训练系列(910B3),CANN 9.1.0,torch_npu 2.7.1,Python 3.12
- 跑各方式前先 `source <CANN路径>/set_env.sh`(脚本会自动定位,找不到会提示)

## 怎么跑

```bash
cd 01_cmdline      && bash run.sh 7                       # 命令行
cd 02_api_AscendC  && bash build.sh && bash run.sh 7      # AscendC(先编译)
cd 03_api_pyAcl    && bash build_model.sh && bash run.sh 7 # pyACL(先转 om)
cd 04_pyTorch      && bash run.sh 7                        # PyTorch API
```

参数 `7` 是 device 号。脚本幂等:每次先清输出目录再重采,跑完打印 Top 算子。

## 预期输出

采集结果落在各方式 `run.sh` 指定的输出目录,核心是几个可读文件:

| 文件 | 内容 |
|---|---|
| `op_statistic.csv` | 算子耗时占比(谁是热点) |
| `op_summary_*.csv` | 单算子 + AI Core 硬件指标(卡在哪个计算单元) |
| `step_trace_time.csv` | 每 step「计算 vs 等待」拆分(仅 PyTorch API) |
| `trace_view.json` | 时间线,可拖进 chrome://tracing |

本示例 TinyMLP 的实测:**MatMulV2 占 ~78%**(主热点);step_trace 显示每步「等待」是「计算」的约 60 倍,说明模型太小、瓶颈在 host 下发。各方式的 README 有更详细的看数说明。
