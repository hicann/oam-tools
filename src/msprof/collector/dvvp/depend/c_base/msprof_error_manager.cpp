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

#include "msprof_error_manager.h"

namespace Analysis {
namespace Dvvp {
namespace MsprofErrMgr {
error_message::Context MsprofErrorManager::errorContext_ = {0UL, "", "", ""};

error_message::Context &MsprofErrorManager::GetErrorManagerContext() const
{
    return errorContext_;
}

void MsprofErrorManager::SetErrorContext(const error_message::Context /* errorContext */) const
{
}

void MsprofErrorManager::ReportErrorMessage(const std::string errorCode, const std::vector<std::string> &keys,
    const std::vector<std::string> &values) const
{
    char **argList = new(std::nothrow) char* [keys.size()]();
    if (argList == nullptr) {
        return;
    }
    for (size_t i = 0; i < keys.size(); i++) {
        argList[i] = const_cast<char*>(keys[i].c_str());
    }

    char **argVals = new(std::nothrow) char* [values.size()]();
    if (argVals == nullptr) {
        delete[] argList;
        return;
    }
    for (size_t i = 0; i < values.size(); i++) {
        argVals[i] = const_cast<char*>(values[i].c_str());
    }

    ReportErrMessage(errorCode.c_str(), argList, argVals, keys.size());
    delete[] argList;
    delete[] argVals;
}
}  // ErrorManager
}  // Dvvp
}  // namespace Analysis