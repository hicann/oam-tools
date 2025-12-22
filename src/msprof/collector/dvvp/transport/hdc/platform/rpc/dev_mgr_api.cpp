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

#include "transport/hdc/dev_mgr_api.h"
#include "logger/msprof_dlog.h"
#include "transport/hdc/device_transport.h"
#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace transport {
void LoadDevMgrAPI(DevMgrAPI &devMgrAPI)
{
    MSPROF_LOGI("LoadDevMgrAPI init begin");
    devMgrAPI.pfDevMgrInit = &DevTransMgr::InitDevTransMgr;
    devMgrAPI.pfDevMgrUnInit = &DevTransMgr::UnInitDevTransMgr;
    devMgrAPI.pfDevMgrCloseDevTrans = &DevTransMgr::CloseDevTrans;
    devMgrAPI.pfDevMgrGetDevTrans = &DevTransMgr::GetDevTrans;
    MSPROF_LOGI("LoadDevMgrAPI init end");
}
}}}