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

#include "david_lite_platform.h"
#include "config/config.h"

namespace Dvvp {
namespace Collect {
namespace Platform {
using namespace analysis::dvvp::common::config;

PLATFORM_REGISTER(CHIP_CLOUD_V3_LITE, DavidLitePlatform);

uint16_t DavidLitePlatform::GetBiuPerfGroupNum() const { return BIU_PERF_LOWER_GROUP_NUM; }

uint16_t DavidLitePlatform::GetCcuDieNum() const { return DAVID_LITE_CCU_DIE_NUM; }
} // namespace Platform
} // namespace Collect
} // namespace Dvvp
