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
#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_PERF_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_PERF_H
#include "prof_comm_job.h"
#include "message/message.h"
#include "memory/chunk_pool.h"
#include "thread/thread.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
class PerfExtraTask : public analysis::dvvp::common::thread::Thread {
public:
    PerfExtraTask(uint32_t bufSize, const std::string &retDir,
                  SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx,
                  SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> param);
    ~PerfExtraTask() override;
    void SetJobCtx(SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx);
    int32_t Init();
    int32_t UnInit();

private:
    void Run(const struct error_message::Context &errorContext) override;
    void PerfScriptTask();
    void ResolvePerfRecordData(const std::string &fileName) const;
    void StoreData(const std::string &fileName);

private:
    volatile bool isInited_;
    long long dataSize_;
    std::string retDir_;
    analysis::dvvp::common::memory::Chunk buf_;
    SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx_;
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> param_;
};

class ProfCtrlcpuJob : public ICollectionJob {
public:
    ProfCtrlcpuJob();
    ~ProfCtrlcpuJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
    bool IsGlobalJobLevel() override
    {
        return true;
    }
private:
    int32_t GetCollectCtrlCpuEventCmd(const std::vector<std::string> &events, std::string &profCtrlcpuCmd);
    int32_t PrepareDataDir(std::string &cpuDataFile);

private:
    OsalProcess ctrlcpuProcess_;
    SHARED_PTR_ALIA<CollectionJobCfg> collectionJobCfg_;
    SHARED_PTR_ALIA<PerfExtraTask> perfExtraTask_;
};

class ProfAicpuHscbJob : public ProfPeripheralJob {
public:
    ProfAicpuHscbJob();
    ~ProfAicpuHscbJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
 
private:
    int32_t GetAicpuHscbCmd(int32_t devId, const std::vector<std::string> &events,
        std::string &hscbCmd) const;
    void SendData() const;
    void SendPerfTimeData() const;
 
private:
    OsalProcess hscbProcess_;
    SHARED_PTR_ALIA<CollectionJobCfg> collectionJobCfg_;
    uint64_t deviceMonotonic_;
    uint64_t deviceSysCnt_;
};
}
}
}

#endif