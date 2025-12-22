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
 
#ifndef ANALYSIS_DVVP_STREAMIO_EPOLL_OPERATION_H
#define ANALYSIS_DVVP_STREAMIO_EPOLL_OPERATION_H

#include <stdint.h>
#if (defined(_WIN32) || defined(_WIN64) || defined(_MSC_VER))
#include <winsock2.h>
#else
#include <sys/select.h>
#include <sys/time.h>
#endif
#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace streamio {
namespace common {
class SelectOperation {
public:
    SelectOperation();
    ~SelectOperation();
    void SelectAdd(OsalSockHandle fd);
    void SelectDel(OsalSockHandle fd);
    bool SelectIsSet(OsalSockHandle fd);
    void SelectClear();

private:
    OsalSockHandle maxFd_;
    fd_set readfd_;

    SelectOperation &operator=(const SelectOperation &op);
    SelectOperation(const SelectOperation &op);
};
}  // namespace common
}  // namespace streamio
}  // namespace dvvp
}  // namespace analysis

#endif
