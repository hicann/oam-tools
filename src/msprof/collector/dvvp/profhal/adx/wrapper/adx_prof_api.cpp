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
#include <cerrno>
#include <map>
#include "errno/error_code.h"
#include "securec.h"

namespace Analysis {
namespace Dvvp {
namespace Adx {
using namespace analysis::dvvp::common::error;

int32_t AdxIdeCreatePacket(CONST_VOID_PTR buffer, int32_t length, IdeBuffT &outPut, int32_t &outLen)
{
    int32_t len = 0;
    IdeBuffT out = nullptr;
    int32_t ret = IdeCreatePacket(IDE_PROFILING_REQ, // enum cmd_class
        (const char *)buffer, // value,
        length,               // value_len,
        &out,                 // buf
        &len);             // buf_len
    outLen = len;
    outPut = out;

    return ret;
}

void AdxIdeFreePacket(IdeBuffT &out)
{
    if (out != nullptr) {
        IdeFreePacket(out);
        out = nullptr;
    }
}

int32_t AdxHdcClientDestroy(HDC_CLIENT client)
{
    return Analysis::Dvvp::Adx::HdcClientDestroy(client);
}

HDC_SESSION AdxHdcServerAccept(HDC_SERVER server)
{
    return Analysis::Dvvp::Adx::HdcServerAccept(server);
}

void AdxHdcServerDestroy(HDC_SERVER server)
{
    Analysis::Dvvp::Adx::HdcServerDestroy(server);
}

int32_t AdxHdcSessionConnect(int32_t peerNode, int32_t peerDevid, HDC_CLIENT client, HDC_SESSION_PTR session)
{
    return Analysis::Dvvp::Adx::HdcSessionConnect(peerNode, peerDevid, client, session);
}

int32_t AdxHdcSessionClose(HDC_SESSION session)
{
    return Analysis::Dvvp::Adx::HdcSessionClose(session);
}

int32_t AdxHalHdcSessionConnect(int32_t peerNode, int32_t peerDevid,
    int32_t hostPid, HDC_CLIENT client, HDC_SESSION_PTR session)
{
    return Analysis::Dvvp::Adx::HalHdcSessionConnect(peerNode, peerDevid, hostPid, client, session);
}

int32_t AdxIdeGetDevIdBySession(HDC_SESSION session, IdeI32Pt devId)
{
    return Analysis::Dvvp::Adx::IdeGetDevIdBySession(session, devId);
}

int32_t AdxIdeGetVfIdBySession(HDC_SESSION session, int32_t &vfId)
{
    return Analysis::Dvvp::Adx::IdeGetVfIdBySession(session, vfId);
}

int32_t AdxHdcWrite(HDC_SESSION session, IdeSendBuffT buf, int32_t len)
{
    return Analysis::Dvvp::Adx::HdcWrite(session, buf, len);
}

int32_t AdxHdcSessionDestroy(HDC_SESSION session)
{
    return Analysis::Dvvp::Adx::HdcSessionDestroy(session);
}

int32_t AdxHdcRead(HDC_SESSION session, IdeRecvBuffT recvBuf, IdeI32Pt recvLen, uint32_t timeout)
{
    return Analysis::Dvvp::Adx::HdcRead(session, recvBuf, recvLen, timeout);
}
}  // namespace Adx
}  // namespace Dvvp
}  // namespace Analysis
