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
#ifndef ANALYSIS_DVVP_COMMON_CONFIG_MANAGER_H
#define ANALYSIS_DVVP_COMMON_CONFIG_MANAGER_H

#include <string>
#include <map>
#include "singleton/singleton.h"
#include "errno/error_code.h"
#include "utils/utils.h"
#include "message/prof_params.h"

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Config {

constexpr uint32_t VER_310M = 5;
enum class PlatformType {
    MINI_TYPE = 0,
    CLOUD_TYPE = 1,
    DC_TYPE = 4,
    CHIP_V4_1_0,
    MINI_V3_TYPE = 7,
    END_TYPE = 17
};

const std::map<PlatformType, std::string> FREQUENCY_TYPE = {
    {PlatformType::MINI_TYPE, "19.2"},
    {PlatformType::CLOUD_TYPE, "100"},
    {PlatformType::DC_TYPE, "38.4"},
    {PlatformType::CHIP_V4_1_0, "50"},
    {PlatformType::MINI_V3_TYPE, "48"}
};

const std::map<PlatformType, std::string> AIC_TYPE = {
    {PlatformType::MINI_TYPE, "680"},
    {PlatformType::CLOUD_TYPE, "800"},
    {PlatformType::DC_TYPE, "1150"},
    {PlatformType::CHIP_V4_1_0, "800"},
    {PlatformType::MINI_V3_TYPE, "1250"}
};

class ConfigManager : public analysis::dvvp::common::singleton::Singleton<ConfigManager> {
public:
    ConfigManager();
    ~ConfigManager() override;
    int32_t Init();
    void Uninit();
    std::string GetFrequency() const;
    std::string GetChipIdStr();
    PlatformType GetPlatformType() const;
    std::string GetAicDefFrequency() const;
    bool IsDriverSupportLlc() const;
    std::string GetPerfDataDir(const int32_t devId = 0) const;
    std::string GetDefaultWorkDir() const;
    void GetVersionSpecificMetrics(std::string &aicMetrics) const;

private:
    void InitFrequency();

    bool isInit_;
    std::map<std::string, std::string> configMap_;
};
}
}
}
}
#endif
