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

#ifndef DEVPROF_COMMON_H
#define DEVPROF_COMMON_H

#include <cstdint>
#include "ascend_inpackage_hal.h"

#ifdef __PROF_LLT
#define STATIC
#else
#define STATIC static
#endif

#ifdef __cplusplus
extern "C" {
#endif
typedef struct prof_sample_start_para ProfSampleStartPara;
typedef struct prof_sample_para ProfSamplePara;
typedef struct prof_sample_stop_para ProfSampleStopPara;
typedef struct prof_sample_ops ProfSampleOps;
typedef struct prof_sample_register_para ProfSampleRegisterPara;


#ifdef __cplusplus
}
#endif

namespace Devprof {
constexpr int32_t REPORT_BUFF_CAPACITY = 16 * 1024;
constexpr size_t REPORT_BUFF_SIZE = 1024 * 1024;
constexpr uint32_t WAIT_DATA_TIME = 5U;
constexpr uint32_t WAIT_DRV_TIME = 1U;
int32_t ProfSendEvent(uint32_t devId, int32_t hostPid, const char *grpName);
}

#endif