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

#ifndef PROF_HDC_SERVER_H
#define PROF_HDC_SERVER_H

#include <string>
#include <future>
#include "utils.h"
#include "transport/hdc/adx_transport.h"
#include "thread/thread.h"
#include "prof_hal_api.h"

namespace Dvvp {
namespace Hal {
namespace Server {
using CONST_VOID_PTR = const void *;
class ProfHdcServer : public analysis::dvvp::common::thread::Thread {
public:
    ProfHdcServer();
    ~ProfHdcServer() override;
    int32_t Init(const int32_t logicDevId);
    int32_t UnInit();
    void Run(const struct error_message::Context &errorContext) override;
    void SetFlushModuleCallback(const ProfHalFlushModuleCallback func)
    {
        flushModuleCallback_ = func;
    }
    void SetSendAicpuDataCallback(const ProfHalSendAicpuDataCallback func)
    {
        sendAicpuDataCallback_ = func;
    }
    void SetHelperDirCallback(const ProfHalHelperDirCallback func)
    {
        setHelperDirCallback_ = func;
    }

private:
    int32_t ReceiveStreamData(CONST_VOID_PTR data, uint32_t dataLen);
    bool dataInitialized_;
    int32_t logicDevId_;
    std::vector<SHARED_PTR_ALIA<analysis::dvvp::transport::AdxTransport>> dataTran_;
    HDC_SERVER server_;
    std::string logicDevIdStr_;
    ProfHalFlushModuleCallback flushModuleCallback_;
    ProfHalSendAicpuDataCallback sendAicpuDataCallback_;
    ProfHalHelperDirCallback setHelperDirCallback_;
    std::vector<std::future<int32_t>> result_;
};
}
}
}
#endif
