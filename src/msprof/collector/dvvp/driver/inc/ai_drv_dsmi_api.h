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
#ifndef ANALYSIS_DVVP_DEVICE_AI_DRV_DSMI_API_H
#define ANALYSIS_DVVP_DEVICE_AI_DRV_DSMI_API_H

#include <map>
#include <string>
#include "ascend_hal.h"
#include "message/prof_params.h"


namespace Analysis {
namespace Dvvp {
namespace Driver {
int32_t DrvGetAicoreInfo(int32_t deviceId, int64_t &freq);
std::string DrvGeAicFrq(int32_t deviceId);
std::string DrvGeAivFrq(int32_t deviceId);
}  // namespace driver
}  // namespace dvvp
}  // namespace analysis

#endif
