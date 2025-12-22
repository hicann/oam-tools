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
#ifndef ERROR_MANAGER_C_H
#define ERROR_MANAGER_C_H

#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#define LIMIT_PER_MESSAGE 1024
#define ARRAY(...) {__VA_ARGS__}

#define REPORT_INNER_ERROR(errcode, fmt, ...) \
    FormatReportInner(errcode, "[FUNC:%s][FILE:%s][LINE:%zu]" #fmt, \
                      &__FUNCTION__[0], __FILE__, (size_t)(__LINE__), ##__VA_ARGS__)

#define REPORT_INPUT_ERROR(errcode, params, vals)                                         \
    do {                                                                                  \
        char *argList[] = params;                                                         \
        char *argVal[] = vals;                                                            \
        ReportErrMessage(errcode, argList, argVal, sizeof(argList) / sizeof(argList[0])); \
    } while (false)

// 请调用者必须保证数组args和arg_values个数一致,且数组个数argsNum正确
void ReportErrMessage(const char *errorCode, char *args[], char *argValues[], int32_t argsNum);
void ReportInterErrMessage(const char *errorCode, const char *errorMsg);
char *GetErrorMessage(void);
void FormatReportInner(const char *errorCode, const char *fmt, ...);
#ifdef __cplusplus
}
#endif
#endif