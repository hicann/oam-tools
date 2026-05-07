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

# 算子类别清单
set(OP_CATEGORY_LIST "src/aml/ops")

set(COMMON_NAME common_${PKG_NAME})
set(OPHOST_NAME ophost_${PKG_NAME})
set(OPSTATIC_NAME cann_${PKG_NAME}_static)
set(OPAPI_NAME opapi_${PKG_NAME})
set(OPGRAPH_NAME opgraph_${PKG_NAME})
set(GRAPH_PLUGIN_NAME graph_plugin_${PKG_NAME})

if(NOT CANN_3RD_LIB_PATH)
  set(CANN_3RD_LIB_PATH ${PROJECT_SOURCE_DIR}/build/third_party)
endif()
if(NOT CANN_3RD_PKG_PATH)
  set(CANN_3RD_PKG_PATH ${PROJECT_SOURCE_DIR}/build/third_party/pkg)
endif()

message(STATUS "System processor: ${CMAKE_SYSTEM_PROCESSOR}")
if (${CMAKE_SYSTEM_PROCESSOR} MATCHES "x86_64")
  set(ARCH x86_64)
elseif (${CMAKE_SYSTEM_PROCESSOR} MATCHES "aarch64|arm64|arm")
  set(ARCH aarch64)
else()
  message(WARNING "Unknown architecture: ${CMAKE_SYSTEM_PROCESSOR}")
endif()

# interface, 用于收集aclnn/aclnn_inner/aclnn_exclude的def文件
add_library(${OPHOST_NAME}_opdef_aclnn_obj INTERFACE)
add_library(${OPHOST_NAME}_opdef_aclnn_inner_obj INTERFACE)
add_library(${OPHOST_NAME}_opdef_aclnn_exclude_obj INTERFACE)
add_library(${OPHOST_NAME}_aclnn_exclude_headers INTERFACE)
# interface, 用于收集ops proto头文件
add_library(${GRAPH_PLUGIN_NAME}_proto_headers INTERFACE)

# global variables
set(COMPILED_OPS CACHE STRING "Compiled Ops" FORCE)
set(COMPILED_OP_DIRS CACHE STRING "Compiled Ops Dirs" FORCE)

# src path
get_filename_component(OAM_TOOLS_CMAKE_DIR           "${OAM_TOOLS_DIR}/cmake"                               REALPATH)
get_filename_component(OAM_TOOLS_COMMON_INC          "${OAM_TOOLS_DIR}/src/aml/ops/common/inc"              REALPATH)
get_filename_component(OAM_TOOLS_COMMON_INC_COMMON   "${OAM_TOOLS_COMMON_INC}/common"                       REALPATH)
get_filename_component(OAM_TOOLS_COMMON_INC_EXTERNAL "${OAM_TOOLS_COMMON_INC}/external"                     REALPATH)
get_filename_component(OAM_TOOLS_COMMON_INC_HEADERS  "${OAM_TOOLS_COMMON_INC_EXTERNAL}/aclnn_kernels"       REALPATH)
get_filename_component(OPS_KERNEL_BINARY_SCRIPT     "${OAM_TOOLS_DIR}/scripts/kernel/binary_script"       REALPATH)
get_filename_component(OPS_KERNEL_BINARY_CONFIG     "${OAM_TOOLS_DIR}/scripts/kernel/binary_config"       REALPATH)

# python
if(NOT DEFINED ASCEND_PYTHON_EXECUTABLE)
  set(ASCEND_PYTHON_EXECUTABLE python3 CACHE STRING "")
endif()

# built-in package install path
set(ACLNN_INC_INSTALL_DIR           oam_tools/include/aclnnop)
set(ACLNN_OP_INC_INSTALL_DIR        oam_tools/include/aclnnop/level2)
set(ACLNN_LIB_INSTALL_DIR           oam_tools/built-in/op_impl/ai_core/tbe/op_api/lib/linux/${CMAKE_SYSTEM_PROCESSOR})
set(OPS_INFO_INSTALL_DIR            oam_tools/built-in/op_impl/ai_core/tbe/config)
set(IMPL_INSTALL_DIR                oam_tools/built-in/op_impl/ai_core/tbe/impl/ops_oam/ascendc)
set(IMPL_DYNAMIC_INSTALL_DIR        oam_tools/built-in/op_impl/ai_core/tbe/impl/ops_oam/dynamic)
set(BIN_KERNEL_INSTALL_DIR          oam_tools/built-in/op_impl/ai_core/tbe/kernel)
set(BIN_KERNEL_CONFIG_INSTALL_DIR   oam_tools/built-in/op_impl/ai_core/tbe/kernel/config)
set(OPHOST_LIB_INSTALL_PATH         oam_tools/built-in/op_impl/ai_core/tbe/op_host/lib/linux/${CMAKE_SYSTEM_PROCESSOR})
set(AICPU_KERNEL_IMPL               oam_tools/built-in/op_impl/aicpu/kernel)
set(AICPU_JSON_CONFIG               oam_tools/built-in/op_impl/aicpu/config)
set(OPTILING_LIB_INSTALL_DIR        ${OPHOST_LIB_INSTALL_PATH})
set(OPGRAPH_INC_INSTALL_DIR         oam_tools/built-in/op_graph/inc)
set(OPGRAPH_LIB_INSTALL_DIR         oam_tools/built-in/op_graph/lib/linux/${CMAKE_SYSTEM_PROCESSOR})
set(VERSION_INFO_INSTALL_DIR        ops_oam)

# util path
set(ASCEND_TENSOR_COMPILER_PATH ${ASCEND_DIR}/compiler)
set(ASCEND_CCEC_COMPILER_PATH ${ASCEND_TENSOR_COMPILER_PATH}/ccec_compiler/bin)
set(OP_BUILD_TOOL ${ASCEND_DIR}/tools/opbuild/op_build)

# tmp path
set(ASCEND_TMP_PATH ${CMAKE_BINARY_DIR}/tmp)
set(ASCEND_SUB_CONFIG_PATH ${ASCEND_TMP_PATH}/ops_config.txt)
file(MAKE_DIRECTORY ${ASCEND_TMP_PATH})
file(REMOVE ${ASCEND_SUB_CONFIG_PATH})
set(UT_PATH ${PROJECT_SOURCE_DIR}/tests/ut)

# output path
set(ASCEND_AUTOGEN_PATH     ${CMAKE_BINARY_DIR}/autogen)
set(ASCEND_KERNEL_SRC_DST   ${CMAKE_BINARY_DIR}/tbe/ascendc)
set(ASCEND_KERNEL_CONF_DST  ${CMAKE_BINARY_DIR}/tbe/config)
set(ASCEND_GRAPH_CONF_DST   ${CMAKE_BINARY_DIR}/tbe/graph)
file(MAKE_DIRECTORY ${ASCEND_AUTOGEN_PATH})
file(MAKE_DIRECTORY ${ASCEND_KERNEL_SRC_DST})
file(MAKE_DIRECTORY ${ASCEND_KERNEL_CONF_DST})
file(MAKE_DIRECTORY ${ASCEND_GRAPH_CONF_DST})
set(CUSTOM_COMPILE_OPTIONS "custom_compile_options.ini")
set(CUSTOM_OPC_OPTIONS "custom_opc_options.ini")
execute_process(
  COMMAND rm -rf ${ASCEND_AUTOGEN_PATH}/${CUSTOM_COMPILE_OPTIONS}
  COMMAND rm -rf ${ASCEND_AUTOGEN_PATH}/${CUSTOM_OPC_OPTIONS}
  COMMAND touch ${ASCEND_AUTOGEN_PATH}/${CUSTOM_COMPILE_OPTIONS}
  COMMAND touch ${ASCEND_AUTOGEN_PATH}/${CUSTOM_OPC_OPTIONS}
)

set(OPAPI_INCLUDE
  ${C_SEC_INCLUDE}
  ${PLATFORM_INC_DIRS}
  ${OPBASE_INC_DIRS}
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/pkg_inc/profiling # include profiling/prof_common.h
  ${METADEF_INCLUDE_DIRS}
  ${NNOPBASE_INCLUDE_DIRS}
  ${NPURUNTIME_INCLUDE_DIRS}
  ${JSON_INCLUDE}
  ${OAM_TOOLS_DIR}
  ${AICPU_INC_DIRS}
  ${TOP_DIR}/output/${PRODUCT}/aclnnop_resource
  ${OAM_TOOLS_DIR}/src/aml/ops/common/stub/op_api
)

set(OP_TILING_INCLUDE
  ${C_SEC_INCLUDE}
  ${PLATFORM_INC_DIRS}
  ${JSON_INCLUDE}
  ${OPBASE_INC_DIRS}
  ${METADEF_INCLUDE_DIRS}
  ${TILINGAPI_INC_DIRS}
  ${NPURUNTIME_INCLUDE_DIRS}
  ${OAM_TOOLS_DIR}
  ${NNOPBASE_INCLUDE_DIRS}
  ${OAM_TOOLS_DIR}/src/aml/ops/common/inc
)

set(OP_PROTO_INCLUDE
  ${C_SEC_INCLUDE}
  ${PLATFORM_INC_DIRS}
  ${METADEF_INCLUDE_DIRS}
  ${OPBASE_INC_DIRS}
  ${NPURUNTIME_INCLUDE_DIRS}
  ${OAM_TOOLS_DIR}
)

set(AICPU_INCLUDE
  ${OPBASE_INC_DIRS}
  ${AICPU_INC_DIRS}
  ${C_SEC_INCLUDE}
  ${NNOPBASE_INCLUDE_DIRS}
  ${HCCL_EXTERNAL_INCLUDE}
  ${METADEF_INCLUDE_DIRS}
)

set(AICPU_DEFINITIONS
  -O2
  -std=c++14
  -fstack-protector-all
  -fvisibility-inlines-hidden
  -fvisibility=hidden
  -frename-registers
  -fpeel-loops
  -DEIGEN_NO_DEBUG
  -DEIGEN_MPL2_ONLY
  -DNDEBUG
  -DEIGEN_HAS_CXX11_MATH
  -DEIGEN_OS_GNULINUX
  -DEigen=ascend_Eigen
  -fno-common
  -fPIC
)
