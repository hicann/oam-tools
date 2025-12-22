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
 
#ifndef MSPROF_ENGINE_ACL_API_COMMON_H
#define MSPROF_ENGINE_ACL_API_COMMON_H

#include <cstdint>

#include "prof_acl_api.h"
#include "prof_api.h"
#include "utils.h"

#ifdef MSPROF_DEBUG
const uint64_t PROF_SWITCH_SUPPORT = PROF_ACL_API | PROF_TASK_TIME | PROF_TASK_TIME_L1 | PROF_AICORE_METRICS |
    PROF_AICPU_TRACE | PROF_FWK_SCHEDULE_L1 | PROF_RUNTIME_API | PROF_TASK_TSFW | PROF_FWK_SCHEDULE_L0 |
    PROF_RUNTIME_TRACE | PROF_SCHEDULE_TIMELINE | PROF_SCHEDULE_TRACE | PROF_AIVECTORCORE_METRICS |
    PROF_SUBTASK_TIME | PROF_TRAINING_TRACE | PROF_HCCL_TRACE | PROF_CPU | PROF_HARDWARE_MEMORY |
    PROF_IO | PROF_INTER_CONNECTION | PROF_DVPP | PROF_SYS_AICORE_SAMPLE | PROF_AIVECTORCORE_SAMPLE |
    PROF_L2CACHE | PROF_MSPROFTX | PROF_AICPU_MODEL | PROF_TASK_MEMORY | PROF_TASK_TIME_L2 | PROF_OP_ATTR;
#else
const uint64_t PROF_SWITCH_SUPPORT = PROF_ACL_API | PROF_TASK_TIME | PROF_TASK_TIME_L1 | PROF_AICORE_METRICS |
    PROF_AICPU_TRACE | PROF_L2CACHE | PROF_HCCL_TRACE | PROF_TRAINING_TRACE | PROF_MSPROFTX | PROF_RUNTIME_API |
    PROF_AICPU_MODEL | PROF_TASK_MEMORY | PROF_FWK_SCHEDULE_L0 | PROF_FWK_SCHEDULE_L1 | PROF_TASK_TIME_L2 |
    PROF_OP_ATTR;
#endif // MSPROF_DEBUG

#define RETURN_IF_NOT_SUCCESS(ret)  \
    do {                            \
        if ((ret) != ACL_SUCCESS) { \
            return ret;             \
        }                           \
    } while (0)
#endif // MSPROF_ENGINE_ACL_API_COMMON_H
