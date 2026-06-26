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
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include <fcntl.h>
#include <unistd.h>
#include "securec.h"
#include "osal.h"

// osal.c 在 OSAL 编译开关下，对外 OsalXxx 接口均转发到 osal_linux.c 的 LinuxXxx 实现。
// 该用例覆盖 osal.c 的封装转发层（socket/write/系统信息/时间等），与 osal_linux_utest
// 互补：后者直接测 LinuxXxx，本用例测 OsalXxx -> LinuxXxx 的转发。
class OSAL_TEST : public testing::Test {
protected:
    void TearDown() override
    {
        GlobalMockObject::verify();
        GlobalMockObject::reset();
    }
};

TEST_F(OSAL_TEST, OsalSocketApis)
{
    struct sockaddr_in servAddr;
    (void)memset_s(&servAddr, sizeof(servAddr), 0, sizeof(servAddr));
    servAddr.sin_family = AF_INET;
    servAddr.sin_addr.s_addr = 0;
    servAddr.sin_port = htons(50002);
    OsalSocklen addrLen = sizeof(servAddr);

    // 非法 fd，转发到 LinuxXxx 后返回错误，覆盖各封装函数
    OsalSockHandle fd = OsalSocket(AF_INET, SOCK_STREAM, 0);
    EXPECT_EQ(OSAL_EN_ERROR, fd);

    EXPECT_EQ(OSAL_EN_ERROR, OsalBind(fd, reinterpret_cast<OsalSockAddr *>(&servAddr), addrLen));
    EXPECT_EQ(OSAL_EN_ERROR, OsalListen(fd, 5));
    EXPECT_EQ(OSAL_EN_ERROR, OsalAccept(fd, nullptr, nullptr));
    EXPECT_EQ(OSAL_EN_ERROR, OsalConnect(fd, reinterpret_cast<OsalSockAddr *>(&servAddr), addrLen));

    char buf[16] = "send";
    EXPECT_EQ(OSAL_EN_ERROR, OsalSocketSend(-1, buf, sizeof(buf), 0));
    EXPECT_EQ(OSAL_EN_ERROR, OsalSocketRecv(1, nullptr, sizeof(buf), 0));
}

TEST_F(OSAL_TEST, OsalWrite)
{
    char buf[16] = "data";
    // 非法 fd，转发到 LinuxWrite 命中入参检查分支
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalWrite(-1, buf, sizeof(buf)));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalWrite(1, nullptr, sizeof(buf)));

    // 真实写 /dev/null，覆盖正常写入路径
    int32_t fd = open("/dev/null", O_WRONLY);
    ASSERT_GE(fd, 0);
    EXPECT_EQ(static_cast<OsalSsize>(sizeof(buf)), OsalWrite(fd, buf, sizeof(buf)));
    close(fd);
}

TEST_F(OSAL_TEST, OsalGetTimeOfDay)
{
    OsalTimeval tv;
    OsalTimezone tz;
    EXPECT_EQ(OSAL_EN_OK, OsalGetTimeOfDay(&tv, &tz));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalGetTimeOfDay(nullptr, &tz));
}

TEST_F(OSAL_TEST, OsalGetOsName)
{
    char osName[OSAL_MIN_OS_NAME_SIZE] = {};
    EXPECT_EQ(OSAL_EN_OK, OsalGetOsName(osName, OSAL_MIN_OS_NAME_SIZE));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalGetOsName(nullptr, OSAL_MIN_OS_NAME_SIZE));
}

TEST_F(OSAL_TEST, OsalGetOsVersion)
{
    char osVersion[OSAL_MIN_OS_VERSION_SIZE] = {};
    EXPECT_EQ(OSAL_EN_OK, OsalGetOsVersion(osVersion, OSAL_MIN_OS_VERSION_SIZE));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalGetOsVersion(nullptr, OSAL_MIN_OS_VERSION_SIZE));
}

TEST_F(OSAL_TEST, OsalGetCpuInfo)
{
    OsalCpuDesc *desc = nullptr;
    int32_t count = 0;
    EXPECT_EQ(OSAL_EN_OK, OsalGetCpuInfo(&desc, &count));
    EXPECT_EQ(OSAL_EN_OK, OsalCpuInfoFree(desc, count));

    int32_t cnt = 1;
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalGetCpuInfo(nullptr, &cnt));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, OsalCpuInfoFree(nullptr, count));
}
