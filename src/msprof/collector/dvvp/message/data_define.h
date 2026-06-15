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

#ifndef ANALYSIS_DVVP_MESSAGE_DATA_DEFINE_H
#define ANALYSIS_DVVP_MESSAGE_DATA_DEFINE_H

#include "message.h"

namespace analysis {
namespace dvvp {
namespace message {

struct CollectionTimeInfo : BaseInfo {
    std::string collectionDateBegin;
    std::string collectionDateEnd;
    std::string collectionTimeBegin;
    std::string collectionTimeEnd;
    std::string clockMonotonicRaw;

    void ToObject(NanoJson::Json &object) override
    {
        SET_VALUE(object, collectionDateBegin);
        SET_VALUE(object, collectionDateEnd);
        SET_VALUE(object, collectionTimeBegin);
        SET_VALUE(object, collectionTimeEnd);
        SET_VALUE(object, clockMonotonicRaw);
    }

    void FromObject(NanoJson::Json &object) override { (void)object; }
};

} // namespace message
} // namespace dvvp
} // namespace analysis

#endif // ANALYSIS_DVVP_MESSAGE_DATA_DEFINE_H