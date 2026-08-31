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
#include "securec.h"
#include "message/codec.h"
#include "errno/error_code.h"
#include "prof_manager.h"
#include "hdc/device_transport.h"
#include "data_handle.h"
#include "adx_prof_api.h"
#include "msprofbin_test_helper.h"

using namespace analysis::dvvp::host;
using namespace analysis::dvvp::transport;
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::MsprofErrMgr;

namespace {
class HOST_PROF_DEVICE_TRANSPORT_UTEST : public testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override {}

public:
    HDC_CLIENT client = (HDC_CLIENT)0x12345678;
    std::string dev_id = "0";
    std::shared_ptr<DeviceTransport> dev_tran;
    std::shared_ptr<analysis::dvvp::transport::AdxTransport> data_tran;
    std::shared_ptr<analysis::dvvp::transport::AdxTransport> ctrl_tran;
};

class FakeAdxTransport : public analysis::dvvp::transport::AdxTransport {
public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override
    {
        (void)buffer;
        (void)length;
        return Analysis::Dvvp::MsprofbinTest::PopResult(sendResults_);
    }

    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override
    {
        (void)fileChunkReq;
        return Analysis::Dvvp::MsprofbinTest::PopResult(sendResults_);
    }

    int32_t CloseSession() override
    {
        ++closeSessionTimes_;
        return PROFILING_SUCCESS;
    }

    int32_t SendAdxBuffer(IdeBuffT out, int32_t outLen) override
    {
        (void)out;
        (void)outLen;
        return PROFILING_SUCCESS;
    }

    int32_t RecvPacket(TLV_REQ_2PTR packet, uint32_t timeout = 0) override
    {
        (void)timeout;
        int32_t result = Analysis::Dvvp::MsprofbinTest::PopResult(recvResults_);
        if (packet != nullptr) {
            if (result < 0 || recvPackets_.empty()) {
                *packet = nullptr;
            } else {
                *packet = recvPackets_.front();
                recvPackets_.erase(recvPackets_.begin());
            }
        }
        return result;
    }

    void DestroyPacket(TLV_REQ_PTR packet) override { (void)packet; }

    std::vector<int32_t> sendResults_;
    std::vector<int32_t> recvResults_;
    std::vector<TLV_REQ_PTR> recvPackets_;
    uint32_t closeSessionTimes_{0};
};

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, CreateCoparamsnn)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(nullptr, "-1", "123", "def_mode");

    std::shared_ptr<analysis::dvvp::proto::DataChannelHandshake> data_message(
        new analysis::dvvp::proto::DataChannelHandshake());
    EXPECT_EQ(nullptr, dev_tran->CreateConn());
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, init_ctrl_tran)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, "-1", "123", "def_mode");
    EXPECT_EQ(PROFILING_FAILED, dev_tran->Init());
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, DoInit)
{
    auto entry = analysis::dvvp::transport::DevTransMgr::instance();
    EXPECT_EQ(PROFILING_FAILED, entry->Init("123", -1, "def_mode", 0));
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, init_data_tran)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, "-1", "123", "def_mode");
    EXPECT_EQ(PROFILING_FAILED, dev_tran->Init());
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, run)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, dev_id, "123", "def_mode");

    auto fakeTransport = std::make_shared<FakeAdxTransport>();
    data_tran = fakeTransport;
    // dataInitialized_ false
    auto errorContext = MsprofErrorManager::instance()->GetErrorManagerContext();
    dev_tran->Run(errorContext);
    EXPECT_FALSE(dev_tran->dataInitialized_);

    auto packet = new struct tlv_req;
    packet->len = 0;
    fakeTransport->recvResults_ = {PROFILING_FAILED, PROFILING_SUCCESS, PROFILING_SUCCESS};
    fakeTransport->recvPackets_ = {packet, packet};

    dev_tran->quit_ = true;
    // RecvPacket failed
    dev_tran->dataInitialized_ = true;
    dev_tran->dataTran_ = data_tran;
    dev_tran->Run(errorContext);
    EXPECT_FALSE(dev_tran->dataInitialized_);

    // ReceiveStreamData failed
    dev_tran->dataInitialized_ = true;
    dev_tran->dataTran_ = data_tran;
    dev_tran->Run(errorContext);
    EXPECT_FALSE(dev_tran->dataInitialized_);

    // success
    dev_tran->dataInitialized_ = true;
    dev_tran->dataTran_ = data_tran;
    dev_tran->Run(errorContext);
    EXPECT_FALSE(dev_tran->dataInitialized_);

    delete packet;
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, SendMsgAndRecvResponse)
{
    dev_tran = std::make_shared<DeviceTransport>(client, dev_id, "123", "def_mode");

    auto fakeTransport = std::make_shared<FakeAdxTransport>();
    fakeTransport->sendResults_ = {PROFILING_FAILED, PROFILING_SUCCESS};
    ctrl_tran = fakeTransport;
    dev_tran->ctrlTran_ = ctrl_tran;
    std::string msg = "profiling msg";

    struct tlv_req** packetFake = nullptr;
    struct tlv_req* packet = nullptr;

    // invalid parameter
    EXPECT_EQ(PROFILING_FAILED, dev_tran->SendMsgAndRecvResponse(msg, packetFake));

    // send data failed
    EXPECT_EQ(PROFILING_FAILED, dev_tran->SendMsgAndRecvResponse(msg, &packet));

    fakeTransport->recvResults_ = {PROFILING_SUCCESS};
    fakeTransport->recvPackets_ = {new struct tlv_req};

    // received succ
    EXPECT_EQ(PROFILING_SUCCESS, dev_tran->SendMsgAndRecvResponse(msg, &packet));
    delete packet;
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, CloseConn)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, dev_id, "123", "def_mode");
    EXPECT_NE(nullptr, dev_tran);
    // ctrl_tran is null
    dev_tran->CloseConn();

    ctrl_tran = std::make_shared<HDCTransport>(client);
    EXPECT_NE(nullptr, ctrl_tran);
    dev_tran->ctrlTran_ = ctrl_tran;

    dev_tran->CloseConn();
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, IsInitialized)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, dev_id, "123", "def_mode");
    EXPECT_NE(nullptr, dev_tran);
    dev_tran->IsInitialized();
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, HandlePacket)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, dev_id, "123", "def_mode");
    EXPECT_NE(nullptr, dev_tran);
    ctrl_tran = std::make_shared<HDCTransport>(client);
    dev_tran->ctrlTran_ = ctrl_tran;
    TLV_REQ_PTR packet = nullptr;
    analysis::dvvp::message::StatusInfo status;
    EXPECT_EQ(PROFILING_FAILED, dev_tran->HandlePacket(packet, status));
}

TEST_F(HOST_PROF_DEVICE_TRANSPORT_UTEST, HandleShake)
{
    GlobalMockObject::verify();

    dev_tran = std::make_shared<DeviceTransport>(client, dev_id, "123", "def_mode");
    EXPECT_NE(nullptr, dev_tran);
    ctrl_tran = std::make_shared<HDCTransport>(client);
    dev_tran->ctrlTran_ = ctrl_tran;
    TLV_REQ_PTR packet = nullptr;
    analysis::dvvp::message::StatusInfo status;
    EXPECT_EQ(PROFILING_FAILED, dev_tran->HandlePacket(packet, status));
}
} // namespace
