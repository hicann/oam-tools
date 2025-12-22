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
#include "mockcpp/mockcpp.hpp"
#include "gtest/gtest.h"
#include "adx_prof_api.h"
#include "errno/error_code.h"
#include "securec.h"

using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Adx;

class ADX_PROF_API_STEST: public testing::Test {
protected:
    virtual void SetUp() {

    }
    virtual void TearDown() {
        GlobalMockObject::verify();
    }
};

TEST_F(ADX_PROF_API_STEST, AdxIdeGetVfIdBySession) {
    GlobalMockObject::verify();
    HDC_SESSION session = (HDC_SESSION)0x12345678;
    int32_t vfId = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, AdxIdeGetVfIdBySession(session, vfId));
}