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

#include "prof_plugin_manager.h"
#include "errno/error_code.h"
#include "prof_cann_plugin.h"
#include "prof_atls_plugin.h"
using namespace analysis::dvvp::common::error;
namespace ProfAPI {
PROF_PLUGIN_PTR ProfPluginManager::GetProfPlugin(void)
{
    if (profPlugin_ == nullptr) {
        profPlugin_ = ProfAPI::ProfCannPlugin::instance();
    }
    return profPlugin_;
}

void ProfPluginManager::SetProfPlugin(PROF_PLUGIN_PTR plugin)
{
    profPlugin_ = plugin;
}
}