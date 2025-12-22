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

#include "devprof_common.h"
#include "securec.h"
#include "ascend_hal.h"
#include "msprof_dlog.h"
#include "error_code.h"
#include "osal.h"

namespace Devprof {
using namespace analysis::dvvp::common::error;

int32_t ProfSendEvent(uint32_t devId, int32_t hostPid, const char *grpName)
{
    struct esched_query_gid_output gidOut = {0};
    struct esched_query_gid_input gidIn = {hostPid, {0}};
    struct esched_output_info outPut = {&gidOut, sizeof(struct esched_query_gid_output)};
    struct esched_input_info inPut = {&gidIn, sizeof(struct esched_query_gid_input)};
    if (strcpy_s(gidIn.grp_name, EVENT_MAX_GRP_NAME_LEN, grpName) != EOK) {
        MSPROF_LOGE("strcpy failed for driver event grp_name[%s].", grpName);
        return PROFILING_FAILED;
    }

#ifdef EP_MODE
    ESCHED_QUERY_TYPE type = QUERY_TYPE_REMOTE_GRP_ID;
#else
    ESCHED_QUERY_TYPE type = QUERY_TYPE_LOCAL_GRP_ID;
#endif

    const uint32_t WAIT_TIME = 10;
    const int32_t WAIT_COUNT = 10;
    drvError_t ret;
    MSPROF_LOGI("devId:%u, type:%d, hostPid:%d", devId, type, hostPid);
    for (int32_t i = 0; i < WAIT_COUNT; i++) {
        ret = halEschedQueryInfo(devId, type, &inPut, &outPut);
        if (ret == DRV_ERROR_NONE) {
            break;
        }
        OsalSleep(WAIT_TIME);
    }
    if (ret != DRV_ERROR_NONE) {
        MSPROF_LOGE("query grp id by name '%s' failed, ret:%d", gidIn.grp_name, ret);
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("query grp id:%u by name '%s'", gidOut.grp_id, gidIn.grp_name);

    char msg[] = "1";
    struct event_summary event = {hostPid, gidOut.grp_id, EVENT_USR_START, 0, 1, msg, CCPU_HOST, ONLY, 0, {0}};
    ret = halEschedSubmitEvent(devId, &event);
    if (ret != DRV_ERROR_NONE) {
        MSPROF_LOGE("send Event failed, err:%d", ret);
        return PROFILING_FAILED;
    }

    return PROFILING_SUCCESS;
}

}

