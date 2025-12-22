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
#include <map>
#include <cstring>
#include "ascend_hal.h"
#include "mmpa_api.h"

extern "C" {
drvError_t halGetAPIVersion(int32_t *ver)
{
    *ver=0x071905;
    return DRV_ERROR_NONE;
}

drvError_t drvGetDeviceSplitMode(unsigned int dev_id, unsigned int *mode)
{
    *mode = 0;
    return DRV_ERROR_NONE;
}

std::map<std::string, void*> g_map = {
    {"halGetAPIVersion", (void *)halGetAPIVersion},
    {"drvGetDeviceSplitMode", (void *)drvGetDeviceSplitMode},
    {"halEschedQueryInfo", (void *)halEschedQueryInfo},
    {"halEschedCreateGrpEx", (void *)halEschedCreateGrpEx},
};

void *mmDlsym(void *handle, const char* funcName)
{
    auto it = g_map.find(funcName);
    if (it != g_map.end()) {
        return it->second;
    }
    return nullptr;
}

char *mmDlerror(void)
{
    return nullptr;
}
int32_t g_handle;
void * mmDlopen(const char *fileName, int mode)
{
    if (strcmp(fileName, "libascend_hal.so") == 0) {
        return &g_handle;
    }
    return nullptr;
}

int mmDlclose(void *handle)
{
    return 0;
}
}