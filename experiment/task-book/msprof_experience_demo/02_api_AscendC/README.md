# 02_api_AscendC —— AscendC 自定义算子 + msprof 采集

> **本环境运行状态：✅ 已实跑。** 按下方步骤跑 `build.sh` + `run.sh` 即可在本地生成性能数据。

## 这种方式采什么

手写一个 AscendC kernel（昇腾的算子开发语言），msprof 采集它在 AI Core 上的
**vector/cube 利用率、MTE 搬运占比、scalar 占比**，判断算子卡在哪个 pipe。
本 demo 用最小可跑单元——**核函数直调（Kernel Launch）**，负载是两个长度 8192 的
fp16 向量逐元素相加。

## 文件

| 文件 | 作用 |
|---|---|
| `src/add_kernel.cpp` | device 侧 AscendC kernel（CopyIn→Add→CopyOut） |
| `src/main.cpp` | host 侧：分配显存、拉起 kernel、拷回校验 |
| `src/CMakeLists.txt` | 用官方 `ascendc_library` 编译 |
| `build.sh` | 一键编译 → `build_run/add_custom_op` |
| `run.sh` | msprof 采集脚本 |

## 跑

```bash
bash build.sh        # 编译
bash run.sh 7        # msprof 采集（默认 device 7）
```

## 如何用到你的算子

改 `src/add_kernel.cpp` 的 `Compute()` 计算逻辑、`src/main.cpp` 的输入输出与 kernel 名、
`src/CMakeLists.txt` 的源文件，然后 `bash build.sh && bash run.sh 7`。

## 预期结果（910B3 示例）

单算子 PMU（`op_summary`，逐元素 Add 的典型画像）：

| PMU 指标 | 值 | 解读 |
|---|---:|---|
| `aiv_vec_ratio` | ~0.04 | vector 计算只占 4%——数据太少，算得太快 |
| `aiv_scalar_ratio` | ~0.65 | **标量指令占主导**（地址计算/循环控制） |
| `aiv_mte2_ratio` | ~0.33 | 从 GM 搬入占 1/3 |
| `cube_utilization(%)` | 0 | element-wise 不用 cube，符合预期 |

**核心洞察**：Add 这种 element-wise 算子是 **scalar/搬运 bound**，真正 vector 计算只占 4%。
与 MatMul（cube bound，cube_utilization 60%+）形成对比——这正是 msprof 采 AscendC 算子的价值。
