# msprof 性能分析工具体验 —— imaginationhh

本目录是 **msprof 性能分析工具体验任务**的交付件,演示在昇腾 NPU 上用
**PyTorch API**(`torch_npu.profiler`)方式采集性能数据,并对采集结果做解读。

- 负载:最简 **TinyMLP**(4 层 Linear + GELU,输入 `[32, 1024]`)
- 实测环境:Atlas A2 训练系列(910B3),CANN 9.1.0,torch_npu 2.7.1,Python 3.12
- 采集时间:2026-06-01

## 目录结构

```
msprof_tool_experience_imaginationhh/
├── README.md            本说明(目录结构 / 输入输出 / 验收标准)
├── app/                 应用与模型
│   └── model_with_profiler.py  TinyMLP + torch_npu.profiler 插桩(PyTorch API 方式)
├── perf-data/           性能数据(PyTorch API 方式实采产物,见下方说明)
│   └── *_ascend_pt/
│       ├── ASCEND_PROFILER_OUTPUT/   torch 风格汇总(用户主要看这里)
│       └── PROF_*/mindstudio_profiler_output/  底层 msprof 原生输出(含完整 PMU)
└── pytorch_run.sh       PyTorch API 方式采集脚本 —— 代码内插桩
```

## 怎么跑

```bash
bash pytorch_run.sh    # PyTorch API 方式(默认自动探测第一张可用 NPU)
# 也可显式指定卡号:bash pytorch_run.sh 7
```

> 跑前先 `source <CANN路径>/set_env.sh`。脚本默认自动探测第一张可用 NPU
> (`/dev/davinci*`),单卡环境无需关心卡号是 0 还是 7。

## 输入输出说明

### 输入

- **模型**:TinyMLP —— 4 层 `Linear(1024,1024)` 之间夹 3 个 `GELU`,纯全连接网络。
- **输入 shape**:`[32, 1024]`(batch=32,hidden=1024),`float32`。
- **采集参数配置**(PyTorch API,`model_with_profiler.py`):`ProfilerLevel.Level1` +
  `AiCMetrics.PipeUtilization`,`schedule(wait=0, warmup=3, active=5, repeat=1)`,
  开启 `record_shapes` / `with_stack`。

### 输出(perf-data/ 下各文件看什么)

PyTorch profiler 产出**双层**结构:`ASCEND_PROFILER_OUTPUT/` 是 torch 用户直接看的汇总;
底层 `PROF_*/mindstudio_profiler_output/` 才是 msprof 原生输出(含完整 PMU 的 op_summary)。

| 文件 | 内容 |
|---|---|
| `ASCEND_PROFILER_OUTPUT/op_statistic.csv` | 算子按类型聚合,看耗时占比(谁是热点) |
| `ASCEND_PROFILER_OUTPUT/kernel_details.csv` | kernel 级明细 |
| `ASCEND_PROFILER_OUTPUT/operator_details.csv` | aten op 级耗时(API 方式独有) |
| `ASCEND_PROFILER_OUTPUT/api_statistic.csv` | host 端 API 下发统计 |
| `ASCEND_PROFILER_OUTPUT/step_trace_time.csv` | **每 step「计算 vs 等待」拆分(API 独有)** |
| `ASCEND_PROFILER_OUTPUT/trace_view.json` | timeline,拖进 Perfetto UI / chrome://tracing |
| `PROF_*/.../op_summary_*.csv` | 单算子明细 + **完整 AI Core PMU**(cube/vector/搬运占比) |
| `PROF_*/.../op_statistic_*.csv` 等 | msprof 原生聚合 / 调度 / timeline |
| `profiler_info.json` / `profiler_metadata.json` | 采集环境与配置元信息 |

### 实测结论(从本目录数据提取)

- **算子耗时**:`MatMulV2` 占 **78.30%**(主热点),`Gelu` 占 21.70%。4 层 Linear×5 active step
  = 20 个 MatMul,符合全连接网络预期。
- **AI Core PMU**(`op_summary`):MatMulV2 `cube_utilization ≈ 65.24%`、`aic_mac_ratio ≈ 0.276`;
  Gelu 走 vector(`aiv_vec_ratio ≈ 0.164`)。
- **step 拆分**(`step_trace_time.csv`):每步「等待」约为「计算」的 60 倍 —— 模型太小,
  瓶颈在 host 下发而非算力,典型的小负载特征。

## 验收标准

- [x] 成功完成 PyTorch API 方式采集性能数据 —— `pytorch_run.sh`,实采数据见 `perf-data/`。
- [ ] (扩展)命令行(CLI)方式采集 —— 本目录未包含。
- [ ] (扩展)AscendC 自定义算子采集 —— 本目录未包含。
- [ ] (扩展)pyACL 离线模型采集 —— 本目录未包含。

> timeline 查看:Chrome 打开 <https://ui.perfetto.dev/>,将 `trace_view.json` 拖入即可
> (快捷键 w 放大 / s 缩小 / a 左移 / d 右移)。
