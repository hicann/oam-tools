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
#include "dyn_prof_mgr.h"
#include "utils/utils.h"
#include "errno/error_code.h"
#include "msprof_dlog.h"
#include "config.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;

DynProfMgr::DynProfMgr() : isStarted_(false)
{
}

DynProfMgr::~DynProfMgr()
{
    StopDynProf();
}

/**
 * @brief Start dynamic profiling task by environment(dynamic start/stop; delay/dutation)
 * @return PROFILING_SUCCESS
 *         PROFILING_FAILED
 */
int32_t DynProfMgr::StartDynProf()
{
    std::lock_guard<std::mutex> lk(startMtx_);
    if (isStarted_) {
        MSPROF_LOGI("Dynamic profiling task has been started");
        return PROFILING_SUCCESS;
    }
    MSPROF_EVENT("Start dynamic profiling task");
    std::string dynProfModeEnv;
    MSPROF_GET_ENV(MM_ENV_PROFILING_MODE, dynProfModeEnv);
    // msprofbin set dynamic, create server and interact with client
    if (dynProfModeEnv == DYNAMIC_PROFILING_VALUE) {
        (void)signal(SIGPIPE, SIG_IGN);
        MSVP_MAKE_SHARED0(dynProfSrv_, DynProfServer, return PROFILING_FAILED);
        if (dynProfSrv_->Start() != PROFILING_SUCCESS) {
            MSPROF_LOGE("Dynamic profiling start server fail");
            dynProfSrv_.reset();
            return PROFILING_FAILED;
        }
    // msprofbin set delay_or_duration, create thread using delay and duration
    } else if (dynProfModeEnv == DELAY_DURARION_PROFILING_VALUE) {
        MSVP_MAKE_SHARED0(dynProfThread_, DynProfThread, return PROFILING_FAILED);
        if (dynProfThread_->Start() != PROFILING_SUCCESS) {
            MSPROF_LOGE("Dynamic profiling start thread fail");
            dynProfThread_.reset();
            return PROFILING_FAILED;
        }
    } else {
        MSPROF_LOGE("PROFILING_MODE: %s is invalid, will not start dynamic profiling task", dynProfModeEnv.c_str());
        return PROFILING_FAILED;
    }
    isStarted_ = true;
    return PROFILING_SUCCESS;
}

/**
 * @brief Stop dynamic profiling task
 */
void DynProfMgr::StopDynProf()
{
    std::lock_guard<std::mutex> lk(startMtx_);
    if (!isStarted_) {
        MSPROF_LOGI("Dynamic profiling task has not been started");
        return;
    }
    if (dynProfSrv_ != nullptr) {
        dynProfSrv_->Stop();
    } else if (dynProfThread_ != nullptr) {
        dynProfThread_->Stop();
    }
    isStarted_ = false;
    MSPROF_EVENT("Dynamic profiling task stoped");
}

/**
 * @brief Save device information when user set device
 * @param [in] chipId: running type(dc, milan ...)
 * @param [in] devId: device id
 * @param [in] isOpenDevice: if device set open
 */
void DynProfMgr::SaveDevicesInfo(uint32_t chipId, uint32_t devId, bool isOpenDevice)
{
    DynProfDeviceInfo data;
    data.chipId = chipId;
    data.devId = devId;
    data.isOpenDevice = isOpenDevice;
    if (dynProfSrv_ != nullptr) {
        dynProfSrv_->SaveDevicesInfo(data);
    } else if (dynProfThread_ != nullptr) {
        dynProfThread_->SaveDevicesInfo(data);
    } else {
        MSPROF_LOGW("Dynamic profiling not start, maybe MsprofInit has not called");
    }
}

/**
 * @brief Save device information when user set device with startMtx_
 * @param [in] chipId: running type(dc, milan ...)
 * @param [in] devId: device id
 * @param [in] isOpenDevice: if device set open
 */
void DynProfMgr::SaveDevicesInfoSecurity(uint32_t chipId, uint32_t devId, bool isOpenDevice)
{
    std::lock_guard<std::mutex> lk(startMtx_);
    SaveDevicesInfo(chipId, devId, isOpenDevice);
}

/**
 * @brief Check if dynamic profiling thread start
 * @return true
           false
 */
bool DynProfMgr::IsDynStarted()
{
    std::lock_guard<std::mutex> lk(startMtx_);
    return isStarted_;
}

/**
 * @brief Check if dynamic profiling task start
 * @return true
           false
 */
bool DynProfMgr::IsProfStarted() const
{
    if (dynProfSrv_ != nullptr) {
        return dynProfSrv_->IsProfStarted();
    } else if (dynProfThread_ != nullptr) {
        return dynProfThread_->IsProfStarted();
    }
    return false;
}
} // DynProf
} // Dvvp
} // Collect