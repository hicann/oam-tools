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
#include "singleton/singleton.h"
#include "prof_utils.h"

namespace ProfRtAPI {
using VOID_PTR = void *;
using RtGetVisibleDeviceIdByLogicDeviceIdFunc = int32_t (*) (int32_t logicDeviceId, int32_t* visibleDeviceId);

class ExtendPlugin : public analysis::dvvp::common::singleton::Singleton<ExtendPlugin> {
public:
    void RuntimeApiInit();
    int32_t ProfGetVisibleDeviceIdByLogicDeviceId(int32_t logicDeviceId, int32_t* visibleDeviceId) const;
    ~ExtendPlugin() override;
private:
    VOID_PTR msRuntimeLibHandle_{nullptr};
    ProfAPI::PTHREAD_ONCE_T loadFlag_;
    RtGetVisibleDeviceIdByLogicDeviceIdFunc rtGetVisibleDeviceIdByLogicDeviceId_{nullptr};
private:
    void LoadProfApi();
};
}
#endif