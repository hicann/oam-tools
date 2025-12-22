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

#ifndef IDE_DAEMON_COMMON_EXTRA_CONFIG_H
#define IDE_DAEMON_COMMON_EXTRA_CONFIG_H
#define ARRAY_LEN(x, type) (sizeof(x) / sizeof(type))

#ifdef __cplusplus
extern "C" {
#endif

typedef void*                IdeSession;
typedef void*                IdeThreadArg;
typedef void*                IdeMemHandle;
typedef void*                IdeKmcHandle;
typedef void*                IdeKmcLock;
typedef void**               IdeKmcLockAddr;
typedef void*                IdeBuffT;
typedef void**               IdeRecvBuffT;
typedef const void*          IdeKmcConHandle;
typedef const void*          IdeSendBuffT;
typedef char*                IdeStringBuffer;
typedef const char*          IdeString;
typedef char**               IdeStrBufAddrT;
typedef unsigned char*       IdeU8Pt;
typedef int*                 IdeI32Pt;
typedef unsigned int*        IdeU32Pt;
typedef const unsigned char* IdeConU8Pt;
typedef const int*           IdeConI32Pt;
typedef const unsigned int*  IdeConU32Pt;
typedef int*                 IdePidPtr;

#define IDE_DAEMON_ERROR                 (-1)
#define IDE_DAEMON_OK                    (0)
#define IDE_DAEMON_SOCK_CLOSE            (1)
#define IDE_DAEMON_RECV_NODATA           (2)
#define IDE_DAEMON_DONE                  (3)
#define DEVICE_NUM_MAX                   (64)
#define MAX_SESSION_NUM                  (100)
#define MAX_TIME_LEN                     (100)
#define IDE_MAX_FILE_PATH                (512)
#define IDE_STATUS_LEN                   (256)
#define MAX_IP_LEN                       (16)
#define TCP_MAX_LISTEN_NUM               (100)
#define PACK_SIZE                        (102400)
#define SOCK_OK                          (0)
#define SOCK_ERROR                       (-1)
#define PASSWORD_MAX_LNE                 (32)

#define HDC_END_MSG                      ("###[HDC_MSG]hdc_end_msg_used_by_framework###")
#define ADX_SAFE_MALLOC(size)            ((size) > 0 ? calloc(1, size) : nullptr)
#define ADX_SAFE_CALLOC(n, size)         (((n) > 0 && (size) > 0) ? calloc(n, size) : nullptr)
#define ADX_SAFE_FREE(p)                 do { if ((p) != nullptr) { free(p); (p) = nullptr; } } while (0)
#ifdef __cplusplus
}
#endif

#endif

