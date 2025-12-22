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

#ifndef IDE_HDC_API_H
#define IDE_HDC_API_H
#include <list>
#include "ascend_hal.h"
#include "ide_tlv.h"
#include "extra_config.h"
#include "adx_log.h"

namespace Analysis {
namespace Dvvp {
namespace Adx {
using IdeTlvReq = TlvReqT*;
using IdeTlvConReq = const TlvReqT*;
using IdeTlvReqAddr = IdeTlvReq*;

using DRV_HDC_MSG_T_PTR = struct drvHdcMsg *;
using IDE_HDC_PACKET_T_PTR = struct IdeHdcPacket *;
using HDC_CLIENT_PTR = HDC_CLIENT *;
using HDC_SESSION_PTR = HDC_SESSION *;

enum class IdeLastPacket:int8_t {
    IDE_NOT_LAST_PACK = 0,
    IDE_LAST_PACK = 1
};
enum IdeDaemonPackageType {
    IDE_DAEMON_LITTLE_PACKAGE = 0xB0,
    IDE_DAEMON_BIG_PACKAGE
};

int32_t HdcClientInit(HDC_CLIENT_PTR client);

struct IdeHdcPacket {
    uint32_t len;
    enum IdeDaemonPackageType type;     // package type : big package,little package
    int8_t isLast;                 // only 0:is not last package; 1:last package
    char value[0];
};
struct IoVec {
    IdeBuffT base;
    uint32_t len;
};

HDC_CLIENT HdcClientCreate(enum drvHdcServiceType type);
int32_t HdcClientDestroy(HDC_CLIENT client);
HDC_SERVER HdcServerCreate(int32_t logDevId, enum drvHdcServiceType type);
void HdcServerDestroy(HDC_SERVER server);
HDC_SESSION HdcServerAccept(HDC_SERVER server);

int32_t HdcRead(HDC_SESSION session, IdeRecvBuffT recvBuf, IdeI32Pt recvLen, uint32_t timeout = 0);
int32_t HdcReadNb(HDC_SESSION session, IdeRecvBuffT recvBuf, IdeI32Pt recvLen);
int32_t HdcWrite(HDC_SESSION session, IdeSendBuffT buf, int32_t len);
int32_t HdcWriteNb(HDC_SESSION session, IdeSendBuffT buf, int32_t len);
int32_t HdcSessionConnect(int32_t peerNode, int32_t peerDevId,
    HDC_CLIENT client, HDC_SESSION_PTR session);
int32_t HalHdcSessionConnect(int32_t peerNode, int32_t peerDevId,
    int32_t hostPid, HDC_CLIENT client, HDC_SESSION_PTR session);
int32_t HdcSessionDestroy(HDC_SESSION session);
int32_t HdcSessionClose(HDC_SESSION session);
int32_t HdcGetDeviceBasePath(int32_t peerNode, int32_t peerDevid, IdeStringBuffer path, uint32_t pathLength);
int32_t HdcCapacity(IdeU32Pt segment);

/* ide-cmd与host-daemon通信使用的接口 */
int32_t IdeSockWriteData(IdeSession sockDesc, IdeSendBuffT buf, int32_t len);
int32_t IdeSockReadData(IdeSession sockDesc, IdeRecvBuffT readBuf, IdeI32Pt recvLen);
IdeSession IdeSockDupCreate(IdeSession sock);
void IdeSockDupDestroy(IdeSession sock);
void IdeSockDestroy(IdeSession sock);
HDC_CLIENT GetIdeDaemonHdcClient();
int32_t IdeCreatePacket(CmdClassT type, IdeString value, uint32_t valueLen,
    IdeRecvBuffT buf, IdeI32Pt bufLen);
void IdeFreePacket(IdeBuffT buf);
int32_t IdeGetDevIdBySession(HDC_SESSION session, IdeI32Pt devId);
int32_t IdeGetVfIdBySession(HDC_SESSION session, int32_t &vfId);
void IdeDeviceStartupRegister(int32_t (*devStartupNotifier)(uint32_t num, IdeU32Pt dev));
int32_t HdcSessionWrite(HDC_SESSION session, IdeSendBuffT buf, int32_t len, int32_t flag);
int32_t HdcStorePackage(const IdeHdcPacket &packet, struct IoVec &ioVec);
int32_t HdcReadIovecToMem(std::list<struct IoVec> &hdcIoList, uint32_t bufLen, IdeRecvBuffT recvBuf, IdeI32Pt recvLen);
}   // namespace Adx
}   // namespace Dvvp
}   // namespace Analysis

#endif
