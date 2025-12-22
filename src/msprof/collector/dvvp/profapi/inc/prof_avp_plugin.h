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

#ifndef PROF_AVP_PLUGIN_H
#define PROF_AVP_PLUGIN_H
#include <vector>
#include <map>
#include "singleton/singleton.h"
#include "prof_api.h"
#include "prof_plugin.h"
#include "prof_utils.h"

namespace ProfAPI {
using ProfInitFunc = int32_t (*)(uint32_t type, void *data, uint32_t dataLen);
using ProfRegisterCallbackFunc = int32_t (*)(uint32_t moduleId, ProfCommandHandle handle);
using ProfNotifySetDeviceFunc = int32_t (*)(uint32_t chipId, uint32_t deviceId, bool isOpen);
using ProfFinalizeFunc = int32_t (*)();
using ProfSysCycleTimeFunc = uint64_t (*)();
using ProfRegTypeInfoFunc = int32_t (*)(uint16_t level, uint32_t typeId, const char *typeName);
using ProfGetHashIdFunc = uint64_t (*)(const char *hashInfo, size_t length);

class ProfAvpPlugin : public analysis::dvvp::common::singleton::Singleton<ProfAvpPlugin> {
public:
    void ProfApiInit();
    int32_t ProfInit(uint32_t type, void *data, uint32_t dataLen);
    int32_t ProfFinalize() const;
    int32_t ProfNotifySetDevice(uint32_t chipId, uint32_t deviceId, bool isOpen);
    int32_t ProfRegisterCallback(uint32_t moduleId, ProfCommandHandle handle);
    int32_t ProfReportApi(uint32_t agingFlag, const MsprofApi &api) const;
    int32_t ProfReportEvent(uint32_t agingFlag, const MsprofEvent &event) const;
    int32_t ProfReportCompactInfo(uint32_t agingFlag, const VOID_PTR data, uint32_t len) const;
    int32_t ProfReportAdditionalInfo(uint32_t agingFlag, const VOID_PTR data, uint32_t len) const;
    int32_t ProfReportRegTypeInfo(uint16_t level, uint32_t typeId, const char *typeName) const;
    uint64_t ProfReportGetHashId(const char *hashInfo, size_t length) const;
    uint64_t ProfSysCycleTime() const;
    ~ProfAvpPlugin() override;

private:
    void LoadProfApi();
    void LoadProfInfo();
    void *avpLibHandle_;
    std::mutex deviceStateMutex_;
    std::mutex callbackMutex_;
    std::map<uint64_t, bool> deviceStates_;
    std::map<uint32_t, ProfCommandHandle> moduleCallbacks_;

    PTHREAD_ONCE_T profApiLoadFlag_;
    ProfInitFunc profInit_{ nullptr };
    ProfRegisterCallbackFunc profRegisterCallback_{ nullptr };
    ProfRegTypeInfoFunc profReportRegTypeInfo_{ nullptr };
    ProfGetHashIdFunc profReportGetHashId_{ nullptr };
    ProfNotifySetDeviceFunc profNotifySetDevice_{ nullptr };
    ProfFinalizeFunc profFinalize_{ nullptr };
    ProfReportEventFunc profReportEvent_{ nullptr };
    ProfReportApiFunc profReportApi_{ nullptr };
    ProfReportCompactInfoFunc profReportCompact_{ nullptr };
    ProfReportAdditionalInfoFunc profReportAdditional_{ nullptr };
    ProfSysCycleTimeFunc profProfSysCycleTime_{ nullptr };
};
}  // namespace ProfAPI
#endif
