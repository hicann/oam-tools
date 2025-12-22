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

#ifndef PROF_HAL_PLUGIN_H
#define PROF_HAL_PLUGIN_H
#include <cstdint>
#include "singleton/singleton.h"
#include "prof_utils.h"
#include "prof_hal_api.h"

namespace ProfAPI {
using VOID_PTR = void *;
using CONST_VOID_PTR = const void *;

using ProfHalInitFunc = int32_t (*) (uint32_t moduleType, const void *moduleConfig, uint32_t length);
using ProfHalGetVersionFunc = int32_t (*) (uint32_t *version);
using ProfHalFinalFunc = int32_t (*) ();
using ProfHalFlushModuleFunc = void (*) (const ProfHalFlushModuleCallback func);
using ProfHalSendDataFunc = int32_t (*) (const ProfHalSendAicpuDataCallback func);
using ProfHalHelperDirFunc = int32_t (*) (const ProfHalHelperDirCallback func);
using ProfHalSendHelperDataFunc = int32_t (*) (const ProfHalSendHelperDataCallback func);

class ProfHalPlugin : public analysis::dvvp::common::singleton::Singleton<ProfHalPlugin> {
public:
    ~ProfHalPlugin() override;
    void ProfHalApiInit();
    int32_t ProfHalInit(uint32_t moduleType, const void *moduleConfig, uint32_t length);
    int32_t ProfHalGetVersion(uint32_t *version) const;
    int32_t ProfHalFinal() const;
    void ProfHalFlushModuleRegister(const ProfHalFlushModuleCallback func) const;
    void ProfHalSendDataRegister(const ProfHalSendAicpuDataCallback func) const;
    void ProfHalHelperDirRegister(const ProfHalHelperDirCallback func) const;
    void ProfHalSendHelperDataRegister(const ProfHalSendHelperDataCallback func) const;

private:
    void LoadHalApi();
    VOID_PTR msProfLibHandle_{nullptr};
    PTHREAD_ONCE_T profHalApiLoadFlag_;

    ProfHalInitFunc profHalInit_;
    ProfHalGetVersionFunc profHalGetVersion_;
    ProfHalFinalFunc profHalFinal_;
    ProfHalFlushModuleFunc profHalFlush_;
    ProfHalSendDataFunc profHalSendData_;
    ProfHalHelperDirFunc profHalHelperDir_;
    ProfHalSendHelperDataFunc profHalSendHelperData_;
};
}
#endif
