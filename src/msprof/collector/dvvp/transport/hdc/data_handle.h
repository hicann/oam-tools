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
#ifndef ANALYSIS_DVVP_TRANSPORT_DATA_HANDLE_H
#define ANALYSIS_DVVP_TRANSPORT_DATA_HANDLE_H

#include <map>
#include "config/config.h"
#include "message/prof_params.h"
#include "singleton/singleton.h"
#include "proto/profiler.pb.h"
#include "utils/utils.h"

namespace Analysis {
namespace Dvvp {
namespace Msprof {
using namespace analysis::dvvp::common::utils;
using PFMessagehandler = int32_t (*)(SHARED_PTR_ALIA<google::protobuf::Message> message);
class IDataHandleCB {
public:
    virtual ~IDataHandleCB();
};

class HdcTransportDataHandle : public IDataHandleCB,
                               public analysis::dvvp::common::singleton::Singleton<HdcTransportDataHandle> {
public:
    HdcTransportDataHandle();
    ~HdcTransportDataHandle() override;
    static std::map<const google::protobuf::Descriptor *, PFMessagehandler> CreateHandlerMap();
    static int32_t ReceiveStreamData(CONST_VOID_PTR data, uint32_t dataLen);

private:
    static int32_t ProcessStreamFileChunk(SHARED_PTR_ALIA<google::protobuf::Message> message);
    static int32_t ProcessDataChannelFinish(SHARED_PTR_ALIA<google::protobuf::Message> message);
    static int32_t ProcessFinishJobRspMsg(SHARED_PTR_ALIA<google::protobuf::Message> message);
    static int32_t ProcessResponseMsg(SHARED_PTR_ALIA<google::protobuf::Message> message);
    static int32_t ProcessRspCommon(const std::string &jobId, const std::string &encoded);

private:
    static std::map<const google::protobuf::Descriptor *, PFMessagehandler> handlerMap_;
};
}
}
}
#endif
