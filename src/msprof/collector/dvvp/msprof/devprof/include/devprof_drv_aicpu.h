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
#ifndef DEVPROF_DRV_AICPU_H
#define DEVPROF_DRV_AICPU_H

#include "singleton.h"
#include "block_buffer.h"
#include "utils.h"
#include "prof_dev_api.h"
#include "thread/thread.h"

class DevprofDrvAicpu : public analysis::dvvp::common::singleton::Singleton<DevprofDrvAicpu>,
    public analysis::dvvp::common::thread::Thread {
public:
    DevprofDrvAicpu();
    ~DevprofDrvAicpu() override;
    int32_t Init(const struct AicpuStartPara *para);
    int32_t Start() override;
    int32_t Stop() override;
    bool IsRegister(void) const;
    void SetProfConfig(uint64_t profConfig);
    int32_t CheckFeatureIsOn(uint64_t feature) const;
    bool CheckProfilingIsOn(uint64_t profConfig);
    int32_t ReportAdditionalInfo(uint32_t agingFlag, ConstVoidPtr data, uint32_t length);
    size_t GetBatchReportMaxSize(uint32_t type) const;
    int32_t AdprofInit(const AicpuStartPara *para);
    int32_t ModuleRegisterCallback(uint32_t moduleId, ProfCommandHandle commandHandle);
    void DoCallbackHandle(ProfCommandHandle commandHandle);
    void CommandHandleLaunch();
    void DeviceReportStart();
    void DeviceReportStop();
#ifdef __PROF_LLT
    void Reset(void);
#endif

protected:
    void Run(const struct error_message::Context &errorContext) override;

private:
    int32_t RegisterDrvChannel(uint32_t devId, uint32_t channelId);

    volatile bool stopped_;
    uint32_t devId_;
    uint32_t channelId_;
    volatile uint64_t profConfig_;
    bool isRegister_;
    analysis::dvvp::common::queue::BlockBuffer<MsprofAdditionalInfo> aicpuAdditionalBuffer_{};
    MsprofCommandHandle command_;
    std::map<uint32_t, std::set<ProfCommandHandle>> moduleCallbacks_;
};

#endif