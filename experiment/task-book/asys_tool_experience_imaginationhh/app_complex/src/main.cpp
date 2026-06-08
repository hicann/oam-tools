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
 * Host 侧：先跑正常 Add(算子1，应成功)，再跑 gather(算子2，后半核读越界，应失败)。
 * 两个 kernel 在同一 stream 顺序下发，模拟多算子流水里的"第二个算子部分核故障"。
 */
#include <cstdio>
#include <cstdint>
#include "acl/acl.h"
#include "aclrtlaunch_add_ok_custom.h"
#include "aclrtlaunch_gather_bad_custom.h"

constexpr int32_t TOTAL = 8192;
constexpr uint32_t BLOCK_DIM = 8;

int main()
{
    if (aclInit(nullptr) != ACL_SUCCESS) { printf("[FAIL] aclInit\n"); return -1; }
    aclrtSetDevice(0);
    aclrtStream stream;
    aclrtCreateStream(&stream);

    size_t size = TOTAL * sizeof(uint16_t);
    uint8_t *xH, *yH;
    aclrtMallocHost((void **)&xH, size);
    aclrtMallocHost((void **)&yH, size);
    for (int i = 0; i < TOTAL; i++) { ((uint16_t *)xH)[i] = 0x3C00; ((uint16_t *)yH)[i] = 0x3C00; }

    uint8_t *xD, *yD, *zD, *dstD;
    aclrtMalloc((void **)&xD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMalloc((void **)&yD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMalloc((void **)&zD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMalloc((void **)&dstD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMemcpy(xD, size, xH, size, ACL_MEMCPY_HOST_TO_DEVICE);
    aclrtMemcpy(yD, size, yH, size, ACL_MEMCPY_HOST_TO_DEVICE);

    // 算子1：正常 Add
    printf("[complex] step1: launch add_ok_custom (expect success)...\n");
    ACLRT_LAUNCH_KERNEL(add_ok_custom)(BLOCK_DIM, stream, xD, yD, zD);

    // 算子2：gather，后半核读越界
    printf("[complex] step2: launch gather_bad_custom (blockIdx>=4 OOB read, expect fail)...\n");
    ACLRT_LAUNCH_KERNEL(gather_bad_custom)(BLOCK_DIM, stream, zD, dstD);

    aclError sync_ret = aclrtSynchronizeStream(stream);
    if (sync_ret != ACL_SUCCESS) {
        printf("[complex] aclrtSynchronizeStream FAILED -> %d (AI Core Error in gather expected)\n", sync_ret);
    } else {
        printf("[complex] sync OK (unexpected: fault not triggered)\n");
    }

    aclrtFree(xD); aclrtFree(yD); aclrtFree(zD); aclrtFree(dstD);
    aclrtFreeHost(xH); aclrtFreeHost(yH);
    aclrtDestroyStream(stream);
    aclrtResetDevice(0);
    aclFinalize();
    printf("[complex] done (ret=%d)\n", sync_ret);
    return sync_ret == ACL_SUCCESS ? 0 : 1;
}
