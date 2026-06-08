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
 * AscendC 复杂故障注入 kernel —— 模拟真实训练中更隐蔽的 AI Core Error。
 *
 * 相比简单版(固定写越界、全核失败)，这里刻意做三件事提升定位难度：
 *   1) 多算子流水：先跑正常 Add(成功)，再跑有问题的 gather(失败)，
 *      考验 analyze 能否准确指出是【第二个】算子出错，而非笼统报错。
 *   2) 条件性故障：仅当 blockIdx >= HALF_CORE 时才注入越界，
 *      模拟"部分 AI Core 失败、另一半正常"的真实现象。
 *   3) 读越界(gather/embedding 索引越界)：偏移在运行时按 block 计算，
 *      比固定写越界更接近真实 indexing bug，也更难一眼看出。
 *
 * ★ 故障注入用途，非正常算子。
 */
#include "kernel_operator.h"
using namespace AscendC;

constexpr int32_t TOTAL_LENGTH = 8192;
constexpr int32_t USE_CORE_NUM = 8;
constexpr int32_t HALF_CORE = USE_CORE_NUM / 2;       // 前 4 核正常，后 4 核故障
constexpr int32_t BLOCK_LENGTH = TOTAL_LENGTH / USE_CORE_NUM;
constexpr int32_t TILE_NUM = 8;
constexpr int32_t BUFFER_NUM = 2;
constexpr int32_t TILE_LENGTH = BLOCK_LENGTH / TILE_NUM / BUFFER_NUM;

// ★ 越界步长：后半核每核把读取基址按 (blockIdx) 倍数推到分配区之外，
//   模拟 gather 索引随 token/行号增大而溢出的真实场景。
constexpr int64_t OOB_STRIDE = 1 << 18;

// ---- 算子1：正常的 element-wise Add（应当成功）----
class KernelAddOk {
public:
    __aicore__ inline void Init(GM_ADDR x, GM_ADDR y, GM_ADDR z)
    {
        xGm.SetGlobalBuffer((__gm__ half *)x + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        yGm.SetGlobalBuffer((__gm__ half *)y + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        zGm.SetGlobalBuffer((__gm__ half *)z + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        pipe.InitBuffer(inQX, BUFFER_NUM, TILE_LENGTH * sizeof(half));
        pipe.InitBuffer(inQY, BUFFER_NUM, TILE_LENGTH * sizeof(half));
        pipe.InitBuffer(outQ, BUFFER_NUM, TILE_LENGTH * sizeof(half));
    }
    __aicore__ inline void Process()
    {
        for (int32_t i = 0; i < TILE_NUM * BUFFER_NUM; i++) {
            LocalTensor<half> xL = inQX.AllocTensor<half>();
            LocalTensor<half> yL = inQY.AllocTensor<half>();
            DataCopy(xL, xGm[i * TILE_LENGTH], TILE_LENGTH);
            DataCopy(yL, yGm[i * TILE_LENGTH], TILE_LENGTH);
            inQX.EnQue(xL); inQY.EnQue(yL);
            xL = inQX.DeQue<half>(); yL = inQY.DeQue<half>();
            LocalTensor<half> zL = outQ.AllocTensor<half>();
            Add(zL, xL, yL, TILE_LENGTH);
            outQ.EnQue<half>(zL);
            inQX.FreeTensor(xL); inQY.FreeTensor(yL);
            zL = outQ.DeQue<half>();
            DataCopy(zGm[i * TILE_LENGTH], zL, TILE_LENGTH);
            outQ.FreeTensor(zL);
        }
    }
private:
    TPipe pipe;
    TQue<QuePosition::VECIN, BUFFER_NUM> inQX, inQY;
    TQue<QuePosition::VECOUT, BUFFER_NUM> outQ;
    GlobalTensor<half> xGm, yGm, zGm;
};

// ---- 算子2：有问题的 gather（后半核读越界，应当失败）----
class KernelGatherBad {
public:
    __aicore__ inline void Init(GM_ADDR src, GM_ADDR dst)
    {
        int64_t base = BLOCK_LENGTH * GetBlockIdx();
        // ★ 故障注入点：后半核把读取基址按 blockIdx 推到 src 分配区之外
        if (GetBlockIdx() >= HALF_CORE) {
            base += OOB_STRIDE * GetBlockIdx();   // 读越界，模拟索引溢出
        }
        srcGm.SetGlobalBuffer((__gm__ half *)src + base, BLOCK_LENGTH);
        dstGm.SetGlobalBuffer((__gm__ half *)dst + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
        pipe.InitBuffer(inQ, BUFFER_NUM, TILE_LENGTH * sizeof(half));
        pipe.InitBuffer(outQ, BUFFER_NUM, TILE_LENGTH * sizeof(half));
    }
    __aicore__ inline void Process()
    {
        for (int32_t i = 0; i < TILE_NUM * BUFFER_NUM; i++) {
            LocalTensor<half> sL = inQ.AllocTensor<half>();
            DataCopy(sL, srcGm[i * TILE_LENGTH], TILE_LENGTH);   // ★ 后半核在此读非法地址
            inQ.EnQue(sL);
            sL = inQ.DeQue<half>();
            LocalTensor<half> dL = outQ.AllocTensor<half>();
            DataCopy(dL, sL, TILE_LENGTH);
            outQ.EnQue<half>(dL);
            inQ.FreeTensor(sL);
            dL = outQ.DeQue<half>();
            DataCopy(dstGm[i * TILE_LENGTH], dL, TILE_LENGTH);
            outQ.FreeTensor(dL);
        }
    }
private:
    TPipe pipe;
    TQue<QuePosition::VECIN, BUFFER_NUM> inQ;
    TQue<QuePosition::VECOUT, BUFFER_NUM> outQ;
    GlobalTensor<half> srcGm, dstGm;
};

extern "C" __global__ __aicore__ void add_ok_custom(GM_ADDR x, GM_ADDR y, GM_ADDR z)
{
    KernelAddOk op; op.Init(x, y, z); op.Process();
}

extern "C" __global__ __aicore__ void gather_bad_custom(GM_ADDR src, GM_ADDR dst)
{
    KernelGatherBad op; op.Init(src, dst); op.Process();
}
