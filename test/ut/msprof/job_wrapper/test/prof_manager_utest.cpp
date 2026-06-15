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
#include "prof_manager.h"
#include "message.h"
#include "errno/error_code.h"
#include "msprof_dlog.h"

using namespace analysis::dvvp::host;
using namespace analysis::dvvp::driver;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::transport;

class JOB_WRAPPER_PROF_MANAGER_UTEST: public testing::Test {
protected:
    virtual void SetUp() {
    }
    virtual void TearDown() {
    }
};

TEST_F(JOB_WRAPPER_PROF_MANAGER_UTEST, Handle_IdeCloudProfileProcess) {
    GlobalMockObject::verify();
    MOCKER_CPP(&ProfManager::CheckIfDevicesOnline)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));

    MOCKER_CPP(&ProfManager::CheckHandleSuc)
        .stubs()
        .will(returnValue(true))
        .then(returnValue(false));

    MOCKER_CPP(&ProfManager::ProcessHandleFailed)
        .stubs()
        .will(returnValue(PROFILING_FAILED));

    auto entry = analysis::dvvp::host::ProfManager::instance();
    entry->isInited_ = true;
    EXPECT_EQ(PROFILING_FAILED, entry->Handle(nullptr));

    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"1\",\"is_cancel\":true,\"profiling_mode\":\"def_mode\",\"host_profiling\":\"false\"}");
    entry->isInited_ = false;
    EXPECT_EQ(PROFILING_FAILED, entry->Handle(params));

    entry->isInited_ = true;
    EXPECT_EQ(PROFILING_FAILED, entry->Handle(params));  // Failed to CheckIfDevicesOnline
    EXPECT_EQ(PROFILING_SUCCESS, entry->Handle(params)); // Success to CheckHandleSuc
    EXPECT_EQ(PROFILING_FAILED, entry->Handle(params));  // Failed to ProcessHandleFailed
}

TEST_F(JOB_WRAPPER_PROF_MANAGER_UTEST, ProcessHandleFailed) {
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::host::ProfManager::instance();

    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"aa\", \"job_id\":\"cloud\", \"profiling_mode\":\"system-wide\"}");
    EXPECT_EQ(PROFILING_FAILED, entry->ProcessHandleFailed(params));

    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"1\", \"job_id\":\"cloud\", \"profiling_mode\":\"def_mode\"}");
    EXPECT_EQ(PROFILING_SUCCESS, entry->ProcessHandleFailed(params));
}