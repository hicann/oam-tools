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

#ifndef PROF_HELPER_SERVER_H
#define PROF_HELPER_SERVER_H

#include <string>
#include <future>
#include "utils.h"
#include "transport/hdc/adx_transport.h"
#include "thread/thread.h"
#include "prof_hal_api.h"
#include "transport/hdc/helper_transport.h"

namespace Dvvp {
namespace Hal {
namespace Server {
using CONST_VOID_PTR = const void *;
class ProfHelperServer : public analysis::dvvp::common::thread::Thread {
public:
    ProfHelperServer();
    ~ProfHelperServer() override;
    int32_t Init(const int32_t logicDevId);
    int32_t UnInit();
    void Run(const struct error_message::Context &errorContext) override;
    void SetFlushModuleCallback(const ProfHalFlushModuleCallback func)
    {
        flushModuleCallback_ = func;
    }
    void SetSendHelperDataCallback(const ProfHalSendHelperDataCallback func)
    {
        sendHelperDataCallback_ = func;
    }
    void SetHelperDirCallback(const ProfHalHelperDirCallback func)
    {
        setHelperDirCallback_ = func;
    }

private:
    int32_t ReceiveStreamData(CONST_VOID_PTR data, uint32_t dataLen);
    int32_t PackSampleJsonFile(std::string id, const ProfHalStruct *message);
    bool dataInitialized_;
    int32_t logicDevId_;
    std::vector<SHARED_PTR_ALIA<analysis::dvvp::transport::HelperTransport>> dataTran_;
    HDC_SERVER server_;
    std::string logicDevIdStr_;
    ProfHalFlushModuleCallback flushModuleCallback_;
    ProfHalSendHelperDataCallback sendHelperDataCallback_;
    ProfHalHelperDirCallback setHelperDirCallback_;
    std::vector<std::future<int32_t>> result_;
    std::unordered_map<std::string, std::string> sampleJsonMap_;
};
}
}
}
#endif
