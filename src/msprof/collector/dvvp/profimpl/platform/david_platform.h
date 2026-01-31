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

#ifndef DVVP_COLLECT_PLATFORM_DAVID_PLATFORM_H
#define DVVP_COLLECT_PLATFORM_DAVID_PLATFORM_H
#include "platform_interface.h"

namespace Dvvp {
namespace Collect {
namespace Platform {
class DavidPlatform : public PlatformInterface {
public:
    DavidPlatform();
    ~DavidPlatform() override {}
    uint16_t GetMaxMonitorNumber() const override;

protected:
    std::string GetPipeUtilizationMetrics() override;
    std::string GetMemoryMetrics() override;
    std::string GetMemoryL0Metrics() override;
    std::string GetMemoryUBMetrics() override;
    std::string GetArithmeticUtilizationMetrics() override;
    std::string GetResourceConflictRatioMetrics() override;
    std::string GetL2CacheMetrics() override;
    int32_t InitOnlineAnalyzer() override;
    std::string GetL2CacheEvents() override;
    uint16_t GetQosMonitorNumber() const override;

private:
    void InsertSysFeature();
};
}}}
#endif