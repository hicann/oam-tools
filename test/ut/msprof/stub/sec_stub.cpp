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
#include <string.h>
#include <stdio.h>

int g_sprintf_s_flag = 0;

#ifdef __cplusplus
extern "C" {
#endif

int memset_s(void *dest, int dest_max, int c, int count)
{
    memset(dest, 0, count);
    return 0;
}

int memcpy_s(void *dest, int dest_max, const void *src, int count)
{
    memcpy(dest, src, count);
    return 0;
}

int sprintf_s(char* strDest, int destMax,const char* format, const char* src)
{
    int ret = 0;

    if (g_sprintf_s_flag == 0) {
        ret = sprintf(strDest, format, src);
        return 0;
    } else if (g_sprintf_s_flag == 2) {
        ret = sprintf(strDest, format, src);
        return ret;
    } else { // g_sprintf_s_flag = 1 compatible with old code
        return -1;
    }
}

int strcpy_s(char* strDest,int dest_max,const char* strSrc)
{
    strcpy(strDest,strSrc);
    return 0;
}

int strcat_s(char* dest, int dest_max, const char* src)
{
    strcat(dest,src);
    return 0;

}

int strtok_s(char* strToken, const char* strDelimit, char** context)
{
    strtok(strToken,strDelimit);
    return 0;
}

int vsnprintf_s(char *strDest, size_t destMax, size_t count, const char *format, va_list argList)
{
    return 0;
}

#ifdef __cplusplus
}
#endif
