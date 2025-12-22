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
#include <map>
#include "tsd/tsd_client.h"
#include <unistd.h>

namespace {
    pid_t pid = 12345;
}

uint32_t TsdCapabilityGet(const uint32_t logicDeviceId, const int32_t type, const uint64_t ptr)
{
    bool *result = (bool *)(ptr);
    *result = true;
    return 0;
}
uint32_t TsdProcessOpen(const uint32_t logicDeviceId, ProcOpenArgs *openArgs)
{
    *(openArgs->subPid) = pid;
    return 0;
}
uint32_t TsdGetProcListStatus(const uint32_t logicDeviceId, ProcStatusParam *pidInfo, const uint32_t arrayLen)
{
    if (pidInfo->pid == pid) {
        pidInfo->curStat = SUB_PROCESS_STATUS_NORMAL;
    }
    return 0;
}
uint32_t ProcessCloseSubProcList(const uint32_t logicDeviceId, const ProcStatusParam *closeList,
                                    const uint32_t listSize)
{
    return 0;
}

static const std::map<std::string, void*> g_map = {
    {"TsdCapabilityGet", (void *)TsdCapabilityGet},
    {"TsdProcessOpen", (void *)TsdProcessOpen},
    {"TsdGetProcListStatus", (void *)TsdGetProcListStatus},
    {"ProcessCloseSubProcList", (void *)ProcessCloseSubProcList}
};

void *mmDlsymTsd(void *handle, const char *funcName)
{
    auto it = g_map.find(funcName);
    if (it != g_map.end()) {
        return it->second;
    }
    return nullptr;
}

uint32_t TsdCapabilityGetStubError(const uint32_t logicDeviceId, const int32_t type, const uint64_t ptr)
{
    return 1;
}
uint32_t TsdProcessOpenStubError(const uint32_t logicDeviceId, ProcOpenArgs *openArgs)
{
    return 1;
}
uint32_t TsdGetProcListStatusError(const uint32_t logicDeviceId, ProcStatusParam *pidInfo, const uint32_t arrayLen)
{
    return 1;
}
uint32_t ProcessCloseSubProcListStubError(const uint32_t logicDeviceId, const ProcStatusParam *closeList,
                                          const uint32_t listSize)
{
    return 1;
}

void *mmDlsymTsdError(void *handle, const char *funcName)
{
    std::map<std::string, void*> errorFunc = {
        {"TsdCapabilityGet", (void *)TsdCapabilityGetStubError},
        {"TsdProcessOpen", (void *)TsdProcessOpenStubError},
        {"TsdGetProcListStatus", (void *)TsdGetProcListStatusError},
        {"ProcessCloseSubProcList", (void *)ProcessCloseSubProcListStubError}
    };
    auto it = errorFunc.find(funcName);
    if (it != errorFunc.end()) {
        return it->second;
    }
    return nullptr;
}

int32_t mmDlclose(void *handle)
{
    return 0;
}

void *mmDlopen(const char *fileName, int mode)
{
    return nullptr;
}