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
#include <fstream>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "info_json.h"
#include "ai_drv_dev_api.h"
#include "config/config.h"
#include "config_manager.h"
#include "errno/error_code.h"
#include "msprof_dlog.h"
#include "prof_manager.h"
#include "securec.h"
#include "utils/utils.h"
#include "platform/platform.h"
#include "task_relationship_mgr.h"
#include "json/json.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::host;
using namespace Dvvp::Collect::Platform;

TEST(INFO_JSON_TEST, GetHwtsFreq) {
    GlobalMockObject::verify();
    auto configManager = ConfigManager::instance();
    const bool hasOriginalType = configManager->configMap_.count("type") > 0;
    const std::string originalType = hasOriginalType ? configManager->configMap_["type"] : "";
    configManager->configMap_["type"] = std::to_string(static_cast<int32_t>(PlatformType::CHIP_CLOUD_V3));
    InfoJson infoJson("1", "0", 1);
    std::string freq = "1005";
    EXPECT_EQ("1000", infoJson.GetHwtsFreq(freq));
    freq = "1000.1";
    EXPECT_EQ("1000.1", infoJson.GetHwtsFreq(freq));
    if (hasOriginalType) {
        configManager->configMap_["type"] = originalType;
    } else {
        configManager->configMap_.erase("type");
    }
}
