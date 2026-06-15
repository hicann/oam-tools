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
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "adx_prof_api.h"

using namespace Analysis::Dvvp::Adx;

class ADX_PROF_API_UTEST: public testing::Test {
protected:
    virtual void SetUp() {
    }
    virtual void TearDown() {

    }
};


TEST_F(ADX_PROF_API_UTEST, AdxIdeCreatePacket) {
    GlobalMockObject::verify();

    IdeBuffT outPut;
    int outLen = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, AdxIdeCreatePacket(NULL, 0, outPut, outLen));

    EXPECT_EQ(IDE_DAEMON_OK, AdxIdeCreatePacket("test", 0, outPut, outLen));
    AdxIdeFreePacket(outPut);
}

TEST_F(ADX_PROF_API_UTEST, AdxIdeFreePacket) {
    GlobalMockObject::verify();
    IdeBuffT outPut = (IdeBuffT)malloc(16);
    AdxIdeFreePacket(outPut);
    EXPECT_EQ(outPut, nullptr);
}

