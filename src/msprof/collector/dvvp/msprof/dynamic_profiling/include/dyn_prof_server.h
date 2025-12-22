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

#ifndef COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_SERVER_H
#define COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_SERVER_H

#include <cstdint>
#include <map>
#include <string>
#include <mutex>
#include "dyn_prof_def.h"
#include "thread/thread.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {
class DynProfServer : public analysis::dvvp::common::thread::Thread {
public:
    DynProfServer() = default;
    ~DynProfServer() override = default;

    int32_t Start() override;
    int32_t Stop() override;
    bool IsProfStarted();
    void SaveDevicesInfo(DynProfDeviceInfo data);

protected:
    void Run(const struct error_message::Context &errorContext) override;

private:
    void DynProfSrvInitProcFunc();
    int32_t DynProfSrvCreate();
    int32_t DynProfSrvRecvParams();
    void DynProfSrvRsqMsg(DynProfMsgType type, DynProfMsgRsqCode rsqCode) const;
    void DynProfSrvProc() const;
    void DynProfSrvProcStart();
    void DynProfSrvProcStop();
    void DynProfSrvProcQuit();

    int32_t srvSockFd_ { -1 };
    int32_t cliSockFd_ { -1 };
    bool srvStarted_ { false };
    bool profStarted_ { false };
    std::string dynProfParams_;
    std::map<DynProfMsgType, ProcFunc> procFuncMap_;
    std::map<uint32_t, DynProfDeviceInfo> devicesInfo_;
    std::mutex devInfoMtx_;
    std::mutex devMtx_;
};
} // namespace DynProf
} // namespace Dvvp
} // namespace Collector

#endif