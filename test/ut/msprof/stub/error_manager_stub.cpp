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
#include "error_manager.h"

ErrorManager &ErrorManager::GetInstance() {
  static ErrorManager instance;
  return instance;
}

error_message::Context &ErrorManager::GetErrorManagerContext() {
    error_message::Context error_context = {0UL, "", "", ""};
    return error_context;
}
    
void ErrorManager::SetErrorContext(const error_message::Context error_context)
{
    (void)(error_context);
}
