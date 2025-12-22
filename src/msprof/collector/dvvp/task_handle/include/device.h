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
 
#ifndef ANALYSIS_DVVP_HOST_DEVICE_H
#define ANALYSIS_DVVP_HOST_DEVICE_H

#include <condition_variable>
#include <memory>
#include <mutex>
#include "ai_drv_dev_api.h"
#include "job_adapter.h"
#include "message/prof_params.h"
#include "thread/thread.h"
#include "transport/transport.h"

namespace analysis {
namespace dvvp {
namespace host {
using DeviceCallback = void (*) (int32_t devId);
class Device : public analysis::dvvp::common::thread::Thread {
public:
    Device(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, const std::string &devId);
    virtual ~Device();

public:
    void Run(const struct error_message::Context &errorContext) override;
    int32_t Stop() override;
    int32_t Wait();
    void PostStopReplay();
    const SHARED_PTR_ALIA<analysis::dvvp::message::StatusInfo> GetStatus();
    int32_t Init();
    int32_t SetResponseCallback(DeviceCallback callback);

private:
    int32_t InitJobAdapter();
    void WaitStopReplay();

private:
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;
    // for host app/training, devId from Constructor is phyId
    // for device app, devId from Constructor is phyId(on host), indexId(on device)
    std::string indexIdStr_;     // devId from Constructor
    int32_t indexId_;
    int32_t hostId_;
    bool isQuited_;
    // sync start/stop
    std::mutex mtx_;
    bool isStopReplayReady_;
    std::condition_variable cvSyncStopReplay;
    // store result
    SHARED_PTR_ALIA<analysis::dvvp::message::StatusInfo> status_;
    // init
    bool isInited_;
    DeviceCallback deviceResponseCallack_;
    SHARED_PTR_ALIA<Analysis::Dvvp::JobWrapper::JobAdapter> jobAdapter_;
};
}  // namespace host
}  // namespace dvvp
}  // namespace analysis

#endif
