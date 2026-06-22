# MatmulLeakyRelu msprof 结果摘要

- `msprof op simulator` 返回码: 0
- 仿真模型运行时间: 179138 ms
- Total tick: 335395
- 正确性: `checked=655360, bad=0, max_abs=0.0`
- 原始日志: `matmul_simulator_msprof.log`

## 采集异常

当前环境没有可见真实 NPU 设备，`msprof op` 上板采集返回 `Device profiling is not supported on current chip`。

仿真方式能够完成 kernel 执行并生成输出，但 msprof 解析阶段报错:

```text
[ERROR] <GetOutputPathFromRemote> GetOutputPathFromRemote failed. send msg to server error ret=0
[WARN]  Profiling results are empty. No kernel profiling data was generated. Please check the dump output.
[ERROR] Profiling data parse failed. Please check
```

因此本次交付保留了完整复现脚本、完整 msprof 仿真日志和正确性校验结果；解析后的 `PipeUtilization.csv` / `trace.json` 未能在当前沙箱环境生成。
