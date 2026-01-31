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
#include <ctime>
#include "prof_avp_plugin.h"
#include "msprof_dlog.h"
#include "errno/error_code.h"
#include "prof_api.h"

#ifdef __cplusplus
extern "C" {
#endif  // __cplusplus

MSVP_PROF_API int32_t MsprofInit(uint32_t dataType, void *data, uint32_t dataLen)
{
    return ProfAPI::ProfAvpPlugin::instance()->ProfInit(dataType, data, dataLen);
}

MSVP_PROF_API int32_t MsprofFinalize()
{
    return ProfAPI::ProfAvpPlugin::instance()->ProfFinalize();
}

MSVP_PROF_API int32_t MsprofNotifySetDevice(uint32_t chipId, uint32_t deviceId, bool isOpen)
{
    return ProfAPI::ProfAvpPlugin::instance()->ProfNotifySetDevice(chipId, deviceId, isOpen);
}

MSVP_PROF_API int32_t MsprofRegisterCallback(uint32_t moduleId, ProfCommandHandle handle)
{
    return ProfAPI::ProfAvpPlugin::instance()->ProfRegisterCallback(moduleId, handle);
}

MSVP_PROF_API int32_t MsprofReportEvent(uint32_t nonPersistantFlag, const MsprofEvent *event)
{
    if (event == nullptr) {
        MSPROF_LOGE("MsprofReportEvent interface input invalid data.");
        return analysis::dvvp::common::error::PROFILING_FAILED;
    }
    return ProfAPI::ProfAvpPlugin::instance()->ProfReportEvent(nonPersistantFlag, *event);
}

MSVP_PROF_API int32_t MsprofReportApi(uint32_t nonPersistantFlag, const MsprofApi *api)
{
    if (api == nullptr) {
        MSPROF_LOGE("MsprofReportApi interface input invalid data.");
        return analysis::dvvp::common::error::PROFILING_FAILED;
    }
    return ProfAPI::ProfAvpPlugin::instance()->ProfReportApi(nonPersistantFlag, *api);
}

MSVP_PROF_API int32_t MsprofReportCompactInfo(uint32_t nonPersistantFlag, const VOID_PTR data, uint32_t length)
{
    if (data == nullptr) {
        MSPROF_LOGE("MsprofReportCompactInfo interface input invalid data.");
        return analysis::dvvp::common::error::PROFILING_FAILED;
    }
    return ProfAPI::ProfAvpPlugin::instance()->ProfReportCompactInfo(nonPersistantFlag, data, length);
}

MSVP_PROF_API int32_t MsprofReportAdditionalInfo(uint32_t nonPersistantFlag, const VOID_PTR data, uint32_t length)
{
    if (data == nullptr) {
        MSPROF_LOGE("MsprofReportAdditionalInfo interface input invalid data.");
        return analysis::dvvp::common::error::PROFILING_FAILED;
    }
    return ProfAPI::ProfAvpPlugin::instance()->ProfReportAdditionalInfo(nonPersistantFlag, data, length);
}

MSVP_PROF_API int32_t MsprofRegTypeInfo(uint16_t level, uint32_t typeId, const char *typeName)
{
    if (typeName == nullptr) {
        return analysis::dvvp::common::error::PROFILING_FAILED;
    }
    return ProfAPI::ProfAvpPlugin::instance()->ProfReportRegTypeInfo(level, typeId, typeName);
}

MSVP_PROF_API uint64_t MsprofGetHashId(const char *hashInfo, size_t length)
{
    if (hashInfo == nullptr || length == 0) {
        MSPROF_LOGW("The hashInfo[%zu] is invalid, thus unable to get hash id.", length);
        return std::numeric_limits<uint64_t>::max();
    }
    return ProfAPI::ProfAvpPlugin::instance()->ProfReportGetHashId(hashInfo, length);
}

MSVP_PROF_API uint64_t MsprofSysCycleTime()
{
    return ProfAPI::ProfAvpPlugin::instance()->ProfSysCycleTime();
}

#ifdef __cplusplus
}
#endif