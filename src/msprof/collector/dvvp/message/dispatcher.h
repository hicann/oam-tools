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
 
#ifndef ANALYSIS_DVVP_MESSAGE_DISPATCHER_H
#define ANALYSIS_DVVP_MESSAGE_DISPATCHER_H

#include <map>
#include <memory>
#include <string>
#include <google/protobuf/descriptor.h>
#include <google/protobuf/message.h>

#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace message {
class IMsgHandler {
public:
    virtual ~IMsgHandler() {}

public:
    virtual void OnNewMessage(SHARED_PTR_ALIA<google::protobuf::Message> message) = 0;
};

class MsgDispatcher {
public:
    MsgDispatcher();
    virtual ~MsgDispatcher();

public:
    void OnNewMessage(SHARED_PTR_ALIA<google::protobuf::Message> message);

    template<typename T>
    void RegisterMessageHandler(SHARED_PTR_ALIA<IMsgHandler> handler)
    {
        if (handler == nullptr) {
            return;
        }
        handlerMap_[T::descriptor()] = handler;
    }

private:
    std::map<const google::protobuf::Descriptor *, SHARED_PTR_ALIA<IMsgHandler> > handlerMap_;
};
}  // namespace message
}  // namespace dvvp
}  // namespace analysis

#endif