/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
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
#include <cstdio>
#include <unistd.h>

#include "gtest/gtest.h"

#if defined(__GNUC__)
extern "C" void __gcov_dump(void) __attribute__((weak));
extern "C" void __gcov_exit(void) __attribute__((weak));
#endif

int main(int argc, char **argv) {
    testing::InitGoogleTest(&argc, argv);

    // Runs all tests using Google Test.
    // testing::GTEST_FLAG(filter) = "COMMON_QUEUE_RING_BUFFER_TEST.BlockBuffer_BasePushPopTest";
    int ret = RUN_ALL_TESTS();
#if defined(__GNUC__)
    if (__gcov_dump != nullptr) {
        __gcov_dump();
    } else if (__gcov_exit != nullptr) {
        __gcov_exit();
    }
#endif
    fflush(stdout);
    fflush(stderr);
    _exit(ret);
}
