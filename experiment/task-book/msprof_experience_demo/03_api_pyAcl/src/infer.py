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

"""03_api_pyAcl —— pyACL（Python 版 ACL）加载 .om 离线模型推理 + msprof 采集。

完整链路：export_onnx.py（TinyMLP→ONNX）→ atc（ONNX→.om）→ 本脚本（pyACL 推理）。
与 01/04 同一个 TinyMLP（4 层 Linear+GELU，输入 [32,1024]），方便横向对比。

pyACL 是 CANN 面向离线部署的推理接口，调用顺序：
  init → set_device → create_context → load_om → create_desc
  → 准备 input/output dataset → execute（msprof 在此采集）→ unload → 清理

用法：
    ASCEND_VISIBLE_DEVICES=7 python3 infer.py [model.om 路径]
"""
import logging
import sys

import acl
import numpy as np

logger = logging.getLogger(__name__)

DEVICE_ID = 0  # ASCEND_VISIBLE_DEVICES 已做映射
ACL_MEM_MALLOC_HUGE_FIRST = 0
ACL_MEMCPY_HOST_TO_DEVICE = 1
ACL_MEMCPY_DEVICE_TO_HOST = 2
NPY_FLOAT32 = 11


def _check(ret, msg):
    if ret != 0:
        raise RuntimeError(f"{msg} failed: {ret}")


def main():
    om_path = sys.argv[1] if len(sys.argv) > 1 else "model_build/tiny_mlp.om"

    # 1~3. 初始化 + device + context
    _check(acl.init(), "acl.init")
    _check(acl.rt.set_device(DEVICE_ID), "set_device")
    context, ret = acl.rt.create_context(DEVICE_ID)
    _check(ret, "create_context")
    logger.info("[pyacl] init ok, device=%s", DEVICE_ID)

    # 4. 加载 .om 模型
    model_id, ret = acl.mdl.load_from_file(om_path)
    _check(ret, f"load_from_file({om_path})")
    model_desc = acl.mdl.create_desc()
    _check(acl.mdl.get_desc(model_desc, model_id), "get_desc")
    logger.info("[pyacl] model loaded, id=%s", model_id)

    # 5. 准备输入：host 数据 → device，组装成 input dataset
    x = np.ones((32, 1024), dtype=np.float32)
    x_bytes = x.tobytes()
    in_size = len(x_bytes)
    in_dev, ret = acl.rt.malloc(in_size, ACL_MEM_MALLOC_HUGE_FIRST)
    _check(ret, "malloc input")
    x_ptr = acl.util.bytes_to_ptr(x_bytes)
    _check(acl.rt.memcpy(in_dev, in_size, x_ptr, in_size, ACL_MEMCPY_HOST_TO_DEVICE),
           "memcpy H2D")
    in_ds = acl.mdl.create_dataset()
    in_buf = acl.create_data_buffer(in_dev, in_size)
    acl.mdl.add_dataset_buffer(in_ds, in_buf)

    # 6. 准备输出：按 model_desc 查询输出大小，分配 device 内存
    out_size = acl.mdl.get_output_size_by_index(model_desc, 0)
    out_dev, ret = acl.rt.malloc(out_size, ACL_MEM_MALLOC_HUGE_FIRST)
    _check(ret, "malloc output")
    out_ds = acl.mdl.create_dataset()
    out_buf = acl.create_data_buffer(out_dev, out_size)
    acl.mdl.add_dataset_buffer(out_ds, out_buf)

    # 7. 执行推理 ×20（warmup 3 + 测量 17），msprof 在此采集算子
    for _ in range(20):
        _check(acl.mdl.execute(model_id, in_ds, out_ds), "execute")
    logger.info("[pyacl] inference x20 done")

    # 8. 拷回输出校验（acl 标准做法：malloc_host → memcpy → ptr_to_bytes）
    out_host_ptr, ret = acl.rt.malloc_host(out_size)
    _check(ret, "malloc_host")
    _check(acl.rt.memcpy(out_host_ptr, out_size, out_dev, out_size, ACL_MEMCPY_DEVICE_TO_HOST),
           "memcpy D2H")
    out_bytes = acl.util.ptr_to_bytes(out_host_ptr, out_size)
    out_host = np.frombuffer(out_bytes, dtype=np.float32)
    logger.info("[pyacl] output[:3]=%s, shape_elems=%s", out_host[:3], out_host.size)
    acl.rt.free_host(out_host_ptr)

    # 9. 清理（逆序）
    acl.mdl.destroy_dataset(in_ds)
    acl.mdl.destroy_dataset(out_ds)
    acl.rt.free(in_dev)
    acl.rt.free(out_dev)
    acl.mdl.destroy_desc(model_desc)
    acl.mdl.unload(model_id)
    acl.rt.destroy_context(context)
    acl.rt.reset_device(DEVICE_ID)
    acl.finalize()
    logger.info("[pyacl] 资源已释放，全链路跑通")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
