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
#include "prof_hal_api.h"
#include "msprof_dlog.h"
#include "prof_server_manager.h"

using namespace analysis::dvvp::common::error;
namespace {
    const uint32_t ASCEND_PROF_MAJOR_VERSION_SHIFT = 16;
    const uint32_t ASCEND_PROF_MINOR_VERSION_SHIFT = 8;
}

extern "C" int32_t ProfHalGetVersion(uint32_t *version)
{
    if (version == nullptr) {
        MSPROF_LOGE("Invalid input version of ProfHalGetVersion");
        return PROFILING_FAILED;
    }

    *version = (ASCEND_PROF_MAJOR_VERSION << ASCEND_PROF_MAJOR_VERSION_SHIFT) +
        (ASCEND_PROF_MINOR_VERSION << ASCEND_PROF_MINOR_VERSION_SHIFT) +
        ASCEND_PROF_PATCH_VERSION;
    return PROFILING_SUCCESS;
}

extern "C" int32_t ProfHalModuleInitialize(uint32_t moduleType, const void *moduleConfig, uint32_t length)
{
    if (moduleConfig == nullptr) {
        MSPROF_LOGE("Invalid input moduleConfig of ProfHalModuleInitialize");
        return PROFILING_FAILED;
    }

    return Dvvp::Hal::Server::ServerManager::instance()->ProfServerInit(
        moduleType, reinterpret_cast<const ProfHalModuleConfig *>(moduleConfig), length);
}

extern "C" int32_t ProfHalModuleFinalize()
{
    return Dvvp::Hal::Server::ServerManager::instance()->ProfServerFinal();
}

extern "C" void ProfHalSetFlushModuleCallback(const ProfHalFlushModuleCallback func)
{
    Dvvp::Hal::Server::ServerManager::instance()->SetFlushModuleCallback(func);
}

extern "C" void ProfHalSetSendDataCallback(const ProfHalSendAicpuDataCallback func)
{
    Dvvp::Hal::Server::ServerManager::instance()->SetSendAicpuDataCallback(func);
}

extern "C" void ProfHalSetHelperDirCallback(const ProfHalHelperDirCallback func)
{
    Dvvp::Hal::Server::ServerManager::instance()->SetHelperDirCallback(func);
}

extern "C" void ProfHalSetSendHelperDataCallback(const ProfHalSendHelperDataCallback func)
{
    Dvvp::Hal::Server::ServerManager::instance()->SetSendHelperDataCallback(func);
}
