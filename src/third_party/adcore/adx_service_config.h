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
 * \file adx_service_config.h
 * \brief
*/

#ifndef ADX_SERVICE_CONFIG_H
#define ADX_SERVICE_CONFIG_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef enum {
    COMPONENT_GETD_FILE    = 6,   // get file from device
    COMPONENT_LOG_BACKHAUL = 7,   // log backhaul from device
    COMPONENT_LOG_LEVEL    = 8,   // operate device log level
    COMPONENT_DUMP         = 10,  // process data dump
    COMPONENT_TRACE        = 11,  // trace
    COMPONENT_MSNPUREPORT  = 12,  // msnpureport
    COMPONENT_HBM_DETECT   = 13,  // hbm detect
    COMPONENT_SYS_GET      = 14,  // get system log
    COMPONENT_SYS_REPORT   = 15,  // report system log
    COMPONENT_FILE_REPORT  = 16,  // file report
    COMPONENT_CPU_DETECT   = 17,  // cpu detect
    COMPONENT_DETECT_LIB_LOAD = 18,  // lib load
    NR_COMPONENTS,
} ComponentType;

typedef uintptr_t OptHandle;

typedef enum {
    COMM_HDC,
    COMM_SSL,
    COMM_LOCAL,
    NR_COMM
} OptType;

typedef struct {
    OptType type;
    OptHandle session;
    ComponentType comp;
    int32_t timeout; // 0 : wait_always; > 0 wait_timeout; < 0 wait_default
    void *client;
} CommHandle;

typedef CommHandle*        AdxCommHandle;
typedef const CommHandle*  AdxCommConHandle;

typedef struct {
    int32_t serverType;
    int32_t mode;      // 0 default, 1 virtual
    int32_t deviceId;  // set -1 is all
} ServerInitInfo;

typedef int32_t (*AdxComponentInit)(void);
typedef int32_t (*AdxComponentProcess)(const CommHandle*, const void*, uint32_t len);
typedef int32_t (*AdxComponentUnInit)(void);
#ifdef __cplusplus
}
#endif
#endif // ADX_SERVICE_CONFIG_H
