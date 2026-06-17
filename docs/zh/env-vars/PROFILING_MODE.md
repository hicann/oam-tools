# PROFILING\_MODE

## 功能描述

是否开启Profiling采集功能。

- true：开启Profiling功能，从PROFILING\_OPTIONS读取Profiling的采集选项。
- false或者不配置：关闭Profiling功能。
- dynamic：动态采集性能数据时（attach方式），需在训练任务执行前配置该参数。

## 配置示例

```sh
export PROFILING_MODE=true
```

## 使用约束

- 此环境变量仅适用于TensorFlow训练和在线推理场景。
- 通过AscendCL接口或者TF Adapter接口参数“profiling\_mode”开启Profiling功能的优先级高于该环境变量优先级（PROFILING\_MODE=dynamic时除外）。

## 支持的型号

<!-- npu="910" id1 -->
Atlas 训练系列产品
<!-- end id1 -->
<!-- npu="310p" id2 -->
Atlas 推理系列产品
<!-- end id2 -->
<!-- npu="910b" id3 -->
Atlas A2 训练系列产品/Atlas A2 推理系列产品
<!-- end id3 -->
<!-- npu="A3" id4 -->
Atlas A3 训练系列产品/Atlas A3 推理系列产品
<!-- end id4 -->
<!-- npu="950" id5 -->
Ascend 950PR/Ascend 950DT
<!-- end id5 -->
