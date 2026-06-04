# 01_cmdline —— msprof 命令行（CLI）采集

> **本环境运行状态：已实跑可复现。** 按下方步骤跑 `run.sh` 即可在本地生成性能数据。

## 这种方式是什么

msprof 作为父进程**拉起**你的应用，全程旁路采集，**不改一行模型代码**。
适合：拿到一个能跑的黑盒应用，想快速看一眼性能。

## 文件

| 文件 | 作用 |
|---|---|
| `src/model.py` | 最简 TinyMLP（4 层 Linear+GELU，输入 [32,1024]） |
| `run.sh` | msprof CLI 采集脚本，跑完自动打印 Top 算子 |

## 跑

```bash
bash run.sh        # 默认 device 7
bash run.sh 5      # 指定卡号
```

## 如何用到你的模型

零侵入：把 `run.sh` 最后一行的 `python3 "$HERE/src/model.py"` 换成你自己的启动命令
（任何在 NPU 上有真实计算的程序都行），其余 msprof 参数不动。

## 预期结果（910B3 示例）

算子耗时 Top（`op_statistic_*.csv`）：

| OP Type | Core Type | Count | Total(us) | Ratio |
|---|---|---:|---:|---:|
| MatMulV2 | AI_CORE | 92 | 645.76 | **77.88%** |
| Gelu | AI_VECTOR_CORE | 69 | 177.88 | 21.45% |
| DSARandomNormal | DSA_SQE | 1 | 5.58 | 0.67% |

MatMul 占主导，符合全连接网络预期。`op_summary_*.csv` 含完整 AI Core PMU，可定位单算子瓶颈。
