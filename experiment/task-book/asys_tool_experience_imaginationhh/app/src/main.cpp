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
 * Host 侧启动程序 —— 分配显存、拉起 dirty_custom 故障 kernel、同步等待。
 * kernel 在写回阶段越界访问 GM，aclrtSynchronizeStream 会返回错误，
 * 同时在 plog / data-dump 留下 AI Core Error 现场，供 asys 收集与解析。
 */
#include <cstdio>
#include <cstdint>
#include "acl/acl.h"
#include "aclrtlaunch_dirty_custom.h"  // ascendc_library 编译时自动生成

constexpr int32_t TOTAL = 8192;
constexpr uint32_t BLOCK_DIM = 8;

int main()
{
    aclError ret = aclInit(nullptr);
    if (ret != ACL_SUCCESS) { printf("[FAIL] aclInit -> %d\n", ret); return -1; }
    aclrtSetDevice(0);
    aclrtStream stream;
    aclrtCreateStream(&stream);

    size_t size = TOTAL * sizeof(uint16_t);  // fp16
    uint8_t *xH, *yH;
    aclrtMallocHost((void **)&xH, size);
    aclrtMallocHost((void **)&yH, size);
    for (int i = 0; i < TOTAL; i++) {
        ((uint16_t *)xH)[i] = 0x3C00;  // fp16(1.0)
        ((uint16_t *)yH)[i] = 0x3C00;
    }

    uint8_t *xD, *yD, *zD;
    aclrtMalloc((void **)&xD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMalloc((void **)&yD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMalloc((void **)&zD, size, ACL_MEM_MALLOC_HUGE_FIRST);
    aclrtMemcpy(xD, size, xH, size, ACL_MEMCPY_HOST_TO_DEVICE);
    aclrtMemcpy(yD, size, yH, size, ACL_MEMCPY_HOST_TO_DEVICE);

    printf("[dirty] launching fault-injection kernel (OOB GM write)...\n");
    ACLRT_LAUNCH_KERNEL(dirty_custom)(BLOCK_DIM, stream, xD, yD, zD);

    // 越界写回会在此被检测到，预期返回非 0 错误码（AI Core Error）
    aclError sync_ret = aclrtSynchronizeStream(stream);
    if (sync_ret != ACL_SUCCESS) {
        printf("[dirty] aclrtSynchronizeStream FAILED -> %d (AI Core Error expected)\n", sync_ret);
    } else {
        printf("[dirty] sync OK (unexpected: fault not triggered)\n");
    }

    aclrtFree(xD); aclrtFree(yD); aclrtFree(zD);
    aclrtFreeHost(xH); aclrtFreeHost(yH);
    aclrtDestroyStream(stream);
    aclrtResetDevice(0);
    aclFinalize();
    printf("[dirty] done (ret=%d)\n", sync_ret);
    return sync_ret == ACL_SUCCESS ? 0 : 1;
}
