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

#ifndef PROF_LOAD_API_H
#define PROF_LOAD_API_H
#include <string>
#include <dlfcn.h>

namespace ProfAPI {
using VOID_PTR = void *;
class ProfLoadApi {
public:
    void ProfLoadApiInit(const VOID_PTR &handle);
    VOID_PTR LoadApi(const std::string &apiName) const;
    template <typename T>
    T LoadProfTxApi(const std::string &apiName) const
    {
        return reinterpret_cast<T>(LoadApi(apiName));
    }
private:
    VOID_PTR handle_{nullptr};
};

inline void ProfLoadApi::ProfLoadApiInit(const VOID_PTR &handle)
{
    handle_ = handle;
}

inline VOID_PTR ProfLoadApi::LoadApi(const std::string &apiName) const
{
    if (handle_ != nullptr) {
        return dlsym(handle_, apiName.c_str());
    }

    return nullptr;
}
}
#endif