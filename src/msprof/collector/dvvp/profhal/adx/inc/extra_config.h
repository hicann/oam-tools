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

#ifdef __cplusplus
extern "C" {
#endif

typedef void*                IdeSession;
typedef void*                IdeThreadArg;
typedef void*                IdeMemHandle;
typedef void*                IdeBuffT;
typedef void**               IdeRecvBuffT;
typedef const void*          IdeSendBuffT;
typedef int*                 IdeI32Pt;
typedef unsigned int*        IdeU32Pt;
typedef char**               IdeStrBufAddrT;

using IdeStringBuffer = char *;
using IdeString = const char *;
using IdeU8Pt = unsigned char *;

const int IDE_DAEMON_ERROR = -1;
const int IDE_DAEMON_OK = 0;
const int IDE_DAEMON_SOCK_CLOSE = 1;
const int IDE_DAEMON_RECV_NODATA = 2;   // 2 : no data
const int MAX_SESSION_NUM = 96; // 96 : max session num
const int DEVICE_NUM_MAX = 1124;

#ifdef __cplusplus
}
#endif

#endif

