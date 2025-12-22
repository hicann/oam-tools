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
 
#ifndef PROF_PLUGIN_H
#define PROF_PLUGIN_H
#include <string>
#include <map>
#include <mutex>
#include <set>
#include "prof_api.h"

namespace ProfAPI {
using ProfReportApiFunc = int32_t (*) (uint32_t agingFlag, const MsprofApi &api);
using ProfReportEventFunc = int32_t (*) (uint32_t agingFlag, const MsprofEvent &event);
using ProfReportCompactInfoFunc = int32_t (*) (uint32_t agingFlag, const VOID_PTR data, uint32_t len);
using ProfReportAdditionalInfoFunc = int32_t (*) (uint32_t agingFlag, const VOID_PTR data, uint32_t len);
using ProfReportRegTypeInfoFunc = int32_t (*) (uint16_t level, uint32_t typeId, const std::string &typeName);
using ProfReportGetHashIdFunc = uint64_t (*) (const std::string &info);
using ProfHostFreqIsEnableFunc = bool (*) ();

using ProfReportApiCFunc = int32_t (*) (uint32_t agingFlag, const MsprofApi* api);
using ProfReportEventCFunc = int32_t (*) (uint32_t agingFlag, const MsprofEvent* event);
using ProfReportRegTypeInfoCFunc = int32_t (*) (uint16_t level, uint32_t typeId, const char* typeName, size_t len);
using ProfReportGetHashIdCFunc = uint64_t (*) (const char* info, size_t len);
using ProfHostFreqIsEnableCFunc = int8_t (*) ();

class ProfPlugin { // : public analysis::dvvp::common::singleton::Singleton<ProfPlugin> {
public:
    virtual ~ProfPlugin() {}
    virtual int32_t ProfInit(uint32_t type, void *data, uint32_t dataLen) = 0;
    virtual int32_t ProfStart(uint32_t dataType, const void *data, uint32_t length) = 0;
    virtual int32_t ProfStop(uint32_t dataType, const void *data, uint32_t length) = 0;
    virtual int32_t ProfSetConfig(uint32_t configType, const char *config, size_t configLength) = 0;
    virtual int32_t ProfRegisterCallback(uint32_t moduleId, ProfCommandHandle handle) = 0;
    virtual int32_t ProfReportData(uint32_t moduleId, uint32_t type, void* data, uint32_t len) = 0;
    virtual int32_t ProfReportApi(uint32_t agingFlag, const MsprofApi* api) = 0;
    virtual int32_t ProfReportEvent(uint32_t agingFlag, const MsprofEvent* event) = 0;
    virtual int32_t ProfReportCompactInfo(uint32_t agingFlag, const VOID_PTR data, uint32_t len) = 0;
    virtual int32_t ProfReportAdditionalInfo(uint32_t agingFlag, const VOID_PTR data, uint32_t len) = 0;
    virtual int32_t ProfReportRegTypeInfo(uint16_t level, uint32_t typeId, const char* typeName, size_t len) = 0;
    virtual uint64_t ProfReportGetHashId(const char* info, size_t len) = 0;
    virtual int32_t ProfSetDeviceIdByGeModelIdx(const uint32_t geModelIdx, const uint32_t deviceId) = 0;
    virtual int32_t ProfUnSetDeviceIdByGeModelIdx(const uint32_t geModelIdx, const uint32_t deviceId) = 0;
    virtual int32_t ProfSetStepInfo(const uint64_t indexId, const uint16_t tagId, void* const stream) = 0;
    virtual int32_t ProfNotifySetDevice(uint32_t chipId, uint32_t deviceId, bool isOpen) = 0;
    virtual int32_t ProfFinalize() = 0;
    virtual bool ProfHostFreqIsEnable() = 0;
    static size_t ReadProfCommandHandle();
protected:
    static std::mutex callbackMutex_;
    static std::map<uint32_t, std::set<ProfCommandHandle>> moduleCallbacks_;
};
}
#endif