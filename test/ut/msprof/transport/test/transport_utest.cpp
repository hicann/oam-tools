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
#include <memory>
#include <vector>
#include <fstream>
#include "transport/hdc/hdc_transport.h"
#include "transport/hdc/helper_transport.h"
#include "transport/file_transport.h"
#include "errno/error_code.h"
#include "utils/utils.h"
#include "param_validation.h"
#include "config/config.h"
#include "message/codec.h"
#include "adx_prof_api.h"
#include "proto/profiler.pb.h"
#include "op_transport.h"
#include "data_struct.h"
#include "aprof_pub.h"
#include "config_manager.h"
#include "platform/platform.h"
#include "ascend_hal.h"
#include "hdc_api.h"

using namespace analysis::dvvp::transport;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace Analysis::Dvvp::Adx;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::Common::Config;
using namespace Dvvp::Acp::Analyze;
//////////////////////////////HDCTransport/////////////////////////////////////
class TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}

private:
    std::string _log_file;
};

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, HDCTransport)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans(new HDCTransport(session));
    EXPECT_NE(nullptr, trans);
    trans.reset();
}

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, SendBuffer)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans(new HDCTransport(session));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;

    void* out = (void*)0x12345678;
    MOCKER(IdeCreatePacket)
        .stubs()
        .with(any(), any(), any(), outBoundP(&out), any())
        .will(returnValue(IDE_DAEMON_ERROR))
        .then(returnValue(IDE_DAEMON_OK));

    MOCKER(HdcWrite).stubs().will(returnValue(IDE_DAEMON_ERROR)).then(returnValue(IDE_DAEMON_OK));

    void* buff = (void*)0x12345678;
    int length = 10;
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(buff, length));
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(buff, length));
    EXPECT_EQ(length, trans->SendBuffer(buff, length));
}

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, SendBufferForProfileFileChunk)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans(new HDCTransport(session));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;

    void* out = (void*)0x12345678;
    MOCKER(IdeCreatePacket)
        .stubs()
        .with(any(), any(), any(), outBoundP(&out), any())
        .will(returnValue(IDE_DAEMON_ERROR))
        .then(returnValue(IDE_DAEMON_OK));

    MOCKER(HdcWrite).stubs().will(returnValue(IDE_DAEMON_ERROR)).then(returnValue(IDE_DAEMON_OK));

    SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq;
    fileChunkReq = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    fileChunkReq->chunkSize = 1;
    fileChunkReq->fileName = "event.null";
    fileChunkReq->extraInfo = "null.0";
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(fileChunkReq));
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(fileChunkReq));
    EXPECT_EQ(PROFILING_SUCCESS, trans->SendBuffer(fileChunkReq));
}

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, RecvPacket)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    int buf_len = sizeof(struct tlv_req);
    struct tlv_req* packet = NULL;

    std::shared_ptr<HDCTransport> trans(new HDCTransport(session));

    MOCKER(HdcRead)
        .stubs()
        .with(any(), any(), outBoundP(&buf_len))
        .will(returnValue(IDE_DAEMON_ERROR))
        .then(returnValue(IDE_DAEMON_OK));

    EXPECT_EQ(PROFILING_FAILED, trans->RecvPacket(&packet));
    EXPECT_EQ(buf_len, trans->RecvPacket(&packet));
}

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, DestroyPacket)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<HDCTransport> trans(new HDCTransport(session));
    EXPECT_NE(nullptr, trans);

    struct tlv_req* packet = (struct tlv_req*)0x12345678;
    trans->DestroyPacket(NULL);
    trans->DestroyPacket(packet);
}

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, CloseSession)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans_s(new HDCTransport(session));
    EXPECT_EQ(PROFILING_SUCCESS, trans_s->CloseSession());
    trans_s.reset();

    session = (HDC_SESSION)0x12345678;
    std::shared_ptr<ITransport> trans_c(new HDCTransport(session, true));
    EXPECT_EQ(PROFILING_SUCCESS, trans_c->CloseSession());
    trans_c.reset();
}

TEST_F(TRANSPORT_TRANSPORT_HDCTRANSPORT_TEST, MultiThread_CloseSession)
{
    GlobalMockObject::verify();
    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<ITransport> trans_s(new HDCTransport(session));

    std::vector<std::thread> th;
    for (int i = 0; i < 10; i++) {
        th.push_back(std::thread([&, trans_s]() -> void { EXPECT_EQ(PROFILING_SUCCESS, trans_s->CloseSession()); }));
    }
    for_each(th.begin(), th.end(), std::mem_fn(&std::thread::join));
}

///////////////////////////////TransportFactory////////////////////////////////////
class TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}

private:
    std::string _log_file;
};

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, TransportFactory)
{
    GlobalMockObject::verify();

    std::shared_ptr<TransportFactory> fac(new TransportFactory());
    EXPECT_NE(nullptr, fac);
    fac.reset();
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, create_hdc_transport_with_nullptr_server)
{
    GlobalMockObject::verify();
    EXPECT_EQ(nullptr, HDCTransportFactory().CreateHdcServerTransport(0, nullptr));
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, create_hdc_transport_session)
{
    GlobalMockObject::verify();

    EXPECT_TRUE(HDCTransportFactory().CreateHdcTransport(nullptr).get() == nullptr);

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    auto trans = HDCTransportFactory().CreateHdcTransport(session);
    EXPECT_NE((ITransport*)NULL, trans.get());

    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::CheckStringIsNonNegativeIntNum).stubs().will(returnValue(false));
    trans = HDCTransportFactory().CreateHdcTransport(session);
    EXPECT_EQ((ITransport*)NULL, trans.get());
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, create_hdc_transport_client)
{
    GlobalMockObject::verify();

    HDC_CLIENT client = (HDC_CLIENT)0x12345678;
    int dev_id = 0;

    MOCKER(HdcSessionConnect).stubs().will(returnValue(IDE_DAEMON_ERROR)).then(returnValue(IDE_DAEMON_OK));

    EXPECT_EQ((ITransport*)NULL, HDCTransportFactory().CreateHdcTransport(client, dev_id).get());
    EXPECT_NE((ITransport*)NULL, HDCTransportFactory().CreateHdcTransport(client, dev_id).get());
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, create_hdc_transport_getdevid)
{
    GlobalMockObject::verify();

    MOCKER(IdeGetDevIdBySession).stubs().will(returnValue(IDE_DAEMON_ERROR));

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    auto trans = HDCTransportFactory().CreateHdcTransport(session);
    EXPECT_EQ((ITransport*)NULL, trans.get());
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, CreateOpTransport)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    Platform::instance()->Init();
    std::string deviceId = "0";
    auto trans = OpTransportFactory().CreateOpTransport(deviceId);
    EXPECT_NE((ITransport*)NULL, trans.get());

    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk(new analysis::dvvp::ProfileFileChunk());
    chunk->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;
    chunk->fileName = "test.data";
    chunk->extraInfo = "null.0";
    int ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    trans->WriteDone();
    Platform::instance()->Uninit();
}

drvError_t halGetDeviceInfoTransStub(uint32_t devId, int32_t moduleType, int32_t infoType, int64_t* value)
{
    if (moduleType == static_cast<int32_t>(MODULE_TYPE_AICORE) &&
        (infoType == static_cast<int32_t>(INFO_TYPE_CORE_NUM))) {
        *value = 20;
    } else if (
        moduleType == static_cast<int32_t>(MODULE_TYPE_VECTOR_CORE) &&
        (infoType == static_cast<int32_t>(INFO_TYPE_CORE_NUM))) {
        *value = 40;
    } else if (
        moduleType == static_cast<int32_t>(MODULE_TYPE_SYSTEM) &&
        (infoType == static_cast<int32_t>(INFO_TYPE_DEV_OSC_FREQUE))) {
        *value = 50000;
    }
    return DRV_ERROR_NONE;
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, ParseMilanOpAicData)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::AscendHalAdaptor::Init).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(halGetDeviceInfo).stubs().will(invoke(halGetDeviceInfoTransStub));
    Platform::instance()->Init();
    using namespace Analysis::Dvvp::Analyze;
    std::string deviceId = "0";
    auto trans = OpTransportFactory().CreateOpTransport(deviceId);
    EXPECT_NE((ITransport*)NULL, trans.get());
    // stars_soc.data
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk(new analysis::dvvp::ProfileFileChunk());
    chunk->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;
    chunk->fileName = "stars_soc.data";
    chunk->extraInfo = "null.0";
    StarsAcsqLog data;
    data.streamId = 0;
    data.taskId = 1;
    // start
    data.sysCountHigh = 1;
    data.sysCountLow = 1;
    data.head.logType = ACSQ_TASK_START_FUNC_TYPE;
    std::string starsData((char*)&data, sizeof(data));
    chunk->chunk = starsData;
    chunk->chunkSize = sizeof(data);
    int ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end
    data.sysCountHigh = 1;
    data.sysCountLow = 2;
    data.head.logType = ACSQ_TASK_END_FUNC_TYPE;
    std::string starsDataEnd((char*)&data, sizeof(data));
    chunk->chunk = starsDataEnd;
    chunk->chunkSize = sizeof(data);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data
    chunk->fileName = "ffts_profile.data";
    FftsSubProfile data2;
    data2.streamId = 0;
    data2.taskId = 1;
    data2.head.funcType = 0b101000;
    data2.fftsType = FFTS_TYPE_FFTS;
    data2.contextType = SUB_TASK_TYPE_AIC;
    data2.totalCycle = 1000;
    data2.startCnt = 0;
    data2.endCnt = 1;
    data2.pmu[0] = 10;
    data2.pmu[1] = 20;
    data2.pmu[2] = 30;
    data2.pmu[3] = 40;
    data2.pmu[4] = 50;
    data2.pmu[5] = 60;
    data2.pmu[6] = 70;
    data2.pmu[7] = 80;
    std::string FftsData((char*)&data2, sizeof(data2));
    chunk->chunk = FftsData;
    chunk->chunkSize = sizeof(data2);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end_info
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk2(new analysis::dvvp::ProfileFileChunk());
    chunk2->fileName = "end_info";
    chunk2->extraInfo = "./";
    chunk2->chunk = "MemoryL0";
    uint16_t low = 0x0001;
    uint16_t high = 0x0000;
    uint32_t blockDim = ((uint32_t)high << 16) | low;
    chunk2->id = std::to_string(blockDim);
    ret = trans->SendBuffer(chunk2);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    Platform::instance()->Uninit();
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, ParseMilanOpAivData)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::AscendHalAdaptor::Init).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(halGetDeviceInfo).stubs().will(invoke(halGetDeviceInfoTransStub));
    Platform::instance()->Init();
    using namespace Analysis::Dvvp::Analyze;
    std::string deviceId = "0";
    auto trans = OpTransportFactory().CreateOpTransport(deviceId);
    EXPECT_NE((ITransport*)NULL, trans.get());
    // stars_soc.data
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk(new analysis::dvvp::ProfileFileChunk());
    chunk->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;
    chunk->fileName = "stars_soc.data";
    chunk->extraInfo = "null.0";
    StarsAcsqLog data;
    data.streamId = 0;
    data.taskId = 1;
    // start
    data.sysCountHigh = 1;
    data.sysCountLow = 1;
    data.head.logType = ACSQ_TASK_START_FUNC_TYPE;
    std::string starsData((char*)&data, sizeof(data));
    chunk->chunk = starsData;
    chunk->chunkSize = sizeof(data);
    int ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end
    data.sysCountHigh = 1;
    data.sysCountLow = 2;
    data.head.logType = ACSQ_TASK_END_FUNC_TYPE;
    std::string starsDataEnd((char*)&data, sizeof(data));
    chunk->chunk = starsDataEnd;
    chunk->chunkSize = sizeof(data);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data
    chunk->fileName = "ffts_profile.data";
    FftsSubProfile data2;
    data2.streamId = 0;
    data2.taskId = 1;
    data2.head.funcType = 0b101000;
    data2.fftsType = FFTS_TYPE_FFTS;
    data2.contextType = SUB_TASK_TYPE_AIC + 1;
    data2.totalCycle = 1000;
    data2.startCnt = 0;
    data2.endCnt = 1;
    data2.pmu[0] = 10;
    data2.pmu[1] = 20;
    data2.pmu[2] = 30;
    data2.pmu[3] = 40;
    data2.pmu[4] = 50;
    data2.pmu[5] = 60;
    data2.pmu[6] = 70;
    data2.pmu[7] = 80;
    std::string FftsData((char*)&data2, sizeof(data2));
    chunk->chunk = FftsData;
    chunk->chunkSize = sizeof(data2);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end_info
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk2(new analysis::dvvp::ProfileFileChunk());
    chunk2->fileName = "end_info";
    chunk2->extraInfo = "./";
    chunk2->chunk = "ArithmeticUtilization";
    uint16_t low = 0x0001;
    uint16_t high = 0x0000;
    uint32_t blockDim = ((uint32_t)high << 16) | low;
    chunk2->id = std::to_string(blockDim);
    ret = trans->SendBuffer(chunk2);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    Platform::instance()->Uninit();
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, ParseMilanOpMixAicData)
{ // aic context，aiv block
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::AscendHalAdaptor::Init).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(halGetDeviceInfo).stubs().will(invoke(halGetDeviceInfoTransStub));
    Platform::instance()->Init();
    using namespace Analysis::Dvvp::Analyze;
    std::string deviceId = "0";
    auto trans = OpTransportFactory().CreateOpTransport(deviceId);
    EXPECT_NE((ITransport*)NULL, trans.get());
    // stars_soc.data
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk(new analysis::dvvp::ProfileFileChunk());
    chunk->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;
    chunk->fileName = "stars_soc.data";
    chunk->extraInfo = "null.0";
    StarsAcsqLog data;
    data.streamId = 0;
    data.taskId = 1;
    // start
    data.sysCountHigh = 1;
    data.sysCountLow = 1;
    data.head.logType = ACSQ_TASK_START_FUNC_TYPE;
    std::string starsData((char*)&data, sizeof(data));
    chunk->chunk = starsData;
    chunk->chunkSize = sizeof(data);
    int ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end
    data.sysCountHigh = 1;
    data.sysCountLow = 2;
    data.head.logType = ACSQ_TASK_END_FUNC_TYPE;
    std::string starsDataEnd((char*)&data, sizeof(data));
    chunk->chunk = starsDataEnd;
    chunk->chunkSize = sizeof(data);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data context
    chunk->fileName = "ffts_profile.data";
    FftsSubProfile data2;
    data2.streamId = 0;
    data2.taskId = 1;
    data2.contextId = 1;
    data2.head.funcType = 0b101000;
    data2.fftsType = FFTS_TYPE_FFTS;
    data2.contextType = SUB_TASK_TYPE_MIXAIC;
    data2.totalCycle = 1000;
    data2.startCnt = 0;
    data2.endCnt = 1;
    data2.pmu[0] = 10;
    data2.pmu[1] = 20;
    data2.pmu[2] = 30;
    std::string FftsSubData((char*)&data2, sizeof(data2));
    chunk->chunk = FftsSubData;
    chunk->chunkSize = sizeof(data2);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data block
    FftsBlockProfile data3;
    data3.streamId = 0;
    data3.taskId = 1;
    data3.contextId = 1;
    data3.head.funcType = 0b101001;
    data3.fftsType = FFTS_TYPE_FFTS;
    data3.contextType = SUB_TASK_TYPE_MIXAIC;
    data3.coreType = CORE_TYPE_AIV;
    data3.totalCycle = 1000;
    data3.startCnt = 0;
    data3.endCnt = 1;
    data3.pmu[0] = 10;
    data3.pmu[1] = 20;
    data3.pmu[2] = 30;
    std::string FftsBlockData((char*)&data3, sizeof(data3));
    chunk->chunk = FftsBlockData;
    chunk->chunkSize = sizeof(data3);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data block repeat 3
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end_info
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk2(new analysis::dvvp::ProfileFileChunk());
    chunk2->fileName = "end_info";
    chunk2->extraInfo = "./";
    chunk2->chunk = "ResourceConflictRatio";
    uint16_t low = 0x0001;
    uint16_t high = 0x0010;
    uint32_t blockDim = ((uint32_t)high << 16) | low;
    chunk2->id = std::to_string(blockDim);
    ret = trans->SendBuffer(chunk2);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    Platform::instance()->Uninit();
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, ParseDavidOpMixAicData)
{ // aic context，aiv block
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_CLOUD_V3));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::AscendHalAdaptor::Init).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(halGetDeviceInfo).stubs().will(invoke(halGetDeviceInfoTransStub));
    Platform::instance()->Init();
    using namespace Analysis::Dvvp::Analyze;
    std::string deviceId = "0";
    auto trans = OpTransportFactory().CreateOpTransport(deviceId);
    EXPECT_NE((ITransport*)NULL, trans.get());
    // stars_soc.data
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk(new analysis::dvvp::ProfileFileChunk());
    chunk->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;
    chunk->fileName = "stars_soc.data";
    chunk->extraInfo = "null.0";
    DavidAcsqLog data;
    data.streamId = 0;
    data.taskId = 1;
    // start
    data.sysCountHigh = 1;
    data.sysCountLow = 1;
    data.head.logType = ACSQ_TASK_START_FUNC_TYPE;
    std::string starsData((char*)&data, sizeof(data));
    chunk->chunk = starsData;
    chunk->chunkSize = sizeof(data);
    int ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end
    data.sysCountHigh = 1;
    data.sysCountLow = 2;
    data.head.logType = ACSQ_TASK_END_FUNC_TYPE;
    std::string starsDataEnd((char*)&data, sizeof(data));
    chunk->chunk = starsDataEnd;
    chunk->chunkSize = sizeof(data);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data context
    chunk->fileName = "ffts_profile.data";
    DavidProfile data2;
    data2.streamId = 0;
    data2.taskId = 1;
    data2.contextId = 1;
    data2.head.funcType = 0b101010;
    data2.contextType = SUB_TASK_TYPE_MIXAIC;
    data2.totalCycle = 1000;
    data2.startCnt = 0;
    data2.endCnt = 1;
    for (auto i = 0; i < 9; i++) {
        data2.pmu[i] = i * 10 + 10;
    }
    std::string FftsSubData((char*)&data2, sizeof(data2));
    chunk->chunk = FftsSubData;
    chunk->chunkSize = sizeof(data2);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data block
    DavidProfile data3;
    data3.streamId = 0;
    data3.taskId = 1;
    data3.contextId = 1;
    data3.head.funcType = 0b101001;
    data3.contextType = SUB_TASK_TYPE_MIXAIC;
    data3.coreType = CORE_TYPE_AIV;
    data3.totalCycle = 1000;
    data3.startCnt = 0;
    data3.endCnt = 1;
    for (auto i = 0; i < 9; i++) {
        data3.pmu[i] = i * 10 + 20;
    }
    std::string FftsBlockData((char*)&data3, sizeof(data3));
    chunk->chunk = FftsBlockData;
    chunk->chunkSize = sizeof(data3);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Ffts.data block repeat 3
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // end_info
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk2(new analysis::dvvp::ProfileFileChunk());
    chunk2->fileName = "end_info";
    chunk2->extraInfo = "./";
    chunk2->chunk = "PipeUtilization";
    uint16_t low = 0x0001;
    uint16_t high = 0x0010;
    uint32_t blockDim = ((uint32_t)high << 16) | low;
    chunk2->id = std::to_string(blockDim);
    ret = trans->SendBuffer(chunk2);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    Platform::instance()->Uninit();
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, ParseDavidOpBiuPerf)
{ // biuPerf
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_CLOUD_V3));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::AscendHalAdaptor::Init).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(halGetDeviceInfo).stubs().will(invoke(halGetDeviceInfoTransStub));
    Platform::instance()->Init();
    using namespace Analysis::Dvvp::Analyze;
    std::string deviceId = "0";
    auto trans = OpTransportFactory().CreateOpTransport(deviceId);
    EXPECT_NE((ITransport*)NULL, trans.get());
    // biu data. group: 0, tag: aic
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> chunk(new analysis::dvvp::ProfileFileChunk());
    chunk->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;
    chunk->fileName = "data/instr.biu_perf_group0_aic.null";
    chunk->extraInfo = "null.0";

    // channel 1st
    // Simulate the execution of syscnt
    BiuPerfProfile biuperf;
    biuperf.ctrlType = 0b1110;
    biuperf.events = 0b000000010101;
    biuperf.timeData = 0b0000000000001110;
    std::string sysCntData = std::string((char*)&biuperf, sizeof(biuperf));
    sysCntData.append(std::string((char*)&biuperf, sizeof(biuperf)));
    sysCntData.append(sysCntData);
    chunk->chunk = sysCntData;
    chunk->chunkSize = sizeof(biuperf) * 4;
    int32_t ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the time stamp of the operator
    biuperf.ctrlType = 0b0011;
    biuperf.events = 0b000000010101;
    biuperf.timeData = 0b1000000100001111;
    chunk->chunk = std::string((char*)&biuperf, sizeof(biuperf));
    chunk->chunkSize = sizeof(biuperf);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the execution of the operator: Start
    biuperf.ctrlType = 0b1111;
    biuperf.events = 0b000000010101;
    biuperf.timeData = 0b1000000000111111;
    chunk->chunk = std::string((char*)&biuperf, sizeof(biuperf));
    chunk->chunkSize = sizeof(biuperf);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the execution of the operator: Stop
    biuperf.ctrlType = 0b1111;
    biuperf.events = 0b000000000000;
    biuperf.timeData = 0b1000000000111111;
    chunk->chunk = std::string((char*)&biuperf, sizeof(biuperf));
    chunk->chunkSize = sizeof(biuperf);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // channel 2nd
    BiuPerfProfile biuperf2;
    biuperf2.ctrlType = 0b1110;
    biuperf2.events = 0b000000010111;
    biuperf2.timeData = 0b0000000000001110;
    std::string sysCntData2 = std::string((char*)&biuperf2, sizeof(biuperf2));
    sysCntData2.append(std::string((char*)&biuperf2, sizeof(biuperf2)));
    sysCntData2.append(sysCntData2);
    chunk->fileName = "data/instr.biu_perf_group1_aiv1.null";
    chunk->extraInfo = "null.0";
    chunk->chunk = sysCntData2;
    chunk->chunkSize = sizeof(biuperf2) * 4;
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the execution of the operator: Start
    biuperf2.ctrlType = 0b1111;
    biuperf2.events = 0b000000101010;
    biuperf2.timeData = 0b1000000001111111;
    chunk->chunk = std::string((char*)&biuperf2, sizeof(biuperf2));
    chunk->chunkSize = sizeof(biuperf2);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the execution of the operator: Stop
    biuperf2.ctrlType = 0b1111;
    biuperf2.events = 0b000000000000;
    biuperf2.timeData = 0b1000000000111110;
    chunk->chunk = std::string((char*)&biuperf2, sizeof(biuperf2));
    chunk->chunkSize = sizeof(biuperf2);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // channel 3rd
    biuperf.ctrlType = 0b1110;
    biuperf.events = 0b000000010101;
    biuperf.timeData = 0b0000000000001110;
    sysCntData = std::string((char*)&biuperf, sizeof(biuperf));
    sysCntData.append(std::string((char*)&biuperf, sizeof(biuperf)));
    sysCntData.append(sysCntData);
    chunk->fileName = "data/instr.biu_perf_group0_aiv0.null";
    chunk->extraInfo = "null.0";
    chunk->chunk = sysCntData;
    chunk->chunkSize = sizeof(biuperf) * 4;
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the execution of the operator: Start
    biuperf.ctrlType = 0b1111;
    biuperf.events = 0b000000011111;
    biuperf.timeData = 0b1000000111111111;
    chunk->chunk = std::string((char*)&biuperf, sizeof(biuperf));
    chunk->chunkSize = sizeof(biuperf);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // Simulate the execution of the operator: Stop
    biuperf.ctrlType = 0b1111;
    biuperf.events = 0b000000000000;
    biuperf.timeData = 0b1000000000111111;
    chunk->chunk = std::string((char*)&biuperf, sizeof(biuperf));
    chunk->chunkSize = sizeof(biuperf);
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);

    // end
    chunk->fileName = "end_info";
    chunk->extraInfo = "./";
    chunk->chunk = "PipeUtilization";
    chunk->id = "1";
    ret = trans->SendBuffer(chunk);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
}

////////////////////////////////////////FILETransport/////////////////////////////////////////
class TRANSPORT_TRANSPORT_ITRANSPORT_TEST : public testing::Test {
protected:
    virtual void SetUp() {}

    virtual void TearDown() {}

private:
};

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, FILETransport)
{
    GlobalMockObject::verify();

    struct tlv_req packet;
    std::shared_ptr<ITransport> trans(new FILETransport("/tmp", "200MB"));

    EXPECT_EQ(PROFILING_SUCCESS, trans->CloseSession());
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, SendBuffer_without_protobuf)
{
    GlobalMockObject::verify();

    std::shared_ptr<FILETransport> trans(new FILETransport("/tmp", "200MB"));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    trans->Init();

    // test the normal procests, fileChunkReq datamodule is PROFILING_IS_FROM_DEVICE
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> message(new analysis::dvvp::ProfileFileChunk());
    message->extraInfo = "null.64";
    message->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_DEVICE;

    MOCKER_CPP(
        &analysis::dvvp::transport::FileSlice::SaveDataToLocalFiles,
        int(analysis::dvvp::transport::FileSlice::*)(
            SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>, const std::string&))
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));

    EXPECT_EQ(PROFILING_SUCCESS, trans->SendBuffer(nullptr));
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(message));
    message->extraInfo = "null.0";
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(message));

    // test fileChunkReq datamodule is PROFILING_DEFAULT_DATA_MODULE
    message->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_DEFAULT_DATA_MODULE;
    EXPECT_EQ(PROFILING_SUCCESS, trans->SendBuffer(message));
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, SendBuffer)
{
    GlobalMockObject::verify();

    std::shared_ptr<FILETransport> trans(new FILETransport("/tmp", "200MB"));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    trans->Init();

    std::string buff = "test SendBuffer";
    EXPECT_EQ(0, trans->SendBuffer(buff.c_str(), 0));
}

TEST_F(TRANSPORT_TRANSPORT_TRANSPORTFACTORY_TEST, CreateFileTransport)
{
    GlobalMockObject::verify();

    std::string storageDir = "";
    bool needSlice = true;
    std::string fileNameType = "EP";
    auto trans = FileTransportFactory().CreateFileTransport(storageDir, "200MB", needSlice);
    EXPECT_EQ((ITransport*)NULL, trans.get());
    storageDir = "/tmp";
    auto trans_ = FileTransportFactory().CreateFileTransport(storageDir, "200MB", needSlice);
    EXPECT_NE((ITransport*)NULL, trans_.get());
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, SendBufferForMsprof)
{
    GlobalMockObject::verify();

    std::shared_ptr<FILETransport> trans(new FILETransport("/tmp", "200MB"));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    trans->SetAbility(true);
    trans->Init();

    std::shared_ptr<analysis::dvvp::proto::FileChunkReq> message(new analysis::dvvp::proto::FileChunkReq());
    analysis::dvvp::message::JobContext job_ctx;
    job_ctx.dev_id = "0";
    job_ctx.job_id = "123456789";
    message->mutable_hdr()->set_job_ctx(job_ctx.ToString());
    message->set_datamodule(analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF);
    message->set_filename("data/test");
    std::string buff = analysis::dvvp::message::EncodeMessage(message);

    // test fileChunkReq datamodule is PROFILING_IS_FROM_DEVICE
    MOCKER(analysis::dvvp::common::utils::Utils::CheckStringIsNonNegativeIntNum)
        .stubs()
        .will(returnValue(true))
        .then(returnValue(true));

    EXPECT_EQ(0, trans->SendBuffer(buff.c_str(), buff.size()));
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, AdxHdcServerAccept)
{
    GlobalMockObject::verify();

    EXPECT_EQ(nullptr, AdxHdcServerAccept(nullptr));
}

int32_t HdcServerDestroyStub(HDC_SERVER server)
{
    int32_t* dataPtr = static_cast<int32_t*>(server);
    *dataPtr = 200;
    return DRV_ERROR_NONE;
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, AdxHdcServerDestroy)
{
    GlobalMockObject::verify();
    int32_t data = 100;
    HDC_SERVER server = &data;
    MOCKER(&HdcServerDestroy).stubs().will(invoke(HdcServerDestroyStub));
    AdxHdcServerDestroy(server);
    int32_t* dataPtr = static_cast<int32_t*>(server);
    EXPECT_EQ(*dataPtr, 200);
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, AdxHalHdcSessionConnect)
{
    GlobalMockObject::verify();

    EXPECT_EQ(DRV_ERROR_NONE, AdxHalHdcSessionConnect(0, 0, 0, nullptr, nullptr));
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, AdxIdeGetVfIdBySession)
{
    GlobalMockObject::verify();

    int32_t vfId = -1;
    EXPECT_EQ(IDE_DAEMON_OK, AdxIdeGetVfIdBySession((HDC_SESSION)0x1, vfId));
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, SendBuffer_TLV)
{
    GlobalMockObject::verify();

    std::shared_ptr<FILETransport> trans(new FILETransport("/tmp", "200MB"));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    trans->Init();

    std::shared_ptr<analysis::dvvp::ProfileFileChunk> message(new analysis::dvvp::ProfileFileChunk());
    message->extraInfo = "trace000000017775175798806765773.0";
    message->chunkModule = FileChunkDataModule::PROFILING_IS_FROM_DEVICE;
    message->fileName = "data/adprof.data.null";
    MOCKER_CPP(&FILETransport::ParseTlvChunk)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_FAILED));
    EXPECT_EQ(PROFILING_SUCCESS, trans->SendBuffer(message));
    EXPECT_EQ(PROFILING_FAILED, trans->SendBuffer(message));
}

ProfTlv GenerateProfTlvData(
    bool isLastChunk, int32_t chunkModule, size_t offset, std::string chunk, std::string fileName,
    std::string extraInfo, std::string id)
{
    ProfTlvValue data;
    data.isLastChunk = isLastChunk;
    data.chunkModule = chunkModule;
    data.chunkSize = chunk.size();
    data.offset = offset;

    strcpy_s(data.chunk, TLV_VALUE_CHUNK_MAX_LEN, chunk.c_str());
    strcpy_s(data.fileName, TLV_VALUE_FILENAME_MAX_LEN, fileName.c_str());
    strcpy_s(data.extraInfo, TLV_VALUE_EXTRAINFO_MAX_LEN, extraInfo.c_str());
    strcpy_s(data.id, TLV_VALUE_ID_MAX_LEN, id.c_str());

    struct ProfTlv tlv;
    tlv.head = TLV_HEAD;
    tlv.version = 0x100;
    tlv.type = 1;
    tlv.len = sizeof(ProfTlvValue);
    memcpy_s(tlv.value, TLV_VALUE_MAX_LEN, &data, sizeof(ProfTlvValue));
    return tlv;
}

uint64_t HashDataGenHashIdWrapper(const std::string& str) { return str.length(); }

// ParseStr2IdChunk 的 hashDataGenIdFuncPtr_ 只接受 free function 指针，无法捕获局部状态，
// 因此用一个文件作用域的 vector 收集喂入 AddHashData 的字符串，每个用例首尾各 clear 一次。
std::vector<std::string> g_str2idCollected;

// 注册给 FILETransport 的伪 GenHashId 回调：把待注册的 hash 字符串记录下来，
// 返回值仅用于占位（hashDataGenIdFuncPtr_ 期望返回 uint64_t hashId）。
uint64_t CollectStr2IdHash(const std::string& s)
{
    g_str2idCollected.push_back(s);
    return static_cast<uint64_t>(g_str2idCollected.size());
}

// 模拟 device 侧 DevprofDrvAicpu::AddStr2IdIntoBuffer：把一段 ASCII payload 装进
// 一个 MsprofAdditionalInfo（24B 二进制头 + 232B data，dataLen 标记有效字节，
// data 末尾 232 - dataLen 字节是 NUL 填充——这就是修复前会污染解析结果的根源）。
MsprofAdditionalInfo MakeStr2IdStruct(const std::string& payload)
{
    MsprofAdditionalInfo info{};
    info.magicNumber = MSPROF_REPORT_DATA_MAGIC_NUM;
    info.dataLen = static_cast<uint32_t>(payload.size());
    (void)memset_s(info.data, MSPROF_ADDTIONAL_INFO_DATA_LENGTH, 0, MSPROF_ADDTIONAL_INFO_DATA_LENGTH);
    if (!payload.empty()) {
        size_t cpyLen = std::min<size_t>(payload.size(), MSPROF_ADDTIONAL_INFO_DATA_LENGTH);
        (void)memcpy_s(info.data, MSPROF_ADDTIONAL_INFO_DATA_LENGTH, payload.c_str(), cpyLen);
    }
    return info;
}

// 模拟 host 侧 ReceiveData::DumpAdprofData：把 N 个 struct 紧密拼成 raw 二进制流
// 塞进 ProfileFileChunk::chunk，正是 ParseStr2IdChunk 实际收到的输入。
std::string PackStr2IdStructs(const std::vector<MsprofAdditionalInfo>& arr)
{
    std::string out;
    out.reserve(arr.size() * sizeof(MsprofAdditionalInfo));
    for (const auto& info : arr) {
        out.append(reinterpret_cast<const char*>(&info), sizeof(MsprofAdditionalInfo));
    }
    return out;
}

// 关键断言：注册到 HashData 的字符串应是干净 ASCII，不能残留 NUL（struct 末尾填充）
// 或 0x5A5A magic（下一个 struct 的二进制头开头）——这两类残留是修复前直写磁盘出乱码的特征。
void ExpectNoBinaryGarbage(const std::string& s, const char* hint)
{
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        EXPECT_NE(c, 0x00) << hint << ": NUL leaked at offset " << i;
        if (i + 1 < s.size()) {
            unsigned char n = static_cast<unsigned char>(s[i + 1]);
            EXPECT_FALSE(c == 0x5A && n == 0x5A) << hint << ": 0x5A5A leaked at offset " << i;
        }
    }
}

TEST_F(TRANSPORT_TRANSPORT_ITRANSPORT_TEST, ParseTlvChunk)
{
    GlobalMockObject::verify();

    std::shared_ptr<FILETransport> trans(new FILETransport("/tmp", "200MB"));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    trans->Init();

    std::shared_ptr<analysis::dvvp::ProfileFileChunk> message = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    message->fileName = "data/adprof.data.null";
    message->chunkModule = FileChunkDataModule::PROFILING_IS_FROM_DEVICE;
    ProfTlv tlv_data1 = GenerateProfTlvData(false, 0, -1, "12345", "test.data", "no extra", "123456");
    ProfTlv tlv_data2 = GenerateProfTlvData(false, 0, -1, "faef", "test.data", "no extra", "123456");
    message->chunk = std::string();
    message->chunk.reserve(2 * sizeof(ProfTlv));
    message->chunk.insert(0, std::string(reinterpret_cast<CHAR_PTR>(&tlv_data1), sizeof(ProfTlv)));
    message->chunk.insert(sizeof(ProfTlv), std::string(reinterpret_cast<CHAR_PTR>(&tlv_data2), 100));
    message->chunkSize = message->chunk.size();
    message->extraInfo = "trace000000017775175798806765773.0";

    MOCKER_CPP(&FileSlice::SaveDataToLocalFiles).stubs().will(returnValue(PROFILING_SUCCESS));

    EXPECT_EQ(PROFILING_SUCCESS, trans->ParseTlvChunk(message));
    message->chunk = std::string(reinterpret_cast<CHAR_PTR>(&tlv_data2) + 100, sizeof(ProfTlv) - 100);
    message->chunkSize = message->chunk.size();
    EXPECT_EQ(PROFILING_SUCCESS, trans->ParseTlvChunk(message));

    tlv_data1.head = 111;
    message->chunk = std::string(reinterpret_cast<CHAR_PTR>(&tlv_data1), sizeof(ProfTlv));
    message->chunkSize = message->chunk.size();
    EXPECT_EQ(PROFILING_FAILED, trans->ParseTlvChunk(message));

    tlv_data1.head = TLV_HEAD;
    tlv_data1.len = TLV_VALUE_MAX_LEN + 1;
    message->chunk = std::string(reinterpret_cast<CHAR_PTR>(&tlv_data1), sizeof(ProfTlv));
    message->chunkSize = message->chunk.size();
    EXPECT_EQ(PROFILING_FAILED, trans->ParseTlvChunk(message));

    ProfTlvValue tlvValue;
    tlvValue.chunkSize = TLV_VALUE_CHUNK_MAX_LEN + 1;
    memcpy_s(tlv_data1.value, TLV_VALUE_MAX_LEN, &tlvValue, sizeof(ProfTlvValue));
    tlv_data1.len = sizeof(ProfTlvValue);
    message->chunk = std::string(reinterpret_cast<CHAR_PTR>(&tlv_data1), sizeof(ProfTlv));
    message->chunkSize = message->chunk.size();
    EXPECT_EQ(PROFILING_FAILED, trans->ParseTlvChunk(message));
}

////////////////////////////////////////HelperTransportFactory/////////////////////////////////////////
class HELPER_TRANSPORTFACTORY_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}
};

TEST_F(HELPER_TRANSPORTFACTORY_TEST, TransportFactory)
{
    GlobalMockObject::verify();

    std::shared_ptr<TransportFactory> fac(new TransportFactory());
    EXPECT_NE(nullptr, fac);
    fac.reset();
}

TEST_F(HELPER_TRANSPORTFACTORY_TEST, create_helper_transport_server)
{
    GlobalMockObject::verify();
    HDC_SERVER server = (HDC_SERVER)0x12345678;
    MOCKER(Analysis::Dvvp::Adx::AdxHdcServerAccept)
        .stubs()
        .will(returnValue((HDC_SESSION)0x12345678))
        .then(returnValue((HDC_SESSION) nullptr));
    EXPECT_EQ((ITransport*)NULL, HelperTransportFactory().CreateHdcServerTransport(0, nullptr).get());
    EXPECT_NE((ITransport*)NULL, HelperTransportFactory().CreateHdcServerTransport(0, server).get());
    EXPECT_EQ((ITransport*)NULL, HelperTransportFactory().CreateHdcServerTransport(0, server).get());
}

TEST_F(HELPER_TRANSPORTFACTORY_TEST, create_hdc_transport_client)
{
    GlobalMockObject::verify();

    HDC_CLIENT client = (HDC_CLIENT)0x12345678;
    int pid = 2023;
    int dev_id = 0;

    MOCKER(AdxHalHdcSessionConnect).stubs().will(returnValue(IDE_DAEMON_ERROR)).then(returnValue(IDE_DAEMON_OK));

    EXPECT_EQ((ITransport*)NULL, HelperTransportFactory().CreateHdcClientTransport(pid, dev_id, client).get());
    EXPECT_NE((ITransport*)NULL, HelperTransportFactory().CreateHdcClientTransport(pid, dev_id, client).get());
}

//////////////////////////////HelperTransport/////////////////////////////////////
class HELPERTRANSPORT_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}
};

TEST_F(HELPERTRANSPORT_TEST, HelperTransport)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans(new HelperTransport(session));
    EXPECT_NE(nullptr, trans);
    trans.reset();
}

TEST_F(HELPERTRANSPORT_TEST, SendBuffer)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans(new HelperTransport(session));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    void* buff = (void*)0x12345678;
    int length = 10;
    EXPECT_EQ(PROFILING_SUCCESS, trans->SendBuffer(buff, length));
}

TEST_F(HELPERTRANSPORT_TEST, SendBufferForProfileFileChunk)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans(new HelperTransport(session));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    std::string content =
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz";
    trans->perfCount_ = perfCount;

    SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq;
    fileChunkReq = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    fileChunkReq->isLastChunk = true;
    fileChunkReq->chunkModule = 2;
    fileChunkReq->offset = 0;
    fileChunkReq->chunkSize = content.size();
    fileChunkReq->chunk = content;
    fileChunkReq->fileName = "event.null";
    fileChunkReq->extraInfo = "null.0";
    EXPECT_EQ(PROFILING_SUCCESS, trans->SendBuffer(fileChunkReq));
}

TEST_F(HELPERTRANSPORT_TEST, CloseSession)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;

    std::shared_ptr<ITransport> trans_s(new HelperTransport(session));
    EXPECT_EQ(PROFILING_SUCCESS, trans_s->CloseSession());
    trans_s.reset();

    session = (HDC_SESSION)0x12345678;
    std::shared_ptr<ITransport> trans_c(new HelperTransport(session, true));
    trans_c->WriteDone();
    EXPECT_EQ(PROFILING_SUCCESS, trans_c->CloseSession());
    trans_c.reset();
}

TEST_F(HELPERTRANSPORT_TEST, ReceivePacket)
{
    GlobalMockObject::verify();

    ProfHalTlv* packet = nullptr;
    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<HelperTransport> trans_c(new HelperTransport(session, true));
    MOCKER_CPP(&Analysis::Dvvp::Adx::AdxHdcRead).stubs().will(returnValue(IDE_DAEMON_OK));
    trans_c->WriteDone();

    EXPECT_EQ(-1, trans_c->ReceivePacket(&packet));
    trans_c->FreePacket(packet);
    packet = nullptr;
    trans_c.reset();
}

TEST_F(HELPERTRANSPORT_TEST, PackingData)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    ProfHalStruct package;
    std::string fileName = "unaging.additional.type_info_dic";
    std::string extraInfo = "null.0";
    std::string content = "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz";
    std::shared_ptr<HelperTransport> trans(new HelperTransport(session));
    std::shared_ptr<PerfCount> perfCount(new PerfCount("test"));
    trans->perfCount_ = perfCount;
    SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq;
    fileChunkReq = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    fileChunkReq->isLastChunk = true;
    fileChunkReq->chunkModule = 2;
    fileChunkReq->offset = 0;
    fileChunkReq->chunkSize = content.size();
    fileChunkReq->chunk = content;
    fileChunkReq->fileName = fileName;
    fileChunkReq->extraInfo = extraInfo;

    EXPECT_EQ(EOK, trans->PackingData(package, fileChunkReq));
    EXPECT_EQ(2, package.chunkModule);
    EXPECT_EQ(0, package.offset);
    EXPECT_EQ(fileName, package.fileName);
    EXPECT_EQ(extraInfo, package.extraInfo);
    EXPECT_NE("", package.id);
}

TEST_F(HELPERTRANSPORT_TEST, SendPackingData)
{
    GlobalMockObject::verify();

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    ProfHalStruct package;
    SHARED_PTR_ALIA<ProfHalTlv> tlvbuff = nullptr;
    MSVP_MAKE_SHARED0(tlvbuff, ProfHalTlv, return);
    std::shared_ptr<HelperTransport> trans = nullptr;
    MSVP_MAKE_SHARED1(trans, HelperTransport, session, return);
    std::shared_ptr<PerfCount> perfCount = nullptr;
    MSVP_MAKE_SHARED1(perfCount, PerfCount, "test", return);
    std::string content =
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz";
    std::string checkContent =
        "stuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz "
        "abcdefghijklmnopqrstuvwxyz";
    trans->perfCount_ = perfCount;

    SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq;
    fileChunkReq = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    fileChunkReq->isLastChunk = true;
    fileChunkReq->chunkModule = 2;
    fileChunkReq->offset = 0;
    fileChunkReq->chunkSize = content.size();
    fileChunkReq->chunk = content;
    fileChunkReq->fileName = "event.null";
    fileChunkReq->extraInfo = "null.0";

    package.chunkModule = fileChunkReq->chunkModule;
    package.offset = fileChunkReq->offset;
    tlvbuff->head = HAL_HELPER_TLV_HEAD;
    tlvbuff->version = HAL_TLV_VERSION;
    tlvbuff->type = HELPER_TLV_TYPE;
    EXPECT_EQ(EOK, trans->PackingData(package, fileChunkReq));
    EXPECT_EQ(PROFILING_SUCCESS, trans->SendPackingData(fileChunkReq, package, tlvbuff));
    EXPECT_EQ(true, package.isLastChunk);
    EXPECT_EQ(checkContent, package.chunk);
}
