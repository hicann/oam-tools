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
#ifndef COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_CLIENT_H
#define COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_CLIENT_H

#include <cstdint>
#include <functional>
#include <map>
#include "dyn_prof_def.h"
#include "thread/thread.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {
enum class DynProfCliCmd {
    DYN_PROF_CLI_CMD_START = 0,
    DYN_PROF_CLI_CMD_STOP,
    DYN_PROF_CLI_CMD_QUIT,
    DYN_PROF_CLI_CMD_HELP,
    DYN_PROF_CLI_CMD_UNKNOW
};

class DynProfClient : public analysis::dvvp::common::thread::Thread {
public:
    DynProfClient() = default;
    ~DynProfClient() override = default;

    void SetParams(const std::string &params);
    int32_t Start() override;
    int32_t Stop() override;
    bool IsCliStarted() const;

protected:
    void Run(const struct error_message::Context &errorContext) override;

private:
    void DynProfCliInitProcFunc();
    int32_t DynProfCliCreate();
    int32_t DynProfCliSendParams() const;

    DynProfMsgRsqCode DynProfCliSendCmd(DynProfMsgType req) const;
    void DynProfCliProcStart() const;
    void DynProfCliProcStop() const;
    void DynProfCliProcQuit() const;
    void DynProfCliHelpInfo() const;

    int32_t cliSockFd_ { -1 };
    bool cliStarted_ { false };
    std::string dynProfParams_;
    std::map<DynProfCliCmd, ProcFunc> procFuncMap_;
};

class DynProfCliMgr : public analysis::dvvp::common::singleton::Singleton<DynProfCliMgr> {
    friend analysis::dvvp::common::singleton::Singleton<DynProfCliMgr>;

public:
    ~DynProfCliMgr() override;
    int32_t StartDynProfCli(const std::string &params);
    void StopDynProfCli();
    void SetKeyPid(int32_t pid);
    int32_t GetKeyPid() const;
    std::string GetKeyPidEnv() const;
    void EnableDynProfCli();
    bool IsDynProfCliEnable() const;
    std::string GetDynProfEnv() const;
    void SetAppMode();
    bool IsAppMode() const;
    bool IsCliStarted() const;
    void WaitQuit();

private:
    DynProfCliMgr() = default;
    bool enabled_ { false };
    bool isAppMode_ { false }; // --application
    int32_t keyPid_ { 0 };         // --application: msprofbin pid; --pid: app pid
    SHARED_PTR_ALIA<Collector::Dvvp::DynProf::DynProfClient> dynProfCli_;
};
} // namespace DynProf
} // namespace Dvvp
} // namespace Collector

#endif