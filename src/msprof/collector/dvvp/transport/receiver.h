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
 
#ifndef ANALYSIS_DVVP_DEVICE_RECEIVER_H
#define ANALYSIS_DVVP_DEVICE_RECEIVER_H

#include "message/codec.h"
#include "message/dispatcher.h"
#include "prof_msg_handler.h"
#include "prof_job_handler.h"
#include "thread/thread.h"
#include "transport/hdc/adx_transport.h"

namespace analysis {
namespace dvvp {
namespace device {
class Receiver : public analysis::dvvp::common::thread::Thread {
public:
    explicit Receiver(SHARED_PTR_ALIA<analysis::dvvp::transport::AdxTransport> transport);
    virtual ~Receiver();

public:
    int32_t Init(int32_t devId);
    int32_t Uinit();
    const SHARED_PTR_ALIA<analysis::dvvp::transport::AdxTransport> GetTransport();
    int32_t SendMessage(SHARED_PTR_ALIA<google::protobuf::Message> message);
    void SetDevIdOnHost(int32_t devIdOnHost);
protected:
    void Run(const struct error_message::Context &errorContext);

private:
    SHARED_PTR_ALIA<analysis::dvvp::message::MsgDispatcher> dispatcher_;
    SHARED_PTR_ALIA<analysis::dvvp::transport::AdxTransport> transport_;
    int32_t devId_;
    int32_t devIdOnHost_;
    volatile bool inited_;
};
}  // namespace device
}  // namespace dvvp
}  // namespace analysis

#endif
