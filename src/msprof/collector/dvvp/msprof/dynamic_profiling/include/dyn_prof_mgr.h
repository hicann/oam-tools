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
#ifndef DYNAMIC_PROFILING_MANAGER_H
#define DYNAMIC_PROFILING_MANAGER_H

#include <string>
#include <mutex>
#include "singleton/singleton.h"
#include "dyn_prof_server.h"
#include "dyn_prof_thread.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {
using namespace analysis::dvvp::common::thread;

class DynProfMgr : public analysis::dvvp::common::singleton::Singleton<DynProfMgr> {
public:
    DynProfMgr();
    ~DynProfMgr() override;
public:
    int32_t StartDynProf();
    void StopDynProf();
    void SaveDevicesInfo(uint32_t chipId, uint32_t devId, bool isOpenDevice);
    void SaveDevicesInfoSecurity(uint32_t chipId, uint32_t devId, bool isOpenDevice);
    bool IsDynStarted();
    bool IsProfStarted() const;

private:
    bool isStarted_;
    std::mutex startMtx_;
    SHARED_PTR_ALIA<DynProfServer> dynProfSrv_;
    SHARED_PTR_ALIA<DynProfThread> dynProfThread_;
};
} // DynProf
} // Dvvp
} // Collect
#endif