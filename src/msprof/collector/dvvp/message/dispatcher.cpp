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
 
#include "dispatcher.h"
#include "config/config.h"
#include "message/prof_params.h"
#include "msprof_dlog.h"

namespace analysis {
namespace dvvp {
namespace message {
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;
MsgDispatcher::MsgDispatcher()
{
}

MsgDispatcher::~MsgDispatcher()
{
}

void MsgDispatcher::OnNewMessage(SHARED_PTR_ALIA<google::protobuf::Message> message)
{
    if (message == nullptr) {
        MSPROF_LOGE("message is null");
        return;
    }

    auto iter = handlerMap_.find(message->GetDescriptor());
    if (iter != handlerMap_.end()) {
        iter->second->OnNewMessage(message);
    } else {
        MSPROF_LOGE("Failed to find handler for message:%s", message->GetTypeName().c_str());
    }
}
}  // namespace message
}  // namespace dvvp
}  // namespace analysis