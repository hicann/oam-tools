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

/*!
 * \file adcore_api.h
 * \brief
*/

#ifndef ADCORE_API_H
#define ADCORE_API_H
#include "ascend_hal.h"
#include "ide_tlv.h"
#include "extra_config.h"
#include "adx_service_config.h"
#define ADX_API __attribute__((visibility("default")))
#ifdef __cplusplus
extern "C" {
#endif
typedef enum drvHdcServiceType AdxHdcServiceType;
typedef enum {
    SEND_FILE_TYPE_REAL_FILE,
    SEND_FILE_TYPE_TMP_FILE
} SendFileType;

typedef struct {
    ComponentType type; // 数据包组件类型
    int32_t devId;      // 设备 ID
    int32_t len;        // 数据包数据长度
    char value[0];      // 数据包数据
} TlvReq;
typedef TlvReq*            AdxTlvReq;
typedef const TlvReq*      AdxTlvConReq;

ADX_API AdxCommHandle AdxCreateCommHandle(AdxHdcServiceType type, int32_t devId, ComponentType compType);
ADX_API int32_t AdxIsCommHandleValid(AdxCommConHandle handle);
ADX_API void AdxDestroyCommHandle(AdxCommHandle handle);
ADX_API int32_t AdxSendMsg(AdxCommConHandle handle, AdxString data, uint32_t len);
ADX_API int32_t AdxRecvMsg(AdxCommHandle handle, IdeStrBufAddrT data, uint32_t *len, uint32_t timeout);
ADX_API int32_t AdxGetAttrByCommHandle(AdxCommConHandle handle, int32_t attr, int32_t *value);
ADX_API int32_t AdxRecvDevFileTimeout(AdxCommHandle handle, AdxString desPath, uint32_t timeout,
    AdxStringBuffer fileName, uint32_t fileNameLen);

ADX_API int32_t AdxSendMsgAndGetResultByType(AdxHdcServiceType type, IdeTlvConReq req, const AdxStringBuffer result,
    uint32_t resultLen);
ADX_API int32_t AdxSendMsgAndNoResultByType(AdxHdcServiceType type, IdeTlvConReq req);
ADX_API int32_t AdxSendMsgByHandle(AdxCommConHandle handle, CmdClassT type, AdxString data, uint32_t len);
ADX_API int32_t AdxSendFileByHandle(AdxCommConHandle handle, CmdClassT type, AdxString srcPath, AdxString desPath,
    SendFileType flag);
ADX_API int32_t AdxDevCommShortLink(AdxHdcServiceType type, AdxTlvConReq req, AdxStringBuffer result, uint32_t length,
    uint32_t timeout);

#ifdef __cplusplus
}
#endif
#endif // ADCORE_API_H