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
#include "dlog_pub.h"
#include <unistd.h>
#include <stdio.h>
#include <stdarg.h>
#include <syslog.h>
#include <map>
#include <string>
#include "securec.h"

const std::map<int, std::string> LOG_LEVEL_INFO = {
    {DLOG_DEBUG, "DEBUG"},
    {DLOG_INFO,  "INFO"},
    {DLOG_WARN,  "WARING"},
    {DLOG_ERROR, "ERROR"}
};

void DlogErrorInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), format, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogErrorInner.");
        return;
    }
    printf("[ERROR]%s\n", buffer);
    va_end(args);
}

void DlogInfoInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), format, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogInfoInner.");
        return;
    }
    printf("[INFO]%s\n", buffer);
    va_end(args);
}

void DlogWarnInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), format, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogWarnInner.");
        return;
    }
    printf("[WARN]%s\n", buffer);
    va_end(args);
}

void DlogEventInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), format, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogEventInner.");
        return;
    }
    printf("[EVENT]%s\n", buffer);
    va_end(args);
}

void DlogDebugInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), format, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogDebugInner.");
        return;
    }
    printf("[DEBUG]%s\n", buffer);
    va_end(args);
}

void DlogRecord(int module_id, int level, const char *fmt, ...){
    auto iter = LOG_LEVEL_INFO.find(level);
    std::string levelStr;
    if (iter != LOG_LEVEL_INFO.end())
    {
        levelStr = iter->second;
    }

    va_list args;
    char buffer[4096] = {0};
    va_start(args, fmt);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), fmt, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogRecord.");
        return;
    }
    printf("[%s][pid:%d]%s", levelStr.c_str(), getpid(), buffer);
    va_end(args);
}

void DlogFlush(void)
{
}

void ide_log(int priority, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    int ret = vsnprintf_s(buffer, sizeof(buffer), sizeof(buffer), format, args);
    if (ret == -1) {
        printf("[ERROR]Failed to execute vsnprintf_s for ide_log.");
        return;
    }
    printf("[IDE]%s\n", buffer);
    va_end(args);
}

int CheckLogLevel(int moduleId, int level)
{
    return 1;
}
