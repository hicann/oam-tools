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
#include <fstream>
#include "errno/error_code.h"
#include "utils/utils.h"
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "info_json.h"

using namespace analysis::dvvp::driver;
using namespace analysis::dvvp::host;
using namespace analysis::dvvp::common::error;

class INFO_JSON_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        GlobalMockObject::verify();
        jobInfo = ("64");
        devices = ("0");
        hostpid = 15151;
    }
    virtual void TearDown() {}

public:
    std::string jobInfo;
    std::string devices;
    int hostpid;
};

TEST_F(INFO_JSON_TEST, DrvGetAiCpuCoreIdWithCoreNum)
{
    GlobalMockObject::verify();
    int device_id = 0;
    DeviceInfo dev_info;

    MOCKER(halGetDeviceInfo).stubs().will(returnValue(DRV_ERROR_NONE));

    dev_info.aiCpuCoreNum = 8;
    InfoJson infoJson(jobInfo, devices, hostpid);
    EXPECT_EQ(PROFILING_SUCCESS, infoJson.GetDevInfo(device_id, dev_info));
}
