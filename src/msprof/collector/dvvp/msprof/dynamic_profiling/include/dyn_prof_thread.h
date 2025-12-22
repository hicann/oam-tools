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

#ifndef DYNAMIC_PROFILING_THREAD_H
#define DYNAMIC_PROFILING_THREAD_H

#include <mutex>
#include <condition_variable>
#include <chrono>
#include <map>
#include "thread/thread.h"
#include "prof_api.h"
#include "msprof_error_manager.h"
#include "dyn_prof_def.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {

class DynProfThread : public analysis::dvvp::common::thread::Thread {
public:
    DynProfThread();
    ~DynProfThread() override;
 
    int32_t Start() override;
    int32_t Stop() override;
    void Run(const struct error_message::Context &errorContext) override;
    void SaveDevicesInfo(DynProfDeviceInfo data);
    bool IsProfStarted();

private:
    int32_t GetDelayAndDurationTime();
    int32_t StartProfTask();
    int32_t StopProfTask();

private:
    bool started_;
    bool profStarted_;
    uint32_t delayTime_;
    uint32_t durationTime_;
    bool durationSet_;
    std::condition_variable cvThreadStop_;
    std::mutex threadStopMtx_;
    std::map<uint32_t, DynProfDeviceInfo> devicesInfo_;
    std::mutex devInfoMtx_;
    std::string msprofEnvCfg_;
    std::mutex devMtx_;
};
} // DynProf
} // Dvvp
} // Collect
#endif