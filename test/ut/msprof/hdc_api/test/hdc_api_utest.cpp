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
#include <cstring>
#include <string>
#include "securec.h"
#include "hdc_api.h"
#include "extra_config.h"
#include "osal.h"

using namespace Analysis::Dvvp::Adx;

static hdcError_t stub_drvHdcClientCreate_Fail(HDC_CLIENT *client, int maxSessionNum, int serviceType, int flag) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcServerCreate_NotReady(int devid, int serviceType, HDC_SERVER *pServer) {
    return DRV_ERROR_DEVICE_NOT_READY;
}

static hdcError_t stub_drvHdcServerCreate_Fail(int devid, int serviceType, HDC_SERVER *pServer) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcServerDestroy_Busy(HDC_SERVER server) {
    return DRV_ERROR_CLIENT_BUSY;
}

static hdcError_t stub_drvHdcSessionAccept_Fail(HDC_SERVER server, HDC_SESSION *session) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcSetSessionReference_Fail(HDC_SESSION session) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcSessionClose_Fail(HDC_SESSION session) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcGetCapacity_Fail(struct drvHdcCapacity *capacity) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcGetCapacity_InvalidSeg(struct drvHdcCapacity *capacity) {
    capacity->maxSegment = 1;
    return DRV_ERROR_NONE;
}

static hdcError_t stub_drvHdcGetCapacity_Valid(struct drvHdcCapacity *capacity) {
    capacity->maxSegment = 4096;
    return DRV_ERROR_NONE;
}

static hdcError_t stub_drvHdcAllocMsg_Success(HDC_SESSION session, struct drvHdcMsg **ppMsg, int count) {
    static struct drvHdcMsg msg;
    *ppMsg = &msg;
    return DRV_ERROR_NONE;
}

static hdcError_t stub_halHdcGetSessionAttr_Fail(HDC_SESSION session, int attr, int *value) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_halHdcRecv_NonBlock(HDC_SESSION session, struct drvHdcMsg *msg, int bufLen,
    unsigned long long flag, int *recvBufCount, unsigned int timeout) {
    *recvBufCount = 0;
    return DRV_ERROR_NON_BLOCK;
}

static hdcError_t stub_halHdcRecv_SockClose(HDC_SESSION session, struct drvHdcMsg *msg, int bufLen,
    unsigned long long flag, int *recvBufCount, unsigned int timeout) {
    *recvBufCount = 0;
    return DRV_ERROR_SOCKET_CLOSE;
}

static hdcError_t stub_halHdcRecv_Timeout(HDC_SESSION session, struct drvHdcMsg *msg, int bufLen,
    unsigned long long flag, int *recvBufCount, unsigned int timeout) {
    *recvBufCount = 0;
    return DRV_ERROR_WAIT_TIMEOUT;
}

static hdcError_t stub_halHdcRecv_Error(HDC_SESSION session, struct drvHdcMsg *msg, int bufLen,
    unsigned long long flag, int *recvBufCount, unsigned int timeout) {
    *recvBufCount = 0;
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_halHdcSend_Fail(HDC_SESSION session, struct drvHdcMsg *msg,
    unsigned long long flag, unsigned int timeout) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcAllocMsg_Fail(HDC_SESSION session, struct drvHdcMsg **ppMsg, int count) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcReuseMsg_Fail(struct drvHdcMsg *msg) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcFreeMsg_Fail(struct drvHdcMsg *msg) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcAddMsgBuffer_Fail(struct drvHdcMsg *msg, char *pBuf, int len) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_drvHdcSessionConnect_Fail(int peer_node, int peer_devid,
    HDC_CLIENT client, HDC_SESSION *session) {
    return DRV_ERROR_INVALID_VALUE;
}

static hdcError_t stub_halHdcSessionConnectEx_Fail(int peer_node, int peer_devid,
    int host_pid, HDC_CLIENT client, HDC_SESSION *session) {
    return DRV_ERROR_INVALID_VALUE;
}

class HDC_API_TEST : public testing::Test {
protected:
    virtual void SetUp() {
        GlobalMockObject::verify();
    }
    virtual void TearDown() {
        GlobalMockObject::verify();
    }
};

// ================================ HdcClientInit ================================

TEST_F(HDC_API_TEST, HdcClientInit_Success) {
    HDC_CLIENT client = nullptr;
    EXPECT_EQ(IDE_DAEMON_OK, HdcClientInit(&client));
    EXPECT_NE(nullptr, client);
}

TEST_F(HDC_API_TEST, HdcClientInit_NullClient) {
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcClientInit(nullptr));
}

TEST_F(HDC_API_TEST, HdcClientInit_CreateFail) {
    MOCKER(drvHdcClientCreate).stubs().will(invoke(stub_drvHdcClientCreate_Fail));
    HDC_CLIENT client = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcClientInit(&client));
    GlobalMockObject::verify();
}

// ================================ HdcClientCreate ================================

TEST_F(HDC_API_TEST, HdcClientCreate_Success) {
    HDC_CLIENT client = HdcClientCreate(HDC_SERVICE_TYPE_IDE1);
    EXPECT_NE(nullptr, client);
}

TEST_F(HDC_API_TEST, HdcClientCreate_Fail) {
    MOCKER(drvHdcClientCreate).stubs().will(invoke(stub_drvHdcClientCreate_Fail));
    HDC_CLIENT client = HdcClientCreate(HDC_SERVICE_TYPE_IDE1);
    EXPECT_EQ(nullptr, client);
    GlobalMockObject::verify();
}

// ================================ HdcClientDestroy ================================

TEST_F(HDC_API_TEST, HdcClientDestroy_Null) {
    EXPECT_EQ(IDE_DAEMON_OK, HdcClientDestroy(nullptr));
}

TEST_F(HDC_API_TEST, HdcClientDestroy_Success) {
    HDC_CLIENT client = (HDC_CLIENT)0x1234;
    EXPECT_EQ(IDE_DAEMON_OK, HdcClientDestroy(client));
}

TEST_F(HDC_API_TEST, HdcClientDestroy_Fail) {
    HDC_CLIENT client = (HDC_CLIENT)0x1234;
    MOCKER(drvHdcClientDestroy).stubs().will(returnValue(DRV_ERROR_INVALID_VALUE));
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcClientDestroy(client));
    GlobalMockObject::verify();
}

// ================================ HdcServerCreate ================================

TEST_F(HDC_API_TEST, HdcServerCreate_Success) {
    HDC_SERVER server = HdcServerCreate(0, HDC_SERVICE_TYPE_IDE1);
    EXPECT_NE(nullptr, server);
}

TEST_F(HDC_API_TEST, HdcServerCreate_NotReady) {
    MOCKER(drvHdcServerCreate).stubs().will(invoke(stub_drvHdcServerCreate_NotReady));
    HDC_SERVER server = HdcServerCreate(0, HDC_SERVICE_TYPE_IDE1);
    EXPECT_EQ(nullptr, server);
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcServerCreate_Fail) {
    MOCKER(drvHdcServerCreate).stubs().will(invoke(stub_drvHdcServerCreate_Fail));
    HDC_SERVER server = HdcServerCreate(0, HDC_SERVICE_TYPE_IDE1);
    EXPECT_EQ(nullptr, server);
    GlobalMockObject::verify();
}

// ================================ HdcServerDestroy ================================

TEST_F(HDC_API_TEST, HdcServerDestroy_Null) {
    HdcServerDestroy(nullptr);
}

TEST_F(HDC_API_TEST, HdcServerDestroy_Success) {
    HDC_SERVER server = (HDC_SERVER)0x1234;
    HdcServerDestroy(server);
}

TEST_F(HDC_API_TEST, HdcServerDestroy_BusyRetry) {
    HDC_SERVER server = (HDC_SERVER)0x1234;
    MOCKER(drvHdcServerDestroy).stubs().will(invoke(stub_drvHdcServerDestroy_Busy));
    MOCKER(OsalSleep).stubs().will(returnValue(0));
    HdcServerDestroy(server);
    GlobalMockObject::verify();
}

// ================================ HdcServerAccept ================================

TEST_F(HDC_API_TEST, HdcServerAccept_Success) {
    HDC_SERVER server = (HDC_SERVER)0x1234;
    HDC_SESSION session = HdcServerAccept(server);
    EXPECT_NE(nullptr, session);
}

TEST_F(HDC_API_TEST, HdcServerAccept_Fail) {
    HDC_SERVER server = (HDC_SERVER)0x1234;
    MOCKER(drvHdcSessionAccept).stubs().will(invoke(stub_drvHdcSessionAccept_Fail));
    HDC_SESSION session = HdcServerAccept(server);
    EXPECT_EQ(nullptr, session);
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcServerAccept_SetRefFail) {
    HDC_SERVER server = (HDC_SERVER)0x1234;
    MOCKER(drvHdcSetSessionReference).stubs().will(invoke(stub_drvHdcSetSessionReference_Fail));
    HDC_SESSION session = HdcServerAccept(server);
    EXPECT_EQ(nullptr, session);
    GlobalMockObject::verify();
}

// ================================ HdcStorePackage ================================

TEST_F(HDC_API_TEST, HdcStorePackage_Success) {
    uint32_t dataLen = 5;
    struct IdeHdcPacket *packet = (struct IdeHdcPacket *)malloc(sizeof(struct IdeHdcPacket) + dataLen);
    packet->type = IDE_DAEMON_LITTLE_PACKAGE;
    packet->len = dataLen;
    packet->isLast = 0;
    const char *data = "hello";
    (void)memcpy_s(packet->value, dataLen, data, dataLen);
    struct IoVec ioVec = {nullptr, 0};
    EXPECT_EQ(IDE_DAEMON_OK, HdcStorePackage(*packet, ioVec));
    EXPECT_EQ(dataLen, ioVec.len);
    if (ioVec.base) {
        free(ioVec.base);
    }
    free(packet);
}

TEST_F(HDC_API_TEST, HdcStorePackage_NotLittlePackage) {
    IdeHdcPacket packet;
    packet.type = IDE_DAEMON_BIG_PACKAGE;
    packet.len = 0;
    struct IoVec ioVec = {nullptr, 0};
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcStorePackage(packet, ioVec));
}

TEST_F(HDC_API_TEST, HdcStorePackage_Overflow) {
    IdeHdcPacket packet;
    packet.type = IDE_DAEMON_LITTLE_PACKAGE;
    packet.len = 10;
    struct IoVec ioVec = {(char*)0x1, UINT32_MAX};
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcStorePackage(packet, ioVec));
}

// ================================ HdcReadIovecToMem ================================

TEST_F(HDC_API_TEST, HdcReadIovecToMem_NullRecvLen) {
    std::list<struct IoVec> ioList;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcReadIovecToMem(ioList, 10, nullptr, nullptr));
}

TEST_F(HDC_API_TEST, HdcReadIovecToMem_ZeroBufLen) {
    std::list<struct IoVec> ioList;
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcReadIovecToMem(ioList, 0, &recvBuf, &recvLen));
}

TEST_F(HDC_API_TEST, HdcReadIovecToMem_NullRecvBuf) {
    std::list<struct IoVec> ioList;
    int32_t recvLen = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcReadIovecToMem(ioList, 10, nullptr, &recvLen));
}

TEST_F(HDC_API_TEST, HdcReadIovecToMem_Success) {
    std::list<struct IoVec> ioList;
    struct IoVec vec;
    vec.base = malloc(5);
    (void)memcpy_s(vec.base, 5, "hello", 5);
    vec.len = 5;
    ioList.push_back(vec);
    IdeMemHandle recvBuf = nullptr;
    int32_t recvLen = 0;
    EXPECT_EQ(IDE_DAEMON_OK, HdcReadIovecToMem(ioList, 5, &recvBuf, &recvLen));
    EXPECT_EQ(5, recvLen);
    if (recvBuf) {
        free(recvBuf);
    }
}

TEST_F(HDC_API_TEST, HdcReadIovecToMem_SuccessWithMultipleVecs) {
    std::list<struct IoVec> ioList;
    struct IoVec vec1;
    vec1.base = malloc(5);
    (void)memcpy_s(vec1.base, 5, "hello", 5);
    vec1.len = 5;
    ioList.push_back(vec1);
    struct IoVec vec2;
    vec2.base = malloc(5);
    (void)memcpy_s(vec2.base, 5, "world", 5);
    vec2.len = 5;
    ioList.push_back(vec2);
    IdeMemHandle recvBuf = nullptr;
    int32_t recvLen = 0;
    EXPECT_EQ(IDE_DAEMON_OK, HdcReadIovecToMem(ioList, 10, &recvBuf, &recvLen));
    EXPECT_EQ(10, recvLen);
    if (recvBuf) {
        free(recvBuf);
    }
}

// ================================ HdcRead ================================

TEST_F(HDC_API_TEST, HdcRead_NullSession) {
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcRead(nullptr, &recvBuf, &recvLen, 0));
}

TEST_F(HDC_API_TEST, HdcRead_NullRecvBuf) {
    int32_t recvLen = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcRead((HDC_SESSION)0x1, nullptr, &recvLen, 0));
}

TEST_F(HDC_API_TEST, HdcRead_NullRecvLen) {
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcRead((HDC_SESSION)0x1, &recvBuf, nullptr, 0));
}

TEST_F(HDC_API_TEST, HdcRead_AllocMsgFail) {
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Fail));
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcRead((HDC_SESSION)0x1, &recvBuf, &recvLen, 0));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcRead_NonBlock) {
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(halHdcRecv).stubs().will(invoke(stub_halHdcRecv_NonBlock));
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_RECV_NODATA, HdcRead((HDC_SESSION)0x1, &recvBuf, &recvLen, 0));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcRead_SockClose) {
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(halHdcRecv).stubs().will(invoke(stub_halHdcRecv_SockClose));
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_SOCK_CLOSE, HdcRead((HDC_SESSION)0x1, &recvBuf, &recvLen, 0));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcRead_Timeout) {
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(halHdcRecv).stubs().will(invoke(stub_halHdcRecv_Timeout));
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcRead((HDC_SESSION)0x1, &recvBuf, &recvLen, 0));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcRead_RecvError) {
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(halHdcRecv).stubs().will(invoke(stub_halHdcRecv_Error));
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcRead((HDC_SESSION)0x1, &recvBuf, &recvLen, 0));
    GlobalMockObject::verify();
}

// ================================ HdcReadNb ================================

TEST_F(HDC_API_TEST, HdcReadNb_NullSession) {
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcReadNb(nullptr, &recvBuf, &recvLen));
}

TEST_F(HDC_API_TEST, HdcReadNb_NonBlock) {
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(halHdcRecv).stubs().will(invoke(stub_halHdcRecv_NonBlock));
    int32_t recvLen = 0;
    IdeMemHandle recvBuf = nullptr;
    EXPECT_EQ(IDE_DAEMON_RECV_NODATA, HdcReadNb((HDC_SESSION)0x1, &recvBuf, &recvLen));
    GlobalMockObject::verify();
}

// ================================ HdcWrite ================================

TEST_F(HDC_API_TEST, HdcWrite_NullSession) {
    char buf[] = "test";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite(nullptr, buf, 4));
}

TEST_F(HDC_API_TEST, HdcWrite_InvalidLen) {
    char buf[] = "test";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite((HDC_SESSION)0x1, buf, 0));
}

TEST_F(HDC_API_TEST, HdcWrite_NullBuf) {
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite((HDC_SESSION)0x1, nullptr, 4));
}

TEST_F(HDC_API_TEST, HdcWrite_Success) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    char buf[] = "hello world test data";
    EXPECT_EQ(IDE_DAEMON_OK, HdcWrite((HDC_SESSION)0x1, buf, 21));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcWrite_AddMsgBufferFail) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(drvHdcAddMsgBuffer).stubs().will(invoke(stub_drvHdcAddMsgBuffer_Fail));
    char buf[] = "hello";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite((HDC_SESSION)0x1, buf, 5));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcWrite_SendFail) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(halHdcSend).stubs().will(invoke(stub_halHdcSend_Fail));
    char buf[] = "hello";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite((HDC_SESSION)0x1, buf, 5));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcWrite_ReuseMsgFail) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(drvHdcReuseMsg).stubs().will(invoke(stub_drvHdcReuseMsg_Fail));
    char buf[] = "hello";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite((HDC_SESSION)0x1, buf, 5));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcWrite_FreeMsgFail) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    MOCKER(drvHdcFreeMsg).stubs().will(invoke(stub_drvHdcFreeMsg_Fail));
    char buf[] = "hello";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWrite((HDC_SESSION)0x1, buf, 5));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcWrite_LargeData) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    char buf[600 * 1024];
    (void)memset_s(buf, sizeof(buf), 'x', sizeof(buf));
    EXPECT_EQ(IDE_DAEMON_OK, HdcWrite((HDC_SESSION)0x1, buf, sizeof(buf)));
    GlobalMockObject::verify();
}

// ================================ HdcWriteNb ================================

TEST_F(HDC_API_TEST, HdcWriteNb_NullSession) {
    char buf[] = "test";
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcWriteNb(nullptr, buf, 4));
}

TEST_F(HDC_API_TEST, HdcWriteNb_Success) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    MOCKER(drvHdcAllocMsg).stubs().will(invoke(stub_drvHdcAllocMsg_Success));
    char buf[] = "hello";
    EXPECT_EQ(IDE_DAEMON_OK, HdcWriteNb((HDC_SESSION)0x1, buf, 5));
    GlobalMockObject::verify();
}

// ================================ HdcSessionConnect ================================

TEST_F(HDC_API_TEST, HdcSessionConnect_InvalidPeerNode) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionConnect(-1, 0, client, &session));
}

TEST_F(HDC_API_TEST, HdcSessionConnect_InvalidPeerDevid) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionConnect(0, -1, client, &session));
}

TEST_F(HDC_API_TEST, HdcSessionConnect_NullClient) {
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionConnect(0, 0, nullptr, &session));
}

TEST_F(HDC_API_TEST, HdcSessionConnect_NullSession) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionConnect(0, 0, client, nullptr));
}

TEST_F(HDC_API_TEST, HdcSessionConnect_Success) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_OK, HdcSessionConnect(0, 0, client, &session));
    EXPECT_NE(nullptr, session);
}

TEST_F(HDC_API_TEST, HdcSessionConnect_ConnectFail) {
    MOCKER(drvHdcSessionConnect).stubs().will(invoke(stub_drvHdcSessionConnect_Fail));
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionConnect(0, 0, client, &session));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcSessionConnect_SetRefFail) {
    MOCKER(drvHdcSetSessionReference).stubs().will(invoke(stub_drvHdcSetSessionReference_Fail));
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionConnect(0, 0, client, &session));
    GlobalMockObject::verify();
}

// ================================ HalHdcSessionConnect ================================

TEST_F(HDC_API_TEST, HalHdcSessionConnect_InvalidPeerNode) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HalHdcSessionConnect(-1, 0, 1, client, &session));
}

TEST_F(HDC_API_TEST, HalHdcSessionConnect_InvalidHostPid) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HalHdcSessionConnect(0, 0, -1, client, &session));
}

TEST_F(HDC_API_TEST, HalHdcSessionConnect_Success) {
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_OK, HalHdcSessionConnect(0, 0, 1, client, &session));
    EXPECT_NE(nullptr, session);
}

TEST_F(HDC_API_TEST, HalHdcSessionConnect_ConnectFail) {
    MOCKER(halHdcSessionConnectEx).stubs().will(invoke(stub_halHdcSessionConnectEx_Fail));
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HalHdcSessionConnect(0, 0, 1, client, &session));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HalHdcSessionConnect_SetRefFail) {
    MOCKER(drvHdcSetSessionReference).stubs().will(invoke(stub_drvHdcSetSessionReference_Fail));
    HDC_CLIENT client = (HDC_CLIENT)0x1;
    HDC_SESSION session = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, HalHdcSessionConnect(0, 0, 1, client, &session));
    GlobalMockObject::verify();
}

// ================================ HdcSessionClose ================================

TEST_F(HDC_API_TEST, HdcSessionClose_NullSession) {
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionClose(nullptr));
}

TEST_F(HDC_API_TEST, HdcSessionClose_Success) {
    EXPECT_EQ(IDE_DAEMON_OK, HdcSessionClose((HDC_SESSION)0x1));
}

TEST_F(HDC_API_TEST, HdcSessionClose_Fail) {
    MOCKER(drvHdcSessionClose).stubs().will(invoke(stub_drvHdcSessionClose_Fail));
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionClose((HDC_SESSION)0x1));
    GlobalMockObject::verify();
}

// ================================ HdcSessionDestroy ================================

TEST_F(HDC_API_TEST, HdcSessionDestroy_NullSession) {
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcSessionDestroy(nullptr));
}

TEST_F(HDC_API_TEST, HdcSessionDestroy_Success) {
    EXPECT_EQ(IDE_DAEMON_OK, HdcSessionDestroy((HDC_SESSION)0x1));
}

// ================================ HdcCapacity ================================

TEST_F(HDC_API_TEST, HdcCapacity_Success) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Valid));
    uint32_t segment = 0;
    EXPECT_EQ(IDE_DAEMON_OK, HdcCapacity(&segment));
    EXPECT_EQ(4096u, segment);
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcCapacity_Fail) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_Fail));
    uint32_t segment = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcCapacity(&segment));
    GlobalMockObject::verify();
}

TEST_F(HDC_API_TEST, HdcCapacity_InvalidSegment) {
    MOCKER(drvHdcGetCapacity).stubs().will(invoke(stub_drvHdcGetCapacity_InvalidSeg));
    uint32_t segment = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, HdcCapacity(&segment));
    GlobalMockObject::verify();
}

// ================================ IdeGetDevIdBySession ================================

TEST_F(HDC_API_TEST, IdeGetDevIdBySession_NullSession) {
    int32_t devId = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeGetDevIdBySession(nullptr, &devId));
}

TEST_F(HDC_API_TEST, IdeGetDevIdBySession_NullDevId) {
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeGetDevIdBySession((HDC_SESSION)0x1, nullptr));
}

TEST_F(HDC_API_TEST, IdeGetDevIdBySession_Success) {
    int32_t devId = -1;
    EXPECT_EQ(IDE_DAEMON_OK, IdeGetDevIdBySession((HDC_SESSION)0x1, &devId));
    EXPECT_EQ(0, devId);
}

TEST_F(HDC_API_TEST, IdeGetDevIdBySession_Fail) {
    MOCKER(halHdcGetSessionAttr).stubs().will(invoke(stub_halHdcGetSessionAttr_Fail));
    int32_t devId = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeGetDevIdBySession((HDC_SESSION)0x1, &devId));
    GlobalMockObject::verify();
}

// ================================ IdeGetVfIdBySession ================================

TEST_F(HDC_API_TEST, IdeGetVfIdBySession_NullSession) {
    int32_t vfId = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeGetVfIdBySession(nullptr, vfId));
}

TEST_F(HDC_API_TEST, IdeGetVfIdBySession_Success) {
    int32_t vfId = -1;
    EXPECT_EQ(IDE_DAEMON_OK, IdeGetVfIdBySession((HDC_SESSION)0x1, vfId));
}

// ================================ IdeCreatePacket ================================

TEST_F(HDC_API_TEST, IdeCreatePacket_NullValue) {
    IdeMemHandle buf = nullptr;
    int32_t bufLen = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeCreatePacket(CmdClassT(), nullptr, 5, &buf, &bufLen));
}

TEST_F(HDC_API_TEST, IdeCreatePacket_NullBuf) {
    const char *value = "test";
    int32_t bufLen = 0;
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeCreatePacket(CmdClassT(), value, 4, nullptr, &bufLen));
}

TEST_F(HDC_API_TEST, IdeCreatePacket_NullBufLen) {
    const char *value = "test";
    IdeMemHandle buf = nullptr;
    EXPECT_EQ(IDE_DAEMON_ERROR, IdeCreatePacket(CmdClassT(), value, 4, &buf, nullptr));
}

TEST_F(HDC_API_TEST, IdeCreatePacket_Success) {
    const char *value = "test_data";
    IdeMemHandle buf = nullptr;
    int32_t bufLen = 0;
    EXPECT_EQ(IDE_DAEMON_OK, IdeCreatePacket(CmdClassT(), value, 9, &buf, &bufLen));
    EXPECT_NE(nullptr, buf);
    EXPECT_GT(bufLen, 0);
    IdeFreePacket(buf);
}
