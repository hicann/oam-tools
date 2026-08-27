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

#### CPACK to package run #####

# download makeself package
function(pack_custom)
  message(STATUS "System processor: ${CMAKE_SYSTEM_PROCESSOR}")
  if (CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64")
      message(STATUS "Detected architecture: x86_64")
      set(ARCH x86_64)
  elseif (CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64|arm")
      message(STATUS "Detected architecture: ARM64")
      set(ARCH aarch64)
  else ()
      message(WARNING "Unknown architecture: ${CMAKE_SYSTEM_PROCESSOR}")
  endif ()
  set(PACK_CUSTOM_NAME "cann-ops-math-${VENDOR_NAME}_linux-${ARCH}")
  set(PATH_NAME "${VENDOR_NAME}_math")
  npu_op_package(${PACK_CUSTOM_NAME}
    TYPE RUN
    CONFIG
      ENABLE_SOURCE_PACKAGE True
      ENABLE_BINARY_PACKAGE True
      INSTALL_PATH ${CMAKE_INSTALL_PREFIX}/
      VENDOR_NAME ${PATH_NAME}
      ENABLE_DEFAULT_PACKAGE_NAME_RULE False
  )

  npu_op_package_add(${PACK_CUSTOM_NAME}
    LIBRARY
      cust_opapi
  )
  if (TARGET cust_proto)
    npu_op_package_add(${PACK_CUSTOM_NAME}
        LIBRARY
        cust_proto
    )
  endif()
  if (TARGET cust_opmaster)
    npu_op_package_add(${PACK_CUSTOM_NAME}
        LIBRARY
        cust_opmaster
    )
  endif()
endfunction()

function(pack_built_in)
  #### built-in package ####
  message(STATUS "System processor: ${CMAKE_SYSTEM_PROCESSOR}")
  if (CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64")
      message(STATUS "Detected architecture: x86_64")
      set(ARCH x86_64)
  elseif (CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64|arm")
      message(STATUS "Detected architecture: ARM64")
      set(ARCH aarch64)
  else ()
      message(WARNING "Unknown architecture: ${CMAKE_SYSTEM_PROCESSOR}")
  endif ()

  set(script_prefix ${OAM_TOOLS_DIR}/scripts/package/oam_tools/scripts)
  install(DIRECTORY ${script_prefix}/
      DESTINATION share/info/oam_tools/script
      FILE_PERMISSIONS
      OWNER_READ OWNER_WRITE OWNER_EXECUTE  # 文件权限
      GROUP_READ GROUP_EXECUTE
      WORLD_READ WORLD_EXECUTE
      DIRECTORY_PERMISSIONS
      OWNER_READ OWNER_WRITE OWNER_EXECUTE  # 目录权限
      GROUP_READ GROUP_EXECUTE
      WORLD_READ WORLD_EXECUTE
      COMPONENT oam-tools
  )

  set(SCRIPTS_FILES
      ${CANN_CMAKE_DIR}/scripts/install/check_version_required.awk
      ${CANN_CMAKE_DIR}/scripts/install/common_func.inc
      ${CANN_CMAKE_DIR}/scripts/install/common_interface.sh
      ${CANN_CMAKE_DIR}/scripts/install/common_interface.csh
      ${CANN_CMAKE_DIR}/scripts/install/common_interface.fish
      ${CANN_CMAKE_DIR}/scripts/install/version_compatiable.inc
  )

  install(FILES ${SCRIPTS_FILES}
      DESTINATION share/info/oam_tools/script
      COMPONENT oam-tools
  )
  set(COMMON_FILES
      ${CANN_CMAKE_DIR}/scripts/install/install_common_parser.sh
      ${CANN_CMAKE_DIR}/scripts/install/common_func_v2.inc
      ${CANN_CMAKE_DIR}/scripts/install/common_installer.inc
      ${CANN_CMAKE_DIR}/scripts/install/script_operator.inc
      ${CANN_CMAKE_DIR}/scripts/install/version_cfg.inc
  )

  set(PACKAGE_FILES
      ${COMMON_FILES}
      ${CANN_CMAKE_DIR}/scripts/install/multi_version.inc
  )

  install(FILES ${CMAKE_BINARY_DIR}/version.oam-tools.info
      DESTINATION share/info/oam_tools
      RENAME version.info
      COMPONENT oam-tools
  )
  install(FILES ${PACKAGE_FILES}
      DESTINATION share/info/oam_tools/script
      COMPONENT oam-tools
  )

  string(FIND "${ASCEND_COMPUTE_UNIT}" ";" SEMICOLON_INDEX)
  if (SEMICOLON_INDEX GREATER -1)
      # 截取分号前的字串
      math(EXPR SUBSTRING_LENGTH "${SEMICOLON_INDEX}")
      string(SUBSTRING "${ASCEND_COMPUTE_UNIT}" 0 "${SUBSTRING_LENGTH}" compute_unit)
  else()
      # 没有分号取全部内容
      set(compute_unit "${ASCEND_COMPUTE_UNIT}")
  endif()

  message(STATUS "current compute_unit is: ${compute_unit}")

  # 仅 rpm 需要：rpmbuild 的 brp-strip 会对 bundle 内 Ascend NPU 的 .o（非标准 ELF）
  # 执行 strip 并失败中断打包，故禁掉。deb 侧 dpkg-deb 不跑 brp-strip、实测无需处理；
  # 若后续 deb 接入 dh 工具链或启用 CPACK_DEBIAN_PACKAGE_SHLIBDEPS，需在此补 deb 分支。
  # deb,rpm 与 all 同样产出 rpm，只判 STREQUAL "rpm" 会漏掉它们而使打包中断；
  # "all" 不含 rpm 子串，须单列。
  if(PACKAGE_TYPE MATCHES "rpm" OR PACKAGE_TYPE STREQUAL "all")
    set(CPACK_RPM_SPEC_MORE_DEFINE "%define __strip /bin/true
%define __objdump /bin/true
%define debug_package %{nil}")
  endif()

  set_cann_cpack_config(oam-tools SHARE_INFO_NAME oam_tools PACKAGE_TYPE ${PACKAGE_TYPE})

endfunction()