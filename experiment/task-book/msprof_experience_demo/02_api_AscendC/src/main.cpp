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
 * Host 侧启动程序 —— 分配显存、拉起 add_custom kernel、拷回校验。
 * 用 ascendc_library 自动生成的 aclrtlaunch_add_custom.h + ACLRT_LAUNCH_KERNEL 宏直调。
 */
#include <cstdio>
#include <cstdint>
#include "acl/acl.h"
#include "aclrtlaunch_add_custom.h" // ascendc_library 编译时自动生成

#define CHECK(x)                                  \
    do {                                          \
        aclError __r = (x);                       \
        if (__r != ACL_SUCCESS) {                 \
            printf("[FAIL] %s -> %d\n", #x, __r); \
            return -1;                            \
        }                                         \
    } while (0)

constexpr int32_t TOTAL = 8192;
constexpr uint32_t BLOCK_DIM = 8;

int main() {
    CHECK(aclInit(nullptr));
    CHECK(aclrtSetDevice(0));
    aclrtStream stream;
    CHECK(aclrtCreateStream(&stream));

    size_t size = TOTAL * sizeof(uint16_t); // fp16
    uint8_t *xH, *yH, *zH;
    CHECK(aclrtMallocHost((void **)&xH, size));
    CHECK(aclrtMallocHost((void **)&yH, size));
    CHECK(aclrtMallocHost((void **)&zH, size));
    for (int i = 0; i < TOTAL; i++) { // fp16(1.0)=0x3C00, 1+1=2 → 0x4000
        ((uint16_t *)xH)[i] = 0x3C00;
        ((uint16_t *)yH)[i] = 0x3C00;
    }

    uint8_t *xD, *yD, *zD;
    CHECK(aclrtMalloc((void **)&xD, size, ACL_MEM_MALLOC_HUGE_FIRST));
    CHECK(aclrtMalloc((void **)&yD, size, ACL_MEM_MALLOC_HUGE_FIRST));
    CHECK(aclrtMalloc((void **)&zD, size, ACL_MEM_MALLOC_HUGE_FIRST));
    CHECK(aclrtMemcpy(xD, size, xH, size, ACL_MEMCPY_HOST_TO_DEVICE));
    CHECK(aclrtMemcpy(yD, size, yH, size, ACL_MEMCPY_HOST_TO_DEVICE));

    // warmup + 多次拉起（给 msprof 稳定样本）
    for (int it = 0; it < 20; it++) {
        ACLRT_LAUNCH_KERNEL(add_custom)(BLOCK_DIM, stream, xD, yD, zD);
    }
    CHECK(aclrtSynchronizeStream(stream));

    CHECK(aclrtMemcpy(zH, size, zD, size, ACL_MEMCPY_DEVICE_TO_HOST));
    printf("[add] z[0]=0x%04X (expect 0x4000=2.0), z[%d]=0x%04X\n", ((uint16_t *)zH)[0], TOTAL - 1,
        ((uint16_t *)zH)[TOTAL - 1]);

    aclrtFree(xD);
    aclrtFree(yD);
    aclrtFree(zD);
    aclrtFreeHost(xH);
    aclrtFreeHost(yH);
    aclrtFreeHost(zH);
    aclrtDestroyStream(stream);
    aclrtResetDevice(0);
    aclFinalize();
    printf("[add] done\n");
    return 0;
}
