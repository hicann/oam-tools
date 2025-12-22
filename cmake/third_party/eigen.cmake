# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

if (IS_DIRECTORY "${CANN_3RD_LIB_PATH}/eigen")
  set(REQ_URL "${CANN_3RD_LIB_PATH}/eigen")
else()
  set(REQ_URL "https://gitcode.com/cann-src-third-party/eigen/releases/download/3.4.0/eigen-3.4.0.tar.gz")
endif()

include(ExternalProject)
ExternalProject_Add(external_eigen_nn
  TLS_VERIFY        OFF
  URL               ${REQ_URL}
  DOWNLOAD_DIR      download/eigen
  PREFIX            third_party
  CONFIGURE_COMMAND ""
  BUILD_COMMAND     ""
  INSTALL_COMMAND   ""
)

ExternalProject_Get_Property(external_eigen_nn SOURCE_DIR)

add_library(EigenNn INTERFACE)
target_compile_options(EigenNn INTERFACE -w)

set_target_properties(EigenNn PROPERTIES
  INTERFACE_INCLUDE_DIRECTORIES "${SOURCE_DIR}"
)
add_dependencies(EigenNn external_eigen_nn)

add_library(Eigen3::EigenNn ALIAS EigenNn)