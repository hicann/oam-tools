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
#ifndef C_BASE_MSPROF_ERROR_MANAGER_H
#define C_BASE_MSPROF_ERROR_MANAGER_H
#include <vector>
#include <string>
#include "base/err_mgr.h"
#include "common/singleton/singleton.h"

namespace Analysis {
namespace Dvvp {
namespace MsprofErrMgr {

class MsprofErrorManager : public analysis::dvvp::common::singleton::Singleton<MsprofErrorManager> {
public:
    error_message::ErrorManagerContext& GetErrorManagerContext() const;
    void SetErrorContext(const error_message::ErrorManagerContext errorContext) const;
    MsprofErrorManager() {}
    ~MsprofErrorManager() override {}
    void ReportErrorMessage(
        const std::string errorCode, const std::vector<std::string>& keys = {},
        const std::vector<std::string>& values = {}) const;

private:
    static error_message::ErrorManagerContext errorContext_;
};

#define MSPROF_INPUT_ERROR(errorCode, key, value) \
    Analysis::Dvvp::MsprofErrMgr::MsprofErrorManager::instance()->ReportErrorMessage(errorCode, key, value)

#define MSPROF_ENV_ERROR MSPROF_INPUT_ERROR
#define MSPROF_INNER_ERROR REPORT_INNER_ERR_MSG
#define MSPROF_CALL_ERROR MSPROF_INNER_ERROR
} // namespace MsprofErrMgr
} // namespace Dvvp
} // namespace Analysis
#endif
