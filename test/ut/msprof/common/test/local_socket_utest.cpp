/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
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

#include <cerrno>
#include <string>

#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"

#include "errno/error_code.h"
#include "osal.h"
#include "socket/local_socket.h"
#include "utils/utils.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::socket;
using namespace analysis::dvvp::common::utils;

extern "C" {
OsalSockHandle OsalSocket(int32_t sockFamily, int32_t type, int32_t protocol)
{
    (void)sockFamily;
    (void)type;
    (void)protocol;
    return OSAL_EN_ERROR;
}

int32_t OsalBind(OsalSockHandle sockFd, OsalSockAddr *addr, OsalSocklen addrLen)
{
    (void)sockFd;
    (void)addr;
    (void)addrLen;
    return OSAL_EN_ERROR;
}

int32_t OsalListen(OsalSockHandle sockFd, int32_t backLog)
{
    (void)sockFd;
    (void)backLog;
    return OSAL_EN_ERROR;
}

OsalSockHandle OsalAccept(OsalSockHandle sockFd, OsalSockAddr *addr, OsalSocklen *addrLen)
{
    (void)sockFd;
    (void)addr;
    (void)addrLen;
    return OSAL_EN_ERROR;
}

int32_t OsalConnect(OsalSockHandle sockFd, OsalSockAddr *addr, OsalSocklen addrLen)
{
    (void)sockFd;
    (void)addr;
    (void)addrLen;
    return OSAL_EN_ERROR;
}

OsalSsize OsalSocketSend(OsalSockHandle sockFd, VOID *sendBuf, int32_t sendLen, int32_t sendFlag)
{
    (void)sockFd;
    (void)sendBuf;
    (void)sendLen;
    (void)sendFlag;
    return OSAL_EN_ERROR;
}

OsalSsize OsalSocketRecv(OsalSockHandle sockFd, VOID *recvBuf, int32_t recvLen, int32_t recvFlag)
{
    (void)sockFd;
    (void)recvBuf;
    (void)recvLen;
    (void)recvFlag;
    return OSAL_EN_ERROR;
}

int32_t OsalChmod(const CHAR *filename, int32_t mode)
{
    (void)filename;
    (void)mode;
    return OSAL_EN_ERROR;
}

int32_t OsalUnlink(const CHAR *filename)
{
    (void)filename;
    return OSAL_EN_OK;
}

int32_t OsalGetErrorCode(void)
{
    return 0;
}

int32_t OsalClose(int32_t fd)
{
    (void)fd;
    return OSAL_EN_OK;
}
}

namespace analysis {
namespace dvvp {
namespace common {
namespace utils {
CHAR_PTR Utils::GetErrno()
{
    static char errInfo[] = "ut errno";
    return errInfo;
}
} // namespace utils
} // namespace common
} // namespace dvvp
} // namespace analysis

class LOCAL_SOCKET_UTEST : public testing::Test {
protected:
    void TearDown() override
    {
        GlobalMockObject::verify();
        GlobalMockObject::reset();
    }
};

TEST_F(LOCAL_SOCKET_UTEST, Create)
{
    const int32_t backlog = 1;
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Create("", backlog));

    const std::string key = "create";
    MOCKER(OsalSocket)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Create(key, backlog));

    MOCKER(OsalBind)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK));
    MOCKER(OsalGetErrorCode)
        .stubs()
        .will(returnValue(0))
        .then(returnValue(EADDRINUSE));
    MOCKER(OsalChmod)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_OK))
        .then(returnValue(OSAL_EN_OK));
    MOCKER(OsalListen)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_OK));
    MOCKER(OsalClose).stubs().will(returnValue(OSAL_EN_OK));
    MOCKER(OsalUnlink).stubs().will(returnValue(OSAL_EN_OK));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Create(key, backlog));
    EXPECT_EQ(SOCKET_ERR_EADDRINUSE, LocalSocket::Create(key, backlog));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Create(key, backlog));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Create(key, backlog));
    EXPECT_EQ(OSAL_EN_OK, LocalSocket::Create(key, backlog));
}

TEST_F(LOCAL_SOCKET_UTEST, Open)
{
    MOCKER(OsalSocket)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_OK));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Open());
    EXPECT_EQ(OSAL_EN_OK, LocalSocket::Open());
}

TEST_F(LOCAL_SOCKET_UTEST, Accept)
{
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Accept(-1));

    MOCKER(OsalAccept)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_ERROR))
        .then(returnValue(10));
    MOCKER(OsalGetErrorCode)
        .stubs()
        .will(returnValue(0))
        .then(returnValue(EAGAIN));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Accept(1));
    EXPECT_EQ(SOCKET_ERR_EAGAIN, LocalSocket::Accept(1));
    EXPECT_EQ(10, LocalSocket::Accept(1));
}

TEST_F(LOCAL_SOCKET_UTEST, Connect)
{
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Connect(-1, "socket"));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Connect(1, ""));

    MOCKER(OsalConnect)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_OK));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Connect(1, "socket"));
    EXPECT_EQ(PROFILING_SUCCESS, LocalSocket::Connect(1, "socket"));
}

TEST_F(LOCAL_SOCKET_UTEST, SetRecvTimeOut)
{
    MOCKER(setsockopt)
        .stubs()
        .will(returnValue(-1))
        .then(returnValue(0));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::SetRecvTimeOut(1, 1, 1));
    EXPECT_EQ(PROFILING_SUCCESS, LocalSocket::SetRecvTimeOut(1, 1, 1));
}

TEST_F(LOCAL_SOCKET_UTEST, SetSendTimeOut)
{
    MOCKER(setsockopt)
        .stubs()
        .will(returnValue(-1))
        .then(returnValue(0));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::SetSendTimeOut(1, 1, 1));
    EXPECT_EQ(PROFILING_SUCCESS, LocalSocket::SetSendTimeOut(1, 1, 1));
}

TEST_F(LOCAL_SOCKET_UTEST, Recv)
{
    int32_t fd = 0;
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Recv(-1, &fd, 1, 0));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Recv(fd, nullptr, 1, 0));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Recv(fd, &fd, 0, 0));

    MOCKER(OsalSocketRecv)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_ERROR))
        .then(returnValue(10));
    MOCKER(OsalGetErrorCode)
        .stubs()
        .will(returnValue(0))
        .then(returnValue(EAGAIN));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Recv(fd, &fd, 1, 0));
    EXPECT_EQ(SOCKET_ERR_EAGAIN, LocalSocket::Recv(fd, &fd, 1, 0));
    EXPECT_EQ(10, LocalSocket::Recv(fd, &fd, 1, 0));
}

TEST_F(LOCAL_SOCKET_UTEST, Send)
{
    int32_t fd = 0;
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Send(-1, &fd, 1, 0));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Send(fd, nullptr, 1, 0));
    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Send(fd, &fd, 0, 0));

    MOCKER(OsalSocketSend)
        .stubs()
        .will(returnValue(OSAL_EN_ERROR))
        .then(returnValue(OSAL_EN_ERROR))
        .then(returnValue(10));
    MOCKER(OsalGetErrorCode)
        .stubs()
        .will(returnValue(0))
        .then(returnValue(EAGAIN));

    EXPECT_EQ(PROFILING_FAILED, LocalSocket::Send(fd, &fd, 1, 0));
    EXPECT_EQ(SOCKET_ERR_EAGAIN, LocalSocket::Send(fd, &fd, 1, 0));
    EXPECT_EQ(PROFILING_SUCCESS, LocalSocket::Send(fd, &fd, 1, 0));
}

TEST_F(LOCAL_SOCKET_UTEST, Close)
{
    int32_t fd = 0;
    MOCKER(OsalClose).stubs().will(returnValue(OSAL_EN_ERROR));
    LocalSocket::Close(fd);
    EXPECT_EQ(-1, fd);

    fd = -1;
    LocalSocket::Close(fd);
    EXPECT_EQ(-1, fd);
}
