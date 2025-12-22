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
 
#ifndef PROF_ATLS_PLUGIN_H
#define PROF_ATLS_PLUGIN_H
#include <map>
#include "prof_plugin.h"
#include "singleton/singleton.h"
namespace ProfAPI {
using ProfCommand = MsprofCommandHandle;
class ProfAtlsPlugin : public ProfPlugin, public analysis::dvvp::common::singleton::Singleton<ProfAtlsPlugin> {
    friend analysis::dvvp::common::singleton::Singleton<ProfAtlsPlugin>;
public:
    int32_t ProfInit(uint32_t type, void *data, uint32_t dataLen) override;
    int32_t ProfStart(uint32_t dataType, const void *data, uint32_t length) override;
    int32_t ProfStop(uint32_t dataType, const void *data, uint32_t length) override;
    int32_t ProfSetConfig(uint32_t configType, const char *config, size_t configLength) override;
    int32_t ProfRegisterCallback(uint32_t moduleId, ProfCommandHandle handle) override;
    int32_t ProfReportData(uint32_t moduleId, uint32_t type, void* data, uint32_t len) override;
    int32_t ProfReportApi(uint32_t agingFlag, const MsprofApi* api) override;
    int32_t ProfReportEvent(uint32_t agingFlag, const MsprofEvent* event) override;
    int32_t ProfReportCompactInfo(uint32_t agingFlag, const VOID_PTR data, uint32_t len) override;
    int32_t ProfReportAdditionalInfo(uint32_t agingFlag, const VOID_PTR data, uint32_t len) override;
    int32_t ProfReportRegTypeInfo(uint16_t level, uint32_t typeId, const char* typeName, size_t len) override;
    uint64_t ProfReportGetHashId(const char* info, size_t len) override;
    int32_t ProfSetDeviceIdByGeModelIdx(const uint32_t geModelIdx, const uint32_t deviceId) override;
    int32_t ProfUnSetDeviceIdByGeModelIdx(const uint32_t geModelIdx, const uint32_t deviceId) override;
    int32_t ProfNotifySetDevice(uint32_t chipId, uint32_t deviceId, bool isOpen) override;
    int32_t ProfSetStepInfo(const uint64_t indexId, const uint16_t tagId, void* const stream) override;
    int32_t ProfFinalize() override;
    bool ProfHostFreqIsEnable() override;

    int32_t ProfRegisterReporter(MsprofReportHandle reporter);
    int32_t ProfRegisterCtrl(MsprofCtrlHandle handle);
    int32_t ProfRegisterDeviceNotify(MsprofSetDeviceHandle handle);
    int32_t ProfSetProfCommand(VOID_PTR command, uint32_t len);
    int32_t ProfGetDeviceIdByGeModelIdx(const uint32_t geModelIdx, uint32_t *deviceId);
    int32_t RegisterProfileCallback(int32_t callbackType, VOID_PTR callback, uint32_t len);
protected:
    ProfAtlsPlugin();
private:
    int32_t RegisterProfileCallbackC(int32_t callbackType, VOID_PTR callback);
private:
    MsprofReportHandle reporter_{nullptr};
    MsprofCtrlHandle profCtrl_{nullptr};
    MsprofSetDeviceHandle profSetDevice_{nullptr};
    ProfReportApiFunc profReportApi_{nullptr};
    ProfReportEventFunc profReportEvent_{nullptr};
    ProfReportCompactInfoFunc profReportCompactInfo_{nullptr};
    ProfReportAdditionalInfoFunc profReportAdditionalInfo_{nullptr};
    ProfReportRegTypeInfoFunc profReportRegTypeInfo_{nullptr};
    ProfReportGetHashIdFunc profReportGetHashId_{nullptr};
    ProfHostFreqIsEnableFunc profHostFreqIsEnable_{nullptr};
    ProfReportApiCFunc profReportApiC_{nullptr};
    ProfReportEventCFunc profReportEventC_{nullptr};
    ProfReportRegTypeInfoCFunc profReportRegTypeInfoC_{nullptr};
    ProfReportGetHashIdCFunc profReportGetHashIdC_{nullptr};
    ProfHostFreqIsEnableCFunc profHostFreqIsEnableC_{nullptr};
    std::map<uint32_t, uint32_t> deviceIdMaps_;  // (moduleId, deviceId)
    std::mutex atlasDeviceMapsMutex_;
    std::map<uint64_t, bool> deviceStates_; // id is deviceid << 32 | chipid;
    std::mutex atlasDeviceStateMutex_;
    ProfCommand command_;
};
}
#endif