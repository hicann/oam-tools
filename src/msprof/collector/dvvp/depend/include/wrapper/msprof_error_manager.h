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
#ifndef MSPROF_ERROR_MANAGER_H
#define MSPROF_ERROR_MANAGER_H

#include <string>
#include <vector>
#include "base/err_mgr.h"
#include "common/singleton/singleton.h"

// 谓词类宏：新接口要求 std::vector<const char *>，业务侧传的是 std::vector<std::string>。
// 先把入参具化为具名局部变量，再取 c_str()，把临时 vector 的生命周期绑定到 do/while 块。
#define MSPROF_INPUT_ERROR(errorCode, key, value)                            \
    do {                                                                     \
        const std::vector<std::string> msprofErrKeys__ = (key);              \
        const std::vector<std::string> msprofErrValues__ = (value);          \
        REPORT_PREDEFINED_ERR_MSG((errorCode),                               \
            Analysis::Dvvp::MsprofErrMgr::ToCStrVec(msprofErrKeys__),        \
            Analysis::Dvvp::MsprofErrMgr::ToCStrVec(msprofErrValues__));     \
    } while (false)

#define MSPROF_ENV_ERROR MSPROF_INPUT_ERROR
#define MSPROF_INNER_ERROR REPORT_INNER_ERR_MSG
#define MSPROF_CALL_ERROR REPORT_INNER_ERR_MSG
namespace Analysis {
namespace Dvvp {
namespace MsprofErrMgr {

inline std::vector<const char *> ToCStrVec(const std::vector<std::string> &in)
{
    std::vector<const char *> out;
    out.reserve(in.size());
    for (const auto &item : in) {
        out.emplace_back(item.c_str());
    }
    return out;
}

class MsprofErrorManager : public analysis::dvvp::common::singleton::Singleton<MsprofErrorManager> {
public:
    error_message::ErrorManagerContext &GetErrorManagerContext() const;
    void SetErrorContext(const error_message::ErrorManagerContext errorContext) const;
    MsprofErrorManager() {}
    ~MsprofErrorManager() override {}
private:
    static error_message::ErrorManagerContext errorContext_;
};

}  // ErrorManager
}  // Dvvp
}  // namespace Analysis
#endif
