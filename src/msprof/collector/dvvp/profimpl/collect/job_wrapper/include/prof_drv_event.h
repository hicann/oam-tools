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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_EVENT_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_EVENT_H
#include "collection_register.h"
#include "ai_drv_prof_api.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {

struct TaskEventAttr {
    uint32_t deviceId;
    analysis::dvvp::driver::AI_DRV_CHANNEL channelId;
    enum ProfCollectionJobE jobTag;
    bool isChannelValid;
    bool isProcessRun;
    bool isExit;
    bool isThreadStart;
    OsalThread handle;
    bool isAttachDevice;
    bool isWaitDevPid;
    const char *grpName;
};

class ProfDrvEvent {
public:
    ProfDrvEvent();
    ~ProfDrvEvent();
    int32_t SubscribeEventThreadInit(struct TaskEventAttr *eventAttr) const;
    void SubscribeEventThreadUninit(uint32_t devId) const;
private:
    static void *EventThreadHandle(void *attr);
    static int32_t QueryDevPid(const struct TaskEventAttr *eventAttr);
    static int32_t QueryGroupId(uint32_t devId, uint32_t &grpId, const char *grpName);
    static void WaitEvent(struct TaskEventAttr *eventAttr, uint32_t grpId);
};

}
}
}
#endif