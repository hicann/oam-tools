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
 
#ifndef ANALYSIS_DVVP_HOST_PROF_TASK_H
#define ANALYSIS_DVVP_HOST_PROF_TASK_H

#include <condition_variable>
#include <memory>
#include <mutex>
#include <queue>
#include "device.h"
#include "queue/bound_queue.h"
#include "thread/thread.h"
#include "uploader.h"
#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace host {
using namespace analysis::dvvp::common::utils;

struct CollectionStartEndTime {
    std::string collectionDateBegin;
    std::string collectionDateEnd;
    std::string collectionTimeBegin;
    std::string collectionTimeEnd;
    std::string clockMonotonicRaw;
};

class ProfTask : public analysis::dvvp::common::thread::Thread {
public:
    ProfTask(const std::vector<std::string> &devices,
             SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> param);
    virtual ~ProfTask();

public:
    int32_t Init();
    int32_t Uinit();
    bool IsDeviceRunProfiling(const std::string &devStr);

public:
    void Run(const struct error_message::Context &errorContext) override;
    int32_t Stop() override;

public:
    int32_t NotifyFileDoneForDevice(const std::string &fileName, const std::string &devId) const;
    int32_t WriteStreamData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunk) const;
    void SetIsFinished(bool finished);
    bool GetIsFinished() const;

private:
    void WriteDone();

private:
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;

    std::vector<std::string> _devices_v;
    std::vector<std::string> currDevicesV_;

    std::mutex taskMtx_;
    std::condition_variable cv_;
    std::mutex devicesMtx_;
    std::map<std::string, SHARED_PTR_ALIA<Device> > devicesMap_;
    bool isInited_;
    SHARED_PTR_ALIA<analysis::dvvp::transport::Uploader> uploader_;
    bool isFinished_;

private:
    int32_t GetHostAndDeviceInfo();
    void GenerateFileName(bool isStartTime, std::string &filename);
    int32_t CreateCollectionTimeInfo(std::string collectionTime, bool isStartTime);
    std::string EncodeTimeInfoJson(SHARED_PTR_ALIA<CollectionStartEndTime> timeInfo) const;
    void StartDevices(const std::vector<std::string> &devicesVec);
    void ProcessDefMode();
    std::string GetDevicesStr(const std::vector<std::string> &events) const;
    void Process(analysis::dvvp::message::StatusInfo &statusInfo);
};
}  // namespace host
}  // namespace dvvp
}  // namespace analysis
#endif
