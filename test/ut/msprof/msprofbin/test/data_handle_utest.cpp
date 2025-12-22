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
#include "mockcpp/mockcpp.hpp"
#include "gtest/gtest.h"
#include <iostream>
#include "errno/error_code.h"
#include "data_handle.h"
#include "message/codec.h"


using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;

class DATA_HANDLE_UTEST : public testing::Test {
protected:
  virtual void SetUp() {}
  virtual void TearDown() {}
};


TEST_F(DATA_HANDLE_UTEST, ReceiveStreamData) { 
    GlobalMockObject::verify();


    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx(new analysis::dvvp::message::JobContext); 
    jobCtx->dev_id = "0";                                                                               
    jobCtx->job_id = "0x123456789";   

    std::shared_ptr<analysis::dvvp::proto::DataChannelFinish> message(
        new analysis::dvvp::proto::DataChannelFinish());
    std::string encoded = analysis::dvvp::message::EncodeMessage(message);
    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)NULL, encoded.size()));
  
    message->mutable_hdr()->set_job_ctx(jobCtx->ToString());  
    encoded = analysis::dvvp::message::EncodeMessage(message); 
    //null
    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)encoded.c_str(), encoded.size()));


    //message error
    std::shared_ptr<analysis::dvvp::proto::Response> fake_message(
        new analysis::dvvp::proto::Response());
    std::string fake_encoded = analysis::dvvp::message::EncodeMessage(fake_message);
    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)fake_encoded.c_str(), fake_encoded.size()));
    //success
    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)encoded.c_str(), encoded.size()));

    // filechunk meessage
    std::shared_ptr<analysis::dvvp::proto::FileChunkReq> fileChunkMessage(
    new analysis::dvvp::proto::FileChunkReq());
    std::string fileChunkEncoded = analysis::dvvp::message::EncodeMessage(fileChunkMessage);

    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)fileChunkEncoded.c_str(), fileChunkEncoded.size()));

                                                               
    fileChunkMessage->mutable_hdr()->set_job_ctx(jobCtx->ToString());    
    fileChunkMessage->set_datamodule(FileChunkDataModule::PROFILING_IS_FROM_MSPROF);
    fileChunkEncoded = analysis::dvvp::message::EncodeMessage(fileChunkMessage);
    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)fileChunkEncoded.c_str(), fileChunkEncoded.size()));

    // FinishJobRsp messsage 
    std::shared_ptr<analysis::dvvp::proto::FinishJobRsp> finishJobRsp(
    new analysis::dvvp::proto::FinishJobRsp());
    std::string finishJob = analysis::dvvp::message::EncodeMessage(finishJobRsp);
    EXPECT_EQ(PROFILING_FAILED, Analysis::Dvvp::Msprof::HdcTransportDataHandle::ReceiveStreamData((void*)finishJob.c_str(), finishJob.size()));

}