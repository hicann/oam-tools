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

#include "prof_aicpu_api.h"
#include "prof_hal_plugin.h"

#ifdef __cplusplus
extern "C" {
#endif // __cplusplus

/* AICPU API */
MSVP_PROF_API int32_t ProfHalGetVersion(uint32_t *version)
{
    return ProfAPI::ProfHalPlugin::instance()->ProfHalGetVersion(version);
}

MSVP_PROF_API int32_t ProfHalModuleInitialize(uint32_t moduleType, const void *moduleConfig, uint32_t length)
{
    return ProfAPI::ProfHalPlugin::instance()->ProfHalInit(moduleType, moduleConfig, length);
}

MSVP_PROF_API int32_t ProfHalModuleFinalize()
{
    return ProfAPI::ProfHalPlugin::instance()->ProfHalFinal();
}

MSVP_PROF_API void ProfHalSetFlushModuleCallback(const ProfHalFlushModuleCallback func)
{
    ProfAPI::ProfHalPlugin::instance()->ProfHalFlushModuleRegister(func);
}

MSVP_PROF_API void ProfHalSetSendDataCallback(const ProfHalSendAicpuDataCallback func)
{
    ProfAPI::ProfHalPlugin::instance()->ProfHalSendDataRegister(func);
}

MSVP_PROF_API void ProfHalSetHelperDirCallback(const ProfHalHelperDirCallback func)
{
    ProfAPI::ProfHalPlugin::instance()->ProfHalHelperDirRegister(func);
}

MSVP_PROF_API void ProfHalSetSendHelperDataCallback(const ProfHalSendHelperDataCallback func)
{
    ProfAPI::ProfHalPlugin::instance()->ProfHalSendHelperDataRegister(func);
}
#ifdef __cplusplus
}
#endif
