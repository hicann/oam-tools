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
#ifndef ANALYSIS_DVVP_PROFILER_COMMAND_HANDLE_H
#define ANALYSIS_DVVP_PROFILER_COMMAND_HANDLE_H

#include <cstdint>
#include <map>
#include <set>
#include "acl/acl_base.h"
#include "utils/utils.h"
#include "prof_api.h"
#include "prof_common.h"

namespace Analysis {
namespace Dvvp {
namespace ProfilerCommon {
using ProfCommand = MsprofCommandHandle;
constexpr uint32_t PROF_INVALID_MODE_ID = 0xFFFFFFFFUL;
int32_t CommandHandleProfInit();
int32_t CommandHandleProfStart(const uint32_t devIdList[], uint32_t devNums, uint64_t profSwitch,
                               uint64_t profSwitchHi);
int32_t CommandHandleProfStop(const uint32_t devIdList[], uint32_t devNums, uint64_t profSwitch, uint64_t profSwitchHi);
int32_t CommandHandleProfFinalize();
int32_t CommandHandleProfUnSubscribe(uint32_t modelId);
void CommandHandleFinalizeGuard();
int32_t ProfRegisterCallback(uint32_t moduleId, ProfCommandHandle callback);

class ProfModuleReprotMgr {
public:
    static ProfModuleReprotMgr &GetInstance()
    {
        static ProfModuleReprotMgr mgr;
        return mgr;
    }
    void DoCallbackHandle(ProfCommandHandle callback);
    int32_t ModuleRegisterCallback(uint32_t moduleId, ProfCommandHandle callback);
    int32_t ModuleReportInit();
    int32_t ModuleReportStart(const uint32_t devIdList[], uint32_t devNums, uint64_t profSwitch,
                              uint64_t profSwitchHi);
    int32_t ModuleReportStop(const uint32_t devIdList[], uint32_t devNums, uint64_t profSwitch, uint64_t profSwitchHi);
    int32_t ModuleReportFinalize();
    int32_t ModuleReportUnSubscribe(uint32_t modelId);
    int32_t ProfSetProCommand(ProfCommand &command);
    void ProfSetFinalizeGuard();

private:
    ProfModuleReprotMgr() : finalizeGuard_(false)
    {
        command_.type = PROF_COMMANDHANDLE_TYPE_MAX;
    }
    ~ProfModuleReprotMgr();
    int32_t SetCommandHandleProf(ProfCommand &command) const;
    void ProcessDeviceList(ProfCommand &command, const uint32_t devIdList[], uint32_t devNums) const;

    std::mutex regCallback_;
    ProfCommand command_;
    std::map<uint32_t, std::set<ProfCommandHandle>> moduleCallbacks_;
    bool finalizeGuard_;
};
}  // namespace ProfilerCommon
}  // namespace Dvvp
}  // namespace Analysis

#endif
