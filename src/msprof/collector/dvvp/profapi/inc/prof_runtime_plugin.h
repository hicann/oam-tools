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
#ifndef PROF_RUNTIME_API_H
#define PROF_RUNTIME_API_H
#include <cstdint>
#include <map>
#include "singleton/singleton.h"
#include "prof_utils.h"
#include "acl/acl_base.h"
#include "runtime/base.h"
#include "runtime/kernel.h"
#include "runtime/rt_error_codes.h"

namespace ProfAPI {
using RtProfilerTraceExFunc = rtError_t (*) (uint64_t indexId, uint64_t modelId, uint16_t tagId, rtStream_t stm);

struct RuntimeApiInfo {
    std::string funcName;
    void *funcAddr;
};

class ProfRuntimePlugin : public analysis::dvvp::common::singleton::Singleton<ProfRuntimePlugin> {
public:
    ~ProfRuntimePlugin() override;
    int32_t RuntimeApiInit();
    void *GetPluginApiFunc(const std::string funcName);
    int32_t ProfMarkEx(uint64_t indexId, uint64_t modelId, uint16_t tagId, void *stm);

private:
    void LoadRuntimeApi();

private:
    void *runtimeLibHandle_{nullptr};
    ProfAPI::PTHREAD_ONCE_T runtimeApiloadFlag_;
    std::map<std::string, RuntimeApiInfo> runtimeApiInfoMap_{};
};
}
#endif