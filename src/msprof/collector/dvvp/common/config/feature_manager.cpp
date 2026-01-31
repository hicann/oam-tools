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
#include "feature_manager.h"
#include "errno/error_code.h"

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Config {

using namespace analysis::dvvp::common::error;
namespace {
// featureName, compatibility, featureVersion, affectedComponent, affectedComponentVersion, infoLog
static FeatureRecord g_features[] = {
    {"ATTR", "0", "1", "all", "all", "It not support feature: ATTR!"},
};
static const std::string FILE_NAME = "incompatible_features.json";
}

FeatureManager::FeatureManager() {}
 
FeatureManager::~FeatureManager()
{
    Uninit();
}

int32_t FeatureManager::Init()
{
    if (isInit_) {
        MSPROF_LOGI("FeatureManager is already initialized.");
        return PROFILING_SUCCESS;
    }
    FUNRET_CHECK_EXPR_ACTION(!CheckCreateFeatures(), return PROFILING_FAILED,
        "Failed to check feature list.");

    isInit_ = true;
    MSPROF_LOGI("FeatureManager initialized successfully.");
    return PROFILING_SUCCESS;
}

bool FeatureManager::CheckCreateFeatures() const
{
    for (const auto& feature : g_features) {
        FUNRET_CHECK_EXPR_ACTION(feature.featureName[0] == '\0' || feature.info.affectedComponent[0] == '\0' ||
            feature.info.affectedComponentVersion[0] == '\0' || feature.info.compatibility[0] == '\0' ||
            feature.info.featureVersion[0] == '\0' || feature.info.infoLog[0] == '\0', return false,
            "Function initialization failed. Member fields are empty.");
    }
    MSPROF_LOGI("All feature checks are successful.");
    return true;
}

FeatureRecord* FeatureManager::GetIncompatibleFeatures(size_t *featuresSize) const
{
    MSPROF_LOGD("Start to obtain the address information of the feature.");
    FUNRET_CHECK_EXPR_ACTION(featuresSize == nullptr, return nullptr,
        "Input parameter featuresSize for GetIncompatibleFeatures is nullptr.");

    *featuresSize = sizeof(g_features) / sizeof(FeatureRecord);
    MSPROF_LOGD("Stop to obtain the address information of the feature.");
    return &g_features[0];
}

void FeatureManager::Uninit()
{
    isInit_ = false;
}
 
}  // namespace Config
}  // namespace Comon
}  // namespace Dvvp
}  // namespace Analysis