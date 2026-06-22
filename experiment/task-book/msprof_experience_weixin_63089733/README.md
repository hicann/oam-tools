# msprof 性能工具体验 - weixin_63089733

本目录是 GitCode 任务书 `#129` 的交付件，使用 asc-devkit 中的 Ascend C `MatmulLeakyRelu` 算子，通过 `msprof op simulator` 进行 Matmul 算子性能采集尝试，并记录完整复现过程、校验结果和问题反馈。

## 目录结构

```text
msprof_experience_weixin_63089733/
├── README.md
├── app/
│   ├── CMakeLists.txt
│   ├── data_utils.h
│   ├── matmul_leakyrelu.asc
│   └── scripts/
│       ├── gen_data.py
│       └── verify_result.py
├── perf-data/
│   └── 20260615_matmul_simulator/
│       ├── environment.txt
│       ├── matmul_simulator_msprof.log
│       ├── result_summary.md
│       └── verification.txt
└── run.sh
```

## 负载说明

- 算子: `MatmulLeakyRelu`
- Kernel: `matmul_leakyrelu_custom`
- Shape: `A[1024,256] fp16`、`B[256,640] fp16`、`bias[640] fp32`、`C[1024,640] fp32`
- 数据: A/B 全 1，bias 全 0，因此 golden 输出全为 `256.0`
- 正确性: `655360` 个 float32 输出全部通过，`max_abs=0.0`

## 复现命令

```bash
bash run.sh simulator
```

如需上板采集:

```bash
bash run.sh board
```

可通过 `CANN_SET_ENV=/path/to/set_env.sh` 指定 CANN 环境脚本，通过 `SOC_VERSION=Ascend910B1` 指定仿真型号。

## 实测环境

- CANN: 9.1.0, `V100R001C11B094`
- 工具链: CMake 3.16.3, g++ 9.4.0, CANN bisheng
- 当前 workspace 未暴露 `/dev/davinci*`，`npu-smi` 不可用
- 因无真实板卡访问，上板 `msprof op` 报 `Device profiling is not supported on current chip`

## 本次结果

`msprof op simulator --soc-version=Ascend910B1 --dump=on` 能完整执行 MatmulLeakyRelu kernel:

- `SIM_RC=0`
- `Model RUN TIME: 179138 ms`
- `Total tick: 335395`
- 输出校验通过: `checked=655360, bad=0, max_abs=0.0`

但当前环境下 msprof 自动解析阶段失败，未生成 `PipeUtilization.csv` / `trace.json` 等解析文件。关键错误见 `perf-data/20260615_matmul_simulator/result_summary.md` 和完整日志。

## 问题与建议

- `msprof op simulator` 在解析失败时仍返回 0，建议对解析失败提供非 0 返回码或更明确的状态文件。
- 仿真运行过程中会产生 tmp_dump，但解析失败后目录被清空；建议提供参数保留失败现场，便于用户反馈。
- `GetOutputPathFromRemote failed` 缺少可操作说明，建议文档补充 socket/权限/环境变量排查路径。
- `MSOPPROF_EXE_PATH` 需要设置为 `$ASCEND_HOME_PATH/tools/msopprof` 才能找到 `kernel-launcher`，建议在工具报错中提示期望路径格式。

## 验收说明

- 已完成 Matmul 算子编译、仿真执行和正确性校验。
- 已保留 msprof 仿真日志和问题记录。
- 受当前环境限制，未获得解析后的完整性能 CSV；该问题已如实记录。
