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
 * AscendC element-wise Add kernel —— 最小骨架示意（本环境未编译实跑）。
 *
 * 仅展示 AscendC kernel 的核心结构：CopyIn(GM->UB) -> Compute -> CopyOut(UB->GM)。
 * 完整可编译样例（含 host 侧 tiling、算子注册）请参考 CANN 官方 samples/operator。
 *
 * msprof 采集这种算子时，重点看 op_summary 里的 aiv_vec_ratio（vector 利用率）
 * 和 aic_mte2_ratio（GM 搬入占比）—— 见同目录 README.md。
 */
#include "kernel_operator.h"

using namespace AscendC;

constexpr int32_t BUFFER_NUM = 2; // double buffer，计算与搬运流水重叠

class KernelAdd {
public:
    __aicore__ inline KernelAdd() {}

    __aicore__ inline void Init(GM_ADDR x, GM_ADDR y, GM_ADDR z, uint32_t totalLength) {
        this->tileLength = totalLength / GetBlockNum();
        xGm.SetGlobalBuffer((__gm__ float *)x + this->tileLength * GetBlockIdx(), this->tileLength);
        yGm.SetGlobalBuffer((__gm__ float *)y + this->tileLength * GetBlockIdx(), this->tileLength);
        zGm.SetGlobalBuffer((__gm__ float *)z + this->tileLength * GetBlockIdx(), this->tileLength);
        pipe.InitBuffer(inQueueX, BUFFER_NUM, this->tileLength * sizeof(float));
        pipe.InitBuffer(inQueueY, BUFFER_NUM, this->tileLength * sizeof(float));
        pipe.InitBuffer(outQueueZ, BUFFER_NUM, this->tileLength * sizeof(float));
    }

    __aicore__ inline void Process() {
        CopyIn();
        Compute();
        CopyOut();
    }

private:
    __aicore__ inline void CopyIn() {
        LocalTensor<float> xLocal = inQueueX.AllocTensor<float>();
        LocalTensor<float> yLocal = inQueueY.AllocTensor<float>();
        DataCopy(xLocal, xGm, this->tileLength); // GM -> UB
        DataCopy(yLocal, yGm, this->tileLength);
        inQueueX.EnQue(xLocal);
        inQueueY.EnQue(yLocal);
    }

    __aicore__ inline void Compute() {
        LocalTensor<float> xLocal = inQueueX.DeQue<float>();
        LocalTensor<float> yLocal = inQueueY.DeQue<float>();
        LocalTensor<float> zLocal = outQueueZ.AllocTensor<float>();
        Add(zLocal, xLocal, yLocal, this->tileLength); // vector 单元逐元素相加
        outQueueZ.EnQue<float>(zLocal);
        inQueueX.FreeTensor(xLocal);
        inQueueY.FreeTensor(yLocal);
    }

    __aicore__ inline void CopyOut() {
        LocalTensor<float> zLocal = outQueueZ.DeQue<float>();
        DataCopy(zGm, zLocal, this->tileLength); // UB -> GM
        outQueueZ.FreeTensor(zLocal);
    }

    TPipe pipe;
    TQue<QuePosition::VECIN, BUFFER_NUM> inQueueX, inQueueY;
    TQue<QuePosition::VECOUT, BUFFER_NUM> outQueueZ;
    GlobalTensor<float> xGm, yGm, zGm;
    uint32_t tileLength;
};

extern "C" __global__ __aicore__ void add_custom(GM_ADDR x, GM_ADDR y, GM_ADDR z, uint32_t totalLength) {
    KernelAdd op;
    op.Init(x, y, z, totalLength);
    op.Process();
}
