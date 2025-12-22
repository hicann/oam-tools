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

#ifndef PROF_API_STUB
#include "prof_api.h"

int32_t profRegReporterCallback(MsprofReportHandle reporter)
{
    (void)reporter;
    return 0;
}

int32_t profRegCtrlCallback(MsprofCtrlHandle handle)
{
    (void)handle;
    return 0;
}

int32_t profRegDeviceStateCallback(MsprofSetDeviceHandle handle)
{
    (void)handle;
    return 0;
}

int32_t profGetDeviceIdByGeModelIdx(const uint32_t modelIdx, uint32_t *deviceId)
{
    (void)modelIdx;
    (void)deviceId;
    return 0;
}

int32_t profSetProfCommand(VOID_PTR command, uint32_t len)
{
    (void)command;
    (void)len;
    return 0;
}

int32_t profSetStepInfo(const uint64_t indexId, const uint16_t tagId, void* const stream)
{
    (void)indexId;
    (void)tagId;
    (void)stream;
    return 0;
}

int32_t MsprofReportApi(uint32_t nonPersistantFlag, const MsprofApi *api)
{
    (void)nonPersistantFlag;
    (void)api;
    return 0;
}

int32_t MsprofReportEvent(uint32_t nonPersistantFlag, const MsprofEvent *event)
{
    (void)nonPersistantFlag;
    (void)event;
    return 0;
}

int32_t MsprofReportCompactInfo(uint32_t nonPersistantFlag, const VOID_PTR data, uint32_t length)
{
    (void)nonPersistantFlag;
    (void)data;
    (void)length;
    return 0;
}

int32_t MsprofReportAdditionalInfo(uint32_t nonPersistantFlag, const VOID_PTR data, uint32_t length)
{
    (void)nonPersistantFlag;
    (void)data;
    (void)length;
    return 0;
}

int32_t MsprofRegTypeInfo(uint16_t level, uint32_t typeId, const char *typeName)
{
    (void)level;
    (void)typeId;
    (void)typeName;
    return 0;
}

uint64_t MsprofGetHashId(const char *hashInfo, size_t length)
{
    (void)hashInfo;
    (void)length;
    return 0;
}

uint64_t MsprofStr2Id(const char *hashInfo, size_t length)
{
    (void)hashInfo;
    (void)length;
    return 0;
}

int32_t MsprofInit(uint32_t dataType, VOID_PTR data, uint32_t dataLen)
{
    (void)dataType;
    (void)data;
    (void)dataLen;
    return 0;
}

int32_t MsprofStart(uint32_t dataType, const void *data, uint32_t length)
{
    (void)dataType;
    (void)data;
    (void)length;
    return 0;
}
 
int32_t MsprofStop(uint32_t dataType, const void *data, uint32_t length)
{
    (void)dataType;
    (void)data;
    (void)length;
    return 0;
}

int32_t MsprofSetConfig(uint32_t configType, const char *config,
    size_t configLength)
{
    (void)configType;
    (void)config;
    (void)configLength;
    return 0;
}

int32_t MsprofRegisterCallback(uint32_t moduleId, ProfCommandHandle handle)
{
    (void)moduleId;
    (void)handle;
    return 0;
}

int32_t MsprofNotifySetDevice(uint32_t chipId, uint32_t deviceId, bool isOpen)
{
    (void)chipId;
    (void)deviceId;
    (void)isOpen;
    return 0;
}

int32_t MsprofReportData(uint32_t moduleId, uint32_t type, VOID_PTR data, uint32_t len)
{
    (void)moduleId;
    (void)type;
    (void)data;
    (void)len;
    return 0;
}

int32_t MsprofSetDeviceIdByGeModelIdx(const uint32_t geModelIdx, const uint32_t deviceId)
{
    (void)geModelIdx;
    (void)deviceId;
    return 0;
}

int32_t MsprofUnsetDeviceIdByGeModelIdx(const uint32_t geModelIdx, const uint32_t deviceId)
{
    (void)geModelIdx;
    (void)deviceId;
    return 0;
}

int32_t MsprofFinalize()
{
    return 0;
}

uint64_t MsprofSysCycleTime()
{
    return 0;
}
#else

#include <string>
#include <iostream>

void profOstreamStub(void)
{
    std::string temp = "profOstreamStub";
    std::cout << temp.c_str() << std::endl;
    double doubleTemp = 0.02;
    std::cout << doubleTemp << std::endl;
    return;
}
#endif
