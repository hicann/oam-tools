# 04_pyTorch —— torch_npu.profiler API 采集

> **本环境运行状态：已实跑。** 按下方步骤跑 `run.sh` 即可在本地生成性能数据。

## 这种方式是什么

在代码里用 `torch_npu.profiler.profile` **插桩**，白盒采集。
相比 CLI（01），API 能精确圈定第 N~M step、拿到 aten op 级耗时、Python 调用栈，
并额外产出 CLI 没有的 **`step_trace_time.csv`**（每 step Computing/Free 占比）。

## 文件

| 文件 | 作用 |
|---|---|
| `src/model_with_profiler.py` | 同一个 TinyMLP + profiler 插桩 |
| `run.sh` | 采集脚本，跑完打印 kernel Top + step 拆分 |

## 跑

```bash
bash run.sh        # 默认 device 7
```

## 如何用到你的模型

1. 替换 `src/model_with_profiler.py` 里的 `build_model()` 和输入 `x`（均标了 ← 注释）。
2. 训练循环则把 `forward + backward + optimizer.step()` 放进 `with prof:` 块内，
   每 step 末尾调 `prof.step()`，用 `schedule(wait/warmup/active)` 圈定要采的 step。
3. 采集配置不用动，直接 `bash run.sh 7`。

## 实测结果（910B3 上的示例输出）

> 换成你的模型后，重点看 `step_trace_time.csv` 的 Computing:Free——它告诉你
> 是算力不够（Computing 高）还是 host 下发拖后腿（Free 高）。

算子聚合（`op_statistic.csv`）—— 与 CLI 高度一致，验证两种方式自洽：

| OP Type | Core Type | Count | Total(us) | Ratio | CLI 对照 |
|---|---|---:|---:|---:|---:|
| MatMulV2 | AI_CORE | 20 | 136.50 | **78.30%** | 77.88% |
| Gelu | AI_VECTOR_CORE | 15 | 37.82 | 21.70% | 21.45% |

**step 拆分（`step_trace_time.csv`，API 独有）**：

| Step | Computing(us) | Free(us) | 解读 |
|---:|---:|---:|---|
| 3 | 35.64 | 2214.72 | Computing : Free ≈ 1 : 62 |
| 5 | 34.40 | 2113.74 | ≈ 1 : 61 |
| 7 | 35.52 | 1384.98 | ≈ 1 : 39 |

**关键洞察**：NPU 实际计算每 step 仅 ~35us，但 Free（等待 host 下发）高达 ~2000us，
是典型的 **host bound**——TinyMLP 太小，host 下发开销完全盖过了计算。
这正是 API 模式相对 CLI 的价值：CLI 只告诉你「MatMul 占 78%」，
API 进一步告诉你「整个 step 99% 时间在等 host」。

## host 下发 Top（`api_statistic.csv`）

| API Name | Time(us) | Count | Avg(us) |
|---|---:|---:|---:|
| aclnnAddmm | 259.56 | 20 | 12.98 |
| aclrtLaunchKernelWithHostArgs | 229.12 | 35 | 6.55 |
| aclnnGelu | 200.51 | 15 | 13.37 |
