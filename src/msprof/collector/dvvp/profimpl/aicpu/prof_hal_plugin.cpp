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

#include "prof_hal_plugin.h"
#include "msprof_dlog.h"
#include "osal.h"
using namespace analysis::dvvp::common::error;
namespace ProfAPI {
const std::string ASCEND_PROF_LIB_PATH = "libascendprofhal.so";

template <class T>
inline T LoadDlsymApi(VOID_PTR hanle, const std::string &name)
{
    return reinterpret_cast<T>(OsalDlsym(hanle, name.c_str()));
}

ProfHalPlugin::~ProfHalPlugin()
{
    if (msProfLibHandle_ != nullptr) {
        OsalDlclose(msProfLibHandle_);
    }
}

/**
 * @name  ProfHalApiInit
 * @brief load prof hal plugin
 */
void ProfHalPlugin::ProfHalApiInit()
{
    if (msProfLibHandle_ == nullptr) {
        msProfLibHandle_ = OsalDlopen(ASCEND_PROF_LIB_PATH.c_str(), OSAL_RTLD_LAZY | RTLD_NODELETE);
    }
    if (msProfLibHandle_ != nullptr) {
        PthreadOnce(&profHalApiLoadFlag_, []()-> void { ProfHalPlugin::instance()->LoadHalApi();});
    } else {
        MSPROF_LOGE("MSPROF API Open Failed, dlopen error: %s\n", OsalDlerror());
    }
    return;
}

void ProfHalPlugin::LoadHalApi()
{
    profHalGetVersion_ = LoadDlsymApi<decltype(profHalGetVersion_)>(msProfLibHandle_, "ProfHalGetVersion");
    profHalInit_ = LoadDlsymApi<decltype(profHalInit_)>(msProfLibHandle_, "ProfHalModuleInitialize");
    profHalFinal_ = LoadDlsymApi<decltype(profHalFinal_)>(msProfLibHandle_, "ProfHalModuleFinalize");
    profHalFlush_ = LoadDlsymApi<decltype(profHalFlush_)>(msProfLibHandle_, "ProfHalSetFlushModuleCallback");
    profHalSendData_ = LoadDlsymApi<decltype(profHalSendData_)>(msProfLibHandle_, "ProfHalSetSendDataCallback");
    profHalHelperDir_ = LoadDlsymApi<decltype(profHalHelperDir_)>(msProfLibHandle_, "ProfHalSetHelperDirCallback");
    profHalSendHelperData_ = LoadDlsymApi<decltype(profHalSendHelperData_)>(msProfLibHandle_,
        "ProfHalSetSendHelperDataCallback");
}

int32_t ProfHalPlugin::ProfHalInit(uint32_t moduleType, const void *moduleConfig, uint32_t length)
{
    ProfHalApiInit();
    if (profHalInit_ != nullptr) {
        return profHalInit_(moduleType, moduleConfig, length);
    }
    return 0;
}

int32_t ProfHalPlugin::ProfHalGetVersion(uint32_t *version) const
{
    if (profHalGetVersion_ != nullptr) {
        return profHalGetVersion_(version);
    }
    return 0;
}

int32_t ProfHalPlugin::ProfHalFinal() const
{
    if (profHalFinal_ != nullptr) {
        return profHalFinal_();
    }
    return 0;
}

void ProfHalPlugin::ProfHalFlushModuleRegister(const ProfHalFlushModuleCallback func) const
{
    if (profHalFlush_ != nullptr) {
        profHalFlush_(func);
    }
}

void ProfHalPlugin::ProfHalSendDataRegister(const ProfHalSendAicpuDataCallback func) const
{
    if (profHalSendData_ != nullptr) {
        profHalSendData_(func);
    }
}

void ProfHalPlugin::ProfHalHelperDirRegister(const ProfHalHelperDirCallback func) const
{
    if (profHalHelperDir_ != nullptr) {
        profHalHelperDir_(func);
    }
}

void ProfHalPlugin::ProfHalSendHelperDataRegister(const ProfHalSendHelperDataCallback func) const
{
    if (profHalSendHelperData_ != nullptr) {
        profHalSendHelperData_(func);
    }
}
}
