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
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "job_device_rpc.h"
#include "config/config.h"
#include "prof_manager.h"
#include "hdc/device_transport.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace Analysis::Dvvp::JobWrapper;

class PROF_DEVICE_RPC_UTEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}

public:
};

TEST_F(PROF_DEVICE_RPC_UTEST, StartProf)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"1\", \"job_id\":\"1\"}");
    auto jobDeviceRpc = std::make_shared<Analysis::Dvvp::JobWrapper::JobDeviceRpc>(0);
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StartProf(params));
    MOCKER_CPP(&Analysis ::Dvvp::JobWrapper::JobDeviceRpc::SendMsgAndHandleResponse)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, jobDeviceRpc->StartProf(params));
}

TEST_F(PROF_DEVICE_RPC_UTEST, BuildStartReplayMessage)
{
    GlobalMockObject::verify();
    auto jobDeviceRpc = std::make_shared<Analysis::Dvvp::JobWrapper::JobDeviceRpc>(0);
    std::shared_ptr<analysis::dvvp::proto::ReplayStartReq> req(new analysis::dvvp::proto::ReplayStartReq);
    EXPECT_NE(nullptr, req);
    auto cfg = std::make_shared<Analysis::Dvvp::JobWrapper::PMUEventsConfig>();
    auto ctrlCPUEvents = std::make_shared<std::vector<std::string>>(0);
    auto aiCoreEventsCoreIds = std::make_shared<std::vector<int>>();
    aiCoreEventsCoreIds->push_back(1);
    ctrlCPUEvents->push_back("aa");
    cfg->ctrlCPUEvents = *ctrlCPUEvents;
    cfg->tsCPUEvents = *ctrlCPUEvents;
    cfg->aiCoreEvents = *ctrlCPUEvents;
    cfg->aiCoreEventsCoreIds = *aiCoreEventsCoreIds;
    cfg->llcEvents = *ctrlCPUEvents;
    cfg->ddrEvents = *ctrlCPUEvents;
    cfg->aivEvents = *ctrlCPUEvents;
    cfg->aivEventsCoreIds = *aiCoreEventsCoreIds;
    jobDeviceRpc->BuildStartReplayMessage(cfg, req);
}

TEST_F(PROF_DEVICE_RPC_UTEST, StartProf1)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"1\", \"job_id\":\"1\"}");
    params->ai_ctrl_cpu_profiling_events = "aa";
    auto jobDeviceRpc = std::make_shared<Analysis::Dvvp::JobWrapper::JobDeviceRpc>(0);

    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StartProf(params));

    jobDeviceRpc->params_ = params;
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StartProf(params));
    MOCKER_CPP(&Analysis ::Dvvp::JobWrapper::JobDeviceRpc::SendMsgAndHandleResponse)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));

    EXPECT_EQ(PROFILING_SUCCESS, jobDeviceRpc->StartProf(params));
}

TEST_F(PROF_DEVICE_RPC_UTEST, StopProf)
{
    GlobalMockObject::verify();
    auto jobDeviceRpc = std::make_shared<Analysis::Dvvp::JobWrapper::JobDeviceRpc>(0);
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StopProf());
    jobDeviceRpc->isStarted_ = true;
    MOCKER_CPP(&Analysis ::Dvvp::JobWrapper::JobDeviceRpc::SendMsgAndHandleResponse)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StopProf());
    EXPECT_EQ(PROFILING_SUCCESS, jobDeviceRpc->StopProf());
}

TEST_F(PROF_DEVICE_RPC_UTEST, StopProf2)
{
    GlobalMockObject::verify();
    auto jobDeviceRpc = std::make_shared<Analysis::Dvvp::JobWrapper::JobDeviceRpc>(0);
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"1\", \"job_id\":\"1\"}");
    jobDeviceRpc->params_ = params;
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StopProf());
    jobDeviceRpc->isStarted_ = true;
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->StopProf());
    MOCKER_CPP(&Analysis ::Dvvp::JobWrapper::JobDeviceRpc::SendMsgAndHandleResponse)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, jobDeviceRpc->StopProf());
}

TEST_F(PROF_DEVICE_RPC_UTEST, SendMsgAndHandleResponse)
{
    GlobalMockObject::verify();
    auto jobDeviceRpc = std::make_shared<Analysis::Dvvp::JobWrapper::JobDeviceRpc>(0);
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    params->FromString("{\"result_dir\":\"/tmp/\", \"devices\":\"1\", \"job_id\":\"1\"}");
    jobDeviceRpc->params_ = params;
    std::shared_ptr<analysis::dvvp::proto::JobStartReq> message(new analysis::dvvp::proto::JobStartReq);
    EXPECT_EQ(-1, jobDeviceRpc->SendMsgAndHandleResponse(message));
    HDC_CLIENT client;
    std::shared_ptr<analysis::dvvp::transport::IDeviceTransport> deviceTransport =
        std::make_shared<analysis::dvvp::transport::DeviceTransport>(client, "123", "0", "def_mode");

    std::shared_ptr<analysis::dvvp::transport::IDeviceTransport> mockTransport;
    mockTransport.reset();

    std::shared_ptr<std::string> encodeMessage = std::make_shared<std::string>();
    std::shared_ptr<std::string> mockMessage;
    mockMessage.reset();

    MOCKER(analysis::dvvp::message::EncodeMessageShared)
        .stubs()
        .will(returnValue(mockMessage))
        .then(returnValue(encodeMessage));

    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->SendMsgAndHandleResponse(message));
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->SendMsgAndHandleResponse(message));
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->SendMsgAndHandleResponse(message));
    EXPECT_EQ(PROFILING_FAILED, jobDeviceRpc->SendMsgAndHandleResponse(message));
}
