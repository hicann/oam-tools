/*
 * Copyright (c) 2025 Huawei Technologies Co., Ltd.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/*
 * AscendC 故障注入 kernel —— 故意制造越界 GM 访问，触发 AI Core Error。
 *
 * 正常的 element-wise Add（参考 msprof demo 的 02_api_AscendC）每核处理
 * BLOCK_LENGTH 个元素。这里在 CopyOut 时把写回地址人为偏移到
 * 远超 z 实际分配长度的位置（OOB_OFFSET），让 DataCopy 写到非法 GM 地址，
 * AI Core 在执行该指令时报异常（Dump exception / AIC_INFO），
 * 正是 asys analyze -r=aicore_error 要定位的故障类型。
 *
 * ★ 这是“故障注入”用途，不是正常算子。它的存在就是为了在 NPU 上
 *   稳定跑出一个 AI Core Error，供 asys launch 复跑 + analyze 解析。
 */
#include "kernel_operator.h"
using namespace AscendC;

constexpr int32_t TOTAL_LENGTH = 8192;
constexpr int32_t USE_CORE_NUM = 8;
constexpr int32_t BLOCK_LENGTH = TOTAL_LENGTH / USE_CORE_NUM;
constexpr int32_t TILE_NUM = 8;
constexpr int32_t BUFFER_NUM = 2;
constexpr int32_t TILE_LENGTH = BLOCK_LENGTH / TILE_NUM / BUFFER_NUM;

// ★ 故障注入点：把写回偏移推到远超 z 分配范围（z 仅 TOTAL_LENGTH 个元素），
//   2^20 个 half 的偏移必然越界，AI Core 写该地址时触发异常。
constexpr int64_t OOB_OFFSET = 1 << 20;

class KernelDirty {
public:
    __aicore__ inline KernelDirty() {}
    __aicore__ inline void Init(GM_ADDR x, GM_ADDR y, GM_ADDR z)
    {
        xGm.SetGlobalBuffer((__gm__ half *)x + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        yGm.SetGlobalBuffer((__gm__ half *)y + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        // ★ z 的 GlobalBuffer 起始地址人为加上 OOB_OFFSET，使后续写回越界
        zGm.SetGlobalBuffer((__gm__ half *)z + OOB_OFFSET + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        pipe.InitBuffer(inQueueX, BUFFER_NUM, TILE_LENGTH * sizeof(half));
        pipe.InitBuffer(inQueueY, BUFFER_NUM, TILE_LENGTH * sizeof(half));
        pipe.InitBuffer(outQueueZ, BUFFER_NUM, TILE_LENGTH * sizeof(half));
    }
    __aicore__ inline void Process()
    {
        int32_t loopCount = TILE_NUM * BUFFER_NUM;
        for (int32_t i = 0; i < loopCount; i++) {
            CopyIn(i);
            Compute(i);
            CopyOut(i);
        }
    }
private:
    __aicore__ inline void CopyIn(int32_t progress)
    {
        LocalTensor<half> xLocal = inQueueX.AllocTensor<half>();
        LocalTensor<half> yLocal = inQueueY.AllocTensor<half>();
        DataCopy(xLocal, xGm[progress * TILE_LENGTH], TILE_LENGTH);
        DataCopy(yLocal, yGm[progress * TILE_LENGTH], TILE_LENGTH);
        inQueueX.EnQue(xLocal);
        inQueueY.EnQue(yLocal);
    }
    __aicore__ inline void Compute(int32_t progress)
    {
        LocalTensor<half> xLocal = inQueueX.DeQue<half>();
        LocalTensor<half> yLocal = inQueueY.DeQue<half>();
        LocalTensor<half> zLocal = outQueueZ.AllocTensor<half>();
        Add(zLocal, xLocal, yLocal, TILE_LENGTH);
        outQueueZ.EnQue<half>(zLocal);
        inQueueX.FreeTensor(xLocal);
        inQueueY.FreeTensor(yLocal);
    }
    __aicore__ inline void CopyOut(int32_t progress)
    {
        LocalTensor<half> zLocal = outQueueZ.DeQue<half>();
        // ★ 写回越界地址 → AI Core Error
        DataCopy(zGm[progress * TILE_LENGTH], zLocal, TILE_LENGTH);
        outQueueZ.FreeTensor(zLocal);
    }
    TPipe pipe;
    TQue<QuePosition::VECIN, BUFFER_NUM> inQueueX, inQueueY;
    TQue<QuePosition::VECOUT, BUFFER_NUM> outQueueZ;
    GlobalTensor<half> xGm, yGm, zGm;
};

extern "C" __global__ __aicore__ void dirty_custom(GM_ADDR x, GM_ADDR y, GM_ADDR z)
{
    KernelDirty op;
    op.Init(x, y, z);
    op.Process();
}
