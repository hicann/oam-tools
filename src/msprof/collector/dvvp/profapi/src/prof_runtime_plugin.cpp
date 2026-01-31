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
#include "prof_runtime_plugin.h"
#include <dlfcn.h>
#include "msprof_dlog.h"
#include "errno/error_code.h"
#include "prof_api.h"
#include "utils/utils.h"

namespace ProfAPI {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;

const std::string RUNTIME_LIB_PATH = "libruntime.so";

static std::set<std::string> g_runtimeApiSet = {
    "rtProfilerTraceEx"
};

ProfRuntimePlugin::~ProfRuntimePlugin()
{
    if (runtimeLibHandle_ != nullptr) {
        dlclose(runtimeLibHandle_);
    }
}

void ProfRuntimePlugin::LoadRuntimeApi()
{
    for (auto &it : g_runtimeApiSet) {
        auto addr = dlsym(runtimeLibHandle_, it.c_str());
        if (addr == nullptr) {
            MSPROF_LOGW("Unable to load api[%s] from %s.", it.c_str(), RUNTIME_LIB_PATH.c_str());
            continue;
        }
        MSPROF_LOGI("Load api[%s] from %s successfully.", it.c_str(), RUNTIME_LIB_PATH.c_str());
        runtimeApiInfoMap_.insert({it, {it, addr}});
    }
}

int32_t ProfRuntimePlugin::RuntimeApiInit()
{
    if (runtimeLibHandle_ == nullptr) {
        MSPROF_LOGD("Init api handle from %s", RUNTIME_LIB_PATH.c_str());
        runtimeLibHandle_ = dlopen(RUNTIME_LIB_PATH.c_str(), RTLD_NOW | RTLD_GLOBAL | RTLD_NODELETE);
    }
    if (runtimeLibHandle_ == nullptr) {
        MSPROF_LOGW("Unable to dlopen api from %s, return code: %s\n", RUNTIME_LIB_PATH.c_str(), dlerror());
        return PROFILING_FAILED;
    }
    ProfAPI::PthreadOnce(&runtimeApiloadFlag_, []() -> void { ProfRuntimePlugin::instance()->LoadRuntimeApi(); });
    return PROFILING_SUCCESS;
}

void *ProfRuntimePlugin::GetPluginApiFunc(const std::string funcName)
{
    auto it = runtimeApiInfoMap_.find(funcName);
    if (it == runtimeApiInfoMap_.cend()) {
        MSPROF_LOGE("Can't find api %s", funcName.c_str());
        return nullptr;
    }

    return it->second.funcAddr;
}

int32_t ProfRuntimePlugin::ProfMarkEx(uint64_t indexId, uint64_t modelId, uint16_t tagId, void *stm)
{
    auto func = GetPluginApiFunc("rtProfilerTraceEx");
    if (func == nullptr) {
        MSPROF_LOGE("Failed to get api stub[rtProfilerTraceEx] func.");
        return PROFILING_FAILED;
    }
    rtError_t ret = reinterpret_cast<RtProfilerTraceExFunc>(func)(indexId, modelId, tagId,
        static_cast<rtStream_t>(stm));
    if (ret != RT_ERROR_NONE) {
        MSPROF_LOGE("Failed to call rtProfilerTraceEx, ret: %d.", ret);
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}
}