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

#ifndef ANALYSIS_DVVP_HOST_PROF_MANAGER_H
#define ANALYSIS_DVVP_HOST_PROF_MANAGER_H

#include <map>
#include "message/prof_params.h"
#include "prof_task.h"
#include "singleton/singleton.h"
#include "transport/prof_channel.h"
#include "app/application.h"
#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace host {
class ProfManager : public analysis::dvvp::common::singleton::Singleton<ProfManager> {
    friend analysis::dvvp::common::singleton::Singleton<ProfManager>;

public:
    int32_t AclInit();
    int32_t AclUinit();

    int32_t Handle(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);

public:
    SHARED_PTR_ALIA<ProfTask> GetTask(const std::string &jobId);
    int32_t StopTask(const std::string &jobId);
    int32_t OnTaskFinished(const std::string &jobId);
    int32_t WriteCtrlDataToFile(const std::string &absolutePath, const std::string &data, int32_t dataLen) const;
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> HandleProfilingParams(uint32_t deviceId,
        const std::string &sampleConfig) const;
    int32_t IdeCloudProfileProcess(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    bool CheckIfDevicesOnline(const std::string paramsDevices, std::string &statusInfo) const;

protected:
    ProfManager() : isInited_(false)
    {
    }
    ~ProfManager() override
    {
    }

private:
    bool CreateSampleJsonFile(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params,
                              const std::string &resultDir) const;
    bool CheckHandleSuc(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params,
                        analysis::dvvp::message::StatusInfo &statusInfo);
    int32_t ProcessHandleFailed(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;

private:
    int32_t LaunchTask(SHARED_PTR_ALIA<ProfTask> task, const std::string &jobId, std::string &info);
    SHARED_PTR_ALIA<ProfTask> GetTaskNoLock(const std::string &jobId);
    bool IsDeviceProfiling(const std::vector<std::string> &devices);
    bool CreateDoneFile(const std::string &absolutePath, const std::string &fileSize) const;
    bool PreGetDeviceList(std::vector<int32_t> &devIds) const;

private:
    bool isInited_;
    std::mutex taskMtx_;
    std::map<std::string, SHARED_PTR_ALIA<ProfTask> > _tasks;  // taskptr, task
};
}  // namespace host
}  // namespace dvvp
}  // namespace analysis

#endif
