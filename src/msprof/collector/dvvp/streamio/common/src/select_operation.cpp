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

#include "select_operation.h"
#include "osal.h"

namespace analysis {
namespace dvvp {
namespace streamio {
namespace common {
SelectOperation::SelectOperation()
    : maxFd_(0)
{
    FD_ZERO(&readfd_);
}

SelectOperation::~SelectOperation()
{
}

void SelectOperation::SelectAdd(OsalSockHandle fd)
{
    if (fd < 0) {
        return;
    }

    if (maxFd_ < fd) {
        maxFd_ = fd;
    }

    FD_SET(fd, &readfd_);
}

void SelectOperation::SelectDel(OsalSockHandle fd)
{
    if (fd < 0) {
        return;
    }

    FD_CLR(fd, &readfd_);
}

bool SelectOperation::SelectIsSet(OsalSockHandle fd)
{
    if (fd < 0) {
        return false;
    }

    if (FD_ISSET(fd, &readfd_)) {
        return true;
    }

    return false;
}

void SelectOperation::SelectClear()
{
    FD_ZERO(&readfd_);
}
}  // namespace common
}  // namespace streamio
}  // namespace dvvp
}  // namespace analysis
