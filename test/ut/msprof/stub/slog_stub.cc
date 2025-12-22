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
#include "slog.h"
#include <map>
#include <cstdio>
#include <string>
#include <unistd.h>

const std::map<int, std::string> LOG_LEVEL_INFO = {
    {DLOG_DEBUG, "DEBUG"},
    {DLOG_INFO,  "INFO"},
    {DLOG_WARN,  "WARING"},
    {DLOG_ERROR, "ERROR"},
    {DLOG_EVENT, "EVENT"},
};

int g_log_level = DLOG_INFO;

void DlogErrorInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    printf("[ERROR][pid:%d]%s", getpid(), buffer);
    va_end(args);
}

void DlogInfoInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    printf("[INFO][pid:%d]%s", getpid(), buffer);
    va_end(args);
}

void DlogWarnInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    printf("[WARN][pid:%d]%s", getpid(), buffer);
    va_end(args);
}

void DlogDebugInner(int moduleId, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    printf("[DEBUG][pid:%d]%s", getpid(), buffer);
    va_end(args);
}

void DlogRecord(int module_id, int level, const char *fmt, ...){
    if (level < g_log_level) {
        return;
    }
    auto iter = LOG_LEVEL_INFO.find(level);
    std::string levelStr;
    if (iter != LOG_LEVEL_INFO.end())
    {
        levelStr = iter->second;
    }

    va_list args;
    char buffer[4096] = {0};
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    printf("[%s][pid:%d]%s", levelStr.c_str(), getpid(), buffer);
    va_end(args);
}

void ide_log(int priority, const char *format, ...) {
    va_list args;

    char buffer[4096] = {0};

    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    printf("%s", buffer);
    va_end(args);
}

void RecordLog(int level, char *buffer)
{
    return;
}

void DlogInnerForC(int moduleId, int level, const char *fmt, ...)
{
    va_list args;

    char buffer[4096] = {0};

    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    auto iter = LOG_LEVEL_INFO.find(level);
    std::string levelStr;

    if(iter != LOG_LEVEL_INFO.end())
    {
        levelStr = iter->second;
    }
    RecordLog(level, buffer);
    printf("[%s][pid:%d]%s", levelStr.c_str(), getpid(), buffer);
    va_end(args);

}

void DlogRecordForC(int moduleId, int level, const char *fmt, ...)
{
    va_list args;

    char buffer[4096] = {0};

    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    auto iter = LOG_LEVEL_INFO.find(level);
    std::string levelStr;

    if(iter != LOG_LEVEL_INFO.end())
    {
        levelStr = iter->second;
    }
    RecordLog(level, buffer);
    printf("[%s][pid:%d]%s", levelStr.c_str(), getpid(), buffer);
    va_end(args);
}

void DlogFlush(void)
{
}

int CheckLogLevelForC(int moduleId, int level)
{
    if (moduleId & RUN_LOG_MASK) {
        return 1;
    }
    if (level >= g_log_level) {
        return 1;
    }
    return 0;
}

int CheckLogLevel(int moduleId, int level)
{
    if (moduleId & RUN_LOG_MASK) {
        return 1;
    }
    if (level >= g_log_level) {
        return 1;
    }
    return 0;
}
