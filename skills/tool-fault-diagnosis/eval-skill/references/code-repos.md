# CANN 相关代码仓库地址

> 本文档列出 Ascend NPU / CANN 生态相关的主要开源代码仓库，用于日志分析时溯源算子实现、查找 bug fix 或参考 API 定义。

## 华为官方仓库（GitCode）

| 仓库 | 地址 | 说明 |
|------|------|------|
| CANN Community | https://gitcode.com/cann/community | CANN 社区版入口，含 roadmap 和问题追踪 |
| MindSpore | https://gitcode.com/mindspore/mindspore | MindSpore 框架主仓，含 graph engine 代码 |
| MindSpeed | https://gitcode.com/Ascend/MindSpeed | 大模型训练加速库（基于 Megatron-LM） |
| PyTorch Adapter (torch_npu) | https://gitcode.com/Ascend/pytorch | PyTorch NPU 适配层，含算子注册和前端 |
| ModelZoo | https://gitcode.com/Ascend/modelzoo | 官方模型样例（含大量算子用法参考） |
| 算子库 (op-plugin) | https://gitcode.com/Ascend/op-plugin | torch_npu 算子插件，C++/Python 实现 |

## GitHub 镜像 / 社区仓库

| 仓库 | 地址 | 说明 |
|------|------|------|
| torch_npu (GitHub) | https://github.com/Ascend/pytorch | PyTorch NPU 适配（GitHub 镜像） |
| apex for Ascend | https://github.com/Ascend/apex | 混合精度训练工具适配 |
| DeepSpeed for Ascend | https://github.com/Ascend/DeepSpeed | DeepSpeed NPU 适配 |

## 代码定位技巧

### 根据算子名称查找源码

```bash
# 在 op-plugin 仓库中搜索算子实现
# 例如查找 MatMulV2
git clone https://gitcode.com/Ascend/op-plugin.git
grep -r "MatMulV2" op-plugin/op_plugin/ops/ --include="*.cpp" -l

# 查找 torch_npu 中的算子注册
grep -r "matmul" pytorch/torch_npu/csrc/ --include="*.cpp" -l
```

### 根据错误码查找处理逻辑

```bash
# 在 MindSpore 中搜索错误码定义
grep -r "ACL_ERROR_RT_MEMORY_ALLOCATION" mindspore/ --include="*.h" -l

# 在 CANN 头文件中查找
find /usr/local/Ascend/cann-8.5.0/ -name "*.h" | xargs grep -l "ACL_ERROR_"
```

### 查找 CANN 本地头文件

```bash
# CANN 安装后的头文件位置
ls /usr/local/Ascend/cann-8.5.0/include/

# ACL 错误码定义
cat /usr/local/Ascend/cann-8.5.0/include/acl/acl_base.h | grep "ACL_ERROR_"

# GE 相关接口
ls /usr/local/Ascend/cann-8.5.0/include/ge/
```

## 文档参考

| 文档 | 地址 |
|------|------|
| CANN 官方文档 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/overview |
| ACL API 参考 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/apiref/appdevgapi |
| HCCL API 参考 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/apiref/hcclapi |
| npu-smi 工具指南 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/devtools/npusmi |

## 版本对应关系

| torch_npu 版本 | PyTorch 版本 | CANN 版本 |
|--------------|------------|---------|
| 2.1.0 | 2.1.0 | 8.0.0 |
| 2.2.0 | 2.2.0 | 8.0.RC3 |
| 2.3.1 | 2.3.1 | 8.5.0 |

> 当前环境：CANN 8.5.0，建议使用 torch_npu 2.3.1。
