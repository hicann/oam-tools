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

#ifndef MSPROFILER_API_PROF_DATA_CONFIG_H
#define MSPROFILER_API_PROF_DATA_CONFIG_H

#include "aprof_pub.h"

// DataTypeConfig
#define PROF_ACL_API              0x00000001ULL
#define PROF_TASK_TIME_L1         0x00000002ULL
#define PROF_AICORE_METRICS       0x00000004ULL
#define PROF_AICPU_TRACE          0x00000008ULL
#define PROF_L2CACHE              0x00000010ULL
#define PROF_HCCL_TRACE           0x00000020ULL
#define PROF_TRAINING_TRACE       0x00000040ULL
#define PROF_MSPROFTX             0x00000080ULL
#define PROF_RUNTIME_API          0x00000100ULL
#define PROF_GE_API_L0            0x00000200ULL
#define PROF_TASK_TSFW            0x00000400ULL
#define PROF_TASK_TIME            0x00000800ULL
#define PROF_TASK_MEMORY          0x00001000ULL
#define PROF_TASK_TIME_L2         0x00002000ULL
#define PROF_OP_ATTR              0x00004000ULL
#define PROF_TASK_TIME_L3         0x00008000ULL

// system profilinig switch
#define PROF_CPU                  0x00010000ULL
#define PROF_HARDWARE_MEMORY      0x00020000ULL
#define PROF_IO                   0x00040000ULL
#define PROF_INTER_CONNECTION     0x00080000ULL
#define PROF_DVPP                 0x00100000ULL
#define PROF_SYS_AICORE_SAMPLE    0x00200000ULL
#define PROF_AIVECTORCORE_SAMPLE  0x00400000ULL
#define PROF_INSTR                0x00800000ULL

#define PROF_GE_API_L1            0x0000001000000ULL
#define PROF_PURE_CPU             0x0000002000000ULL
#define PROF_RUNTIME_TRACE        0x0000004000000ULL
#define PROF_SCHEDULE_TIMELINE    0x0000008000000ULL
#define PROF_SCHEDULE_TRACE       0x0000010000000ULL
#define PROF_AIVECTORCORE_METRICS 0x0000020000000ULL
#define PROF_SUBTASK_TIME         0x0000040000000ULL
#define PROF_OP_DETAIL            0x0000080000000ULL
#define PROF_OP_TIMESTAMP         0x0000100000000ULL

#define PROF_AICPU_MODEL          0x4000000000000000ULL
#define PROF_MODEL_LOAD           0x8000000000000000ULL

#define PROF_TASK_TRACE  PROF_RUNTIME_TRACE | PROF_TASK_TIME | PROF_TRAINING_TRACE | PROF_HCCL_TRACE | PROF_TASK_TIME_L1

// profSwitchHi config, upper 16 bits will be send to aicpu by runtime
#define PROF_HI_AICPU_CHANNEL 0x1000000000000ULL   // bit0 of the upper 16 bits means aicpu channel switch

#endif  // MSPROFILER_API_PROF_DATA_CONFIG_H_