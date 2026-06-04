# 03_api_pyAcl —— pyACL 加载 .om 离线模型推理 + msprof 采集

> **本环境运行状态：✅ 已实跑（全链路）。** 按下方步骤跑 `build_model.sh` + `run.sh` 即可在本地生成性能数据。

## 这种方式采什么

pyACL 是 CANN 的 Python 推理接口，面向**离线模型（.om）部署**场景：
模型先用 ATC 从 ONNX 转成 .om，再用 `acl.mdl.execute` 推理。
这里用与 01/04 相同的 TinyMLP，走 ONNX → .om 转换链后用 pyACL 推理。

## 文件

| 文件 | 作用 |
|---|---|
| `src/export_onnx.py` | TinyMLP → `tiny_mlp.onnx` |
| `build_model.sh` | 一键：导出 ONNX + ATC 转 `.om` |
| `src/infer.py` | pyACL 全链路：加载→推理×20→拷回→清理 |
| `run.sh` | msprof 采集脚本 |

## 跑

```bash
bash build_model.sh   # 生成 model_build/tiny_mlp.om
bash run.sh 7         # msprof 采集（默认 device 7）
```

## 如何用到你的模型

替换 `src/export_onnx.py` 的模型与输入（或直接拿已有 ONNX 改 `build_model.sh` 的 atc 命令），
改 `src/infer.py` 的输入 shape，然后 `bash build_model.sh && bash run.sh 7`。

## 预期结果（910B3 示例）

算子聚合（`op_statistic`）—— **与 01/04 对比出现关键差异**：

| OP Type | Core Type | Count | Total(us) | Ratio | 01/04 对照 |
|---|---|---:|---:|---:|---:|
| MatMulV2 | AI_CORE | 80 | 361.18 | 42.0% | 77.88% |
| Gelu | AI_VECTOR_CORE | 60 | 252.9 | 29.4% | 21.45% |
| **Cast** | AI_VECTOR_CORE | 40 | 245.68 | **28.6%** | **无** |

**核心洞察**：pyACL 路径凭空多出 **Cast 算子（占 28.6%）**，PyTorch 路径没有。
原因：ATC 转 .om 默认按 fp16 优化，而模型 IO 是 fp32，于是自动插入 fp32↔fp16 转换。
这是**离线部署相对框架推理的典型代价**——可在 ATC 阶段让 IO 也走 fp16 消掉这些 Cast。
