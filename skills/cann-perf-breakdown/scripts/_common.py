#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
"""perf-breakdown 脚本共享工具函数。

各脚本以 `python scripts/<name>.py` 形式从 skill 根目录调用，scripts 目录位于
sys.path[0]，故可直接 `from _common import ...`。
"""
import json
from pathlib import Path


def validate_file_exists(filepath: str) -> Path:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    return path


def load_json(filepath: Path) -> dict:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {filepath}: {e}") from e


# 始终必填 shape_semantic 的算子（被 check_op_coverage / check_structure /
# regression_check 共用，避免三处重复定义）。
SHAPE_SEMANTIC_ALWAYS_REQUIRED = {
    'MatMul', 'MatMulV2', 'QuantBatchMatmulV3', 'GroupedMatmul', 'GemmEx', 'BatchMatMul',
    'FlashAttentionScore', 'FusedInferAttentionScore', 'KvQuantSparseFlashAttention',
    'HcomAllGather', 'HcomReduceScatter', 'HcomAllToAll', 'hcom_allReduce', 'HcomAllReduce',
    'RmsNorm', 'LayerNormV3', 'InplaceAddRmsNorm', 'AddRmsNormDynamicQuant',
    'MlaPrologV3', 'DequantSwigluQuant', 'LightningIndexerQuant', 'MoeGatingTopKHash',
    'RotaryMul',
    'GatherV2', 'GatherV3',
    'MoeDistributeDispatchV2', 'MoeDistributeCombineV2',
}


def is_shape_always_required(name: str) -> bool:
    """算子是否始终必填 shape_semantic（含 AddRmsNorm 前缀系列）。"""
    return name in SHAPE_SEMANTIC_ALWAYS_REQUIRED or name.startswith('AddRmsNorm')

