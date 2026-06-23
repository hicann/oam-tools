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
#include <iostream>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "proto/profiler.pb.h"
#include "message/dispatcher.h"

class MESSAGE_DISPATCHER_TEST: public testing::Test {
protected:
    virtual void SetUp() {
    }
    virtual void TearDown() {
    }
};

TEST_F(MESSAGE_DISPATCHER_TEST, IMsgHandler_OnNewMessage) {
    GlobalMockObject::verify();

    MockObject<analysis::dvvp::message::IMsgHandler> handler;
    MOCK_METHOD(handler, OnNewMessage)
        .stubs();

    std::shared_ptr<analysis::dvvp::proto::JobStartReq> message(
        new analysis::dvvp::proto::JobStartReq);
    EXPECT_NE(nullptr, message);

    handler->OnNewMessage(message);
}

class FakeJobStartHandler : public analysis::dvvp::message::IMsgHandler {
public:
    FakeJobStartHandler() {}
    virtual ~FakeJobStartHandler() {}

public:
    virtual void OnNewMessage(std::shared_ptr<google::protobuf::Message> message) {
        std::cout << "handle fake job start" << std::endl;
    }
};

TEST_F(MESSAGE_DISPATCHER_TEST, RegisterMessageHandler) {
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::MsgDispatcher> disp(
        new analysis::dvvp::message::MsgDispatcher());
    EXPECT_NE(nullptr, disp);

    //find handler
    std::shared_ptr<analysis::dvvp::message::IMsgHandler> handler(
        new FakeJobStartHandler());
    disp->RegisterMessageHandler<analysis::dvvp::proto::JobStartReq>(
        handler);
}

TEST_F(MESSAGE_DISPATCHER_TEST, OnNewMessage) {
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::MsgDispatcher> disp(
        new analysis::dvvp::message::MsgDispatcher());
    EXPECT_NE(nullptr, disp);

    //null param
    disp->OnNewMessage(nullptr);

    //not register handler
    std::shared_ptr<analysis::dvvp::proto::JobStartReq> message(
        new analysis::dvvp::proto::JobStartReq);
    disp->OnNewMessage(message);

    //register handler
    std::shared_ptr<analysis::dvvp::message::IMsgHandler> handler(
        new FakeJobStartHandler());
    disp->RegisterMessageHandler<analysis::dvvp::proto::JobStartReq>(
        handler);
    disp->OnNewMessage(message);
}