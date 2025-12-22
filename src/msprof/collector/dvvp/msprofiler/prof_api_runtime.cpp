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

#include "prof_api_runtime.h"
#include <dlfcn.h>
#include "msprof_dlog.h"
#include "errno/error_code.h"

namespace ProfRtAPI {
using namespace analysis::dvvp::common::error;
const std::string RUNTIME_LIB_PATH = "libruntime.so";

ExtendPlugin::~ExtendPlugin()
{
    if (msRuntimeLibHandle_ != nullptr) {
        dlclose(msRuntimeLibHandle_);
    }
}

void ExtendPlugin::RuntimeApiInit()
{
    if (msRuntimeLibHandle_ == nullptr) {
        msRuntimeLibHandle_ = dlopen(RUNTIME_LIB_PATH.c_str(), RTLD_NOW | RTLD_GLOBAL | RTLD_NODELETE);
    }
    if (msRuntimeLibHandle_ != nullptr) {
        ProfAPI::PthreadOnce(&loadFlag_, []() -> void { ExtendPlugin::instance()->LoadProfApi(); });
    } else {
        MSPROF_LOGE("RUNTIME API Open Failed, dlopen error: %s\n", dlerror());
    }
    return;
}

void ExtendPlugin::LoadProfApi()
{
    do {
        rtGetVisibleDeviceIdByLogicDeviceId_ = reinterpret_cast<RtGetVisibleDeviceIdByLogicDeviceIdFunc>(
            dlsym(msRuntimeLibHandle_, "rtGetVisibleDeviceIdByLogicDeviceId"));
    } while (0);
}

int32_t ExtendPlugin::ProfGetVisibleDeviceIdByLogicDeviceId(int32_t logicDeviceId,
    int32_t* visibleDeviceId) const
{
    if (rtGetVisibleDeviceIdByLogicDeviceId_ == nullptr) {
        MSPROF_LOGW("RuntimePlugin rtGetVisibleDeviceIdByLogicDeviceId function is null.");
        return PROFILING_NOTSUPPORT;
    }
    return rtGetVisibleDeviceIdByLogicDeviceId_(logicDeviceId, visibleDeviceId);
}

}