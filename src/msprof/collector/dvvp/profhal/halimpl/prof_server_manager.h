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

#ifndef PROF_SERVER_MANAGER_H
#define PROF_SERVER_MANAGER_H
#include <cstdint>
#include <unordered_map>
#include "singleton/singleton.h"
#include "prof_hdc_server.h"
#include "prof_helper_server.h"
#include "prof_hal_api.h"

namespace Dvvp {
namespace Hal {
namespace Server {
class ServerManager : public analysis::dvvp::common::singleton::Singleton<ServerManager> {
public:
    ServerManager();
    ~ServerManager() override;
    int32_t ProfServerInit(uint32_t moduleType, const ProfHalModuleConfig *moduleConfig, uint32_t length);
    int32_t ProfServerFinal();
    void SetFlushModuleCallback(const ProfHalFlushModuleCallback func);
    void SetSendAicpuDataCallback(const ProfHalSendAicpuDataCallback func);
    void SetHelperDirCallback(const ProfHalHelperDirCallback func);
    void SetSendHelperDataCallback(const ProfHalSendHelperDataCallback func);

private:
    int32_t ProfAiCpuServerInit(uint32_t devId);
    int32_t ProfHelperServerInit(uint32_t devId);
    std::unordered_map<uint32_t, SHARED_PTR_ALIA<Dvvp::Hal::Server::ProfHdcServer>> hdcDevMap_;
    std::unordered_map<uint32_t, SHARED_PTR_ALIA<Dvvp::Hal::Server::ProfHelperServer>> helperDevMap_;
    std::mutex halMtx_;
};
}
}
}
#endif
