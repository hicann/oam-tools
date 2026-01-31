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
#ifndef ANALYSIS_DVVP_JOB_DEVICE_RPC_H
#define ANALYSIS_DVVP_JOB_DEVICE_RPC_H

#include "collection_register.h"
#include "job_adapter.h"
#include "message/codec.h"
#include "message/prof_params.h"
#include "proto/profiler.pb.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
class JobDeviceRpc : public JobAdapter {
public:
    explicit JobDeviceRpc(int32_t indexId);
    ~JobDeviceRpc() override;

public:
    int32_t StartProf(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) override;
    int32_t StopProf(void) override;

private:
    int32_t SendMsgAndHandleResponse(SHARED_PTR_ALIA<google::protobuf::Message> msg);
    void BuildStartReplayMessage(SHARED_PTR_ALIA<PMUEventsConfig> cfg,
                                SHARED_PTR_ALIA<analysis::dvvp::proto::ReplayStartReq> startReplayMessage) const;
    void BuildCtrlCpuEventMessage(SHARED_PTR_ALIA<PMUEventsConfig> cfg,
                                SHARED_PTR_ALIA<analysis::dvvp::proto::ReplayStartReq> startReplayMessage) const;
    void BuildLlcEventMessage(SHARED_PTR_ALIA<PMUEventsConfig> cfg,
                                SHARED_PTR_ALIA<analysis::dvvp::proto::ReplayStartReq> startReplayMessage) const;
private:
    int32_t indexId_;
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;
    bool isStarted_;
    analysis::dvvp::message::JobContext jobCtx_;
    SHARED_PTR_ALIA<PMUEventsConfig> pmuCfg_;
};
}}}
#endif