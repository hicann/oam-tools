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

#include "common/util/error_manager/error_manager.h"
#include "common/singleton/singleton.h"

#define MSPROF_INPUT_ERROR REPORT_INPUT_ERROR
#define MSPROF_ENV_ERROR REPORT_ENV_ERROR
#define MSPROF_INNER_ERROR REPORT_INNER_ERROR
#define MSPROF_CALL_ERROR REPORT_CALL_ERROR
namespace Analysis {
namespace Dvvp {
namespace MsprofErrMgr {

class MsprofErrorManager : public analysis::dvvp::common::singleton::Singleton<MsprofErrorManager> {
public:
    error_message::Context &GetErrorManagerContext() const;
    void SetErrorContext(const error_message::Context errorContext) const;
    MsprofErrorManager() {}
    ~MsprofErrorManager() override {}
private:
    static error_message::Context errorContext_;
};

}  // ErrorManager
}  // Dvvp
}  // namespace Analysis
#endif