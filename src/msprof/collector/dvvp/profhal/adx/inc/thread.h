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

#ifndef IDE_DAEMON_COMMON_THREAD_H
#define IDE_DAEMON_COMMON_THREAD_H
#include <string>
#include <cstdint>
#include "osal.h"
#include "extra_config.h"
#include "common/util/error_manager/error_manager.h"

#define IDE_DAEMON_DEFAULT_THREAD_ATTR        {0, 0, 0, 0, 0, 1, 128 * 1024}
#define IDE_DAEMON_DEFAULT_DETACH_THREAD_ATTR {1, 0, 0, 0, 0, 1, 128 * 1024}

namespace Adx {
static const int32_t WAIT_TID_TIME   = 500;

class Thread {
public:
    static int32_t CreateTask(OsalThread &tid, OsalUserBlock &funcBlock);
    static int32_t CreateTaskWithDefaultAttr(OsalThread &tid, OsalUserBlock &funcBlock);
    static int32_t CreateDetachTaskWithDefaultAttr(OsalThread &tid, OsalUserBlock &funcBlock);
    static int32_t CreateDetachTask(OsalThread &tid, OsalUserBlock &funcBlock);
};

class Runnable {
public:
    Runnable();
    virtual ~Runnable();
    virtual int32_t Terminate();
    virtual int32_t Stop();
    int32_t Join();
    bool IsQuit();
    virtual int32_t Start();
    const std::string &GetThreadName();
    void SetThreadName(const std::string &threadName);

protected:
    virtual void Run(const struct error_message::Context &errorContext) = 0;

private:
    static IdeThreadArg Process(IdeThreadArg arg);

private:
    mutable bool quit_;
    OsalThread tid_;
    mutable bool isStarted_;
    std::string threadName_;
};
}
#endif
