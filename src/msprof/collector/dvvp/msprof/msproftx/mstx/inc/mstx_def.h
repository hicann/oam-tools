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
#ifndef MSTX_DATA_TYPE_H
#define MSTX_DATA_TYPE_H

#define MSTX_INVALID_RANGE_ID 0
#define MSTX_SUCCESS 0
#define MSTX_FAIL 1
#define MSTX_TOOLS_MSPROF_ID 0x1000

typedef enum {
    MODULE_INVALID,
    PROF_MODULE_MSPROF,
    PROF_MODULE_MSPTI,
    PROF_MODULE_SIZE
} ProfModule;

typedef enum {
    MSTX_API_MODULE_INVALID                 = 0,
    MSTX_API_MODULE_CORE                    = 1,
    MSTX_API_MODULE_CORE_DOMAIN             = 2,
    MSTX_API_MODULE_SIZE,                   // end of the enum, new enum items must be added before this
    MSTX_API_MODULE_FORCE_INT               = 0x7fffffff
} MstxFuncModule;

typedef enum {
    MSTX_FUNC_START                         = 0,
    MSTX_FUNC_MARKA                         = 1,
    MSTX_FUNC_RANGE_STARTA                  = 2,
    MSTX_FUNC_RANGE_END                     = 3,
    MSTX_API_CORE_MEMHEAP_REGISTER          = 4,
    MSTX_API_CORE_MEMHEAP_UNREGISTER        = 5,
    MSTX_API_CORE_MEM_REGIONS_REGISTER      = 6,
    MSTX_API_CORE_MEM_REGIONS_UNREGISTER    = 7,
    MSTX_FUNC_END
} MstxCoreFuncId;

typedef enum {
    MSTX_FUNC_DOMAIN_START        = 0,
    MSTX_FUNC_DOMAIN_CREATEA      = 1,
    MSTX_FUNC_DOMAIN_DESTROY      = 2,
    MSTX_FUNC_DOMAIN_MARKA        = 3,
    MSTX_FUNC_DOMAIN_RANGE_STARTA = 4,
    MSTX_FUNC_DOMAIN_RANGE_END    = 5,
    MSTX_FUNC_DOMAIN_END
} MstxCore2FuncId;

using mstxRangeId = uint64_t;

struct MstxDomainRegistrationSt {};
typedef struct MstxDomainRegistrationSt MstxDomainHandle;
typedef MstxDomainHandle* mstxDomainHandle_t;

typedef void* aclrtStream;
typedef void (*MstxFuncPointer)(void);
typedef MstxFuncPointer** MstxFuncTable;
typedef int (*MstxGetModuleFuncTableFunc)(MstxFuncModule module, MstxFuncTable *outTable, unsigned int *outSize);
typedef int(*MstxInitInjectionFunc)(MstxGetModuleFuncTableFunc);

#endif