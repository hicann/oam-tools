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
#include "adx_prof_api.h"
#include "memory_utils.h"

namespace Analysis {
namespace Dvvp {
namespace Adx {
using namespace analysis::dvvp::common::error;

int AdxIdeCreatePacket(CONST_VOID_PTR buffer, int length, IdeBuffT &outPut, int &outLen)
{
    MSPROF_LOGD("AdxIdeCreatePacket, length:%d, outLen:%d", length, outLen);
    return IDE_DAEMON_ERROR;
}

void AdxIdeFreePacket(IdeBuffT &out)
{
    return;
}

HDC_CLIENT AdxHdcClientCreate(drvHdcServiceType type)
{
    return nullptr;
}

int32_t AdxHdcClientDestroy(HDC_CLIENT client)
{
    return IDE_DAEMON_ERROR;
}

HDC_SERVER AdxHdcServerCreate(int32_t logDevId, drvHdcServiceType type)
{
    return nullptr;
}

void AdxHdcServerDestroy(HDC_SERVER server)
{
    return;
}

HDC_SESSION AdxHdcServerAccept(HDC_SERVER server)
{
    return nullptr;
}

int32_t AdxHdcSessionConnect(int32_t peerNode, int32_t peerDevid, HDC_CLIENT client, HDC_SESSION_PTR session)
{
    return IDE_DAEMON_ERROR;
}

int32_t AdxHalHdcSessionConnect(int32_t peerNode, int32_t peerDevid,
    int32_t hostPid, HDC_CLIENT client, HDC_SESSION_PTR session)
{
    return IDE_DAEMON_ERROR;
}

int32_t AdxHdcSessionClose(HDC_SESSION session)
{
    return IDE_DAEMON_ERROR;
}

int32_t AdxIdeGetDevIdBySession(HDC_SESSION session, IdeI32Pt devId)
{
    return IDE_DAEMON_ERROR;
}

int32_t AdxIdeGetVfIdBySession(HDC_SESSION session, int32_t &vfId)
{
    return IDE_DAEMON_ERROR;
}

int32_t AdxHdcSessionDestroy(HDC_SESSION session)
{
    return IDE_DAEMON_ERROR;
}

int32_t AdxHdcWrite(HDC_SESSION session, IdeSendBuffT buf, int32_t len)
{
    return IDE_DAEMON_ERROR;
}

int AdxHdcRead(HDC_SESSION session, IdeRecvBuffT recvBuf, IdeI32Pt recvLen, uint32_t timeout)
{
    return IDE_DAEMON_ERROR;
}
}  // namespace Adx
}  // namespace Dvvp
}  // namespace Analysis