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

include(CMakePackageConfigHelpers)

set(CMAKE_CXX_STANDARD 11)

macro(install_package)
    set(file_count 1)
    set(directory_count 1)
    foreach(arg ${ARGN})
        if (arg STREQUAL "PACKAGE")
            set (key PKG_NAME)
        elseif (arg STREQUAL "TARGETS")
            set (key TARGET_LIST)
        elseif (arg STREQUAL "FILES")
            set (key ${arg}_${file_count})
            set (prekey "FILES")
        elseif (arg STREQUAL "DIRECTORY")
            set (key ${arg}_${directory_count})
            set (prekey "DIRECTORY")
        elseif (arg STREQUAL "DESTINATION")
            if (prekey STREQUAL "FILES")
                set (key ${prekey}_${arg}_${file_count})
                math(EXPR file_count "${file_count}+1")
            else ()
                set (key ${prekey}_${arg}_${directory_count})
                math(EXPR directory_count "${directory_count}+1")
            endif()
        else ()
            list(APPEND ${key} ${arg})
        endif()
    endforeach()
    math(EXPR file_count "${file_count}-1")
    math(EXPR directory_count "${directory_count}-1")

    install(TARGETS ${TARGET_LIST}
        EXPORT ${PKG_NAME}-targets
        LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}
        ARCHIVE DESTINATION ${INSTALL_LIBRARY_DIR}
        RUNTIME DESTINATION ${INSTALL_RUNTIME_DIR}
    )

    if (file_count GREATER 0)
        foreach(i RANGE 1 ${file_count})
            install(FILES ${FILES_${i}} DESTINATION ${FILES_DESTINATION_${i}} EXCLUDE_FROM_ALL)
        endforeach()
    endif()

    if (directory_count GREATER 0)
        foreach(i RANGE 1 ${directory_count})
            install(DIRECTORY ${DIRECTORY_${i}} DESTINATION ${DIRECTORY_DESTINATION_${i}}
                EXCLUDE_FROM_ALL
                FILES_MATCHING 
                PATTERN "*.h"
                PATTERN "*.cppm")
        endforeach()
    endif()

    unset(PKG_NAME)
    unset(TARGET_LIST)
    if (file_count GREATER 0)
        foreach(i RANGE 1 ${file_count})
            unset(FILES_${i})
            unset(FILES_DESTINATION_${i})
        endforeach()
    endif()
    if (directory_count GREATER 0)
        foreach(i RANGE 1 ${directory_count})
            unset(DIRECTORY_${i})
            unset(DIRECTORY_DESTINATION_${i})
        endforeach()
    endif()
endmacro(install_package)


set(TARGET_SYSTEM_NAME "Linux")

set(MSPROF_DIR ${CMAKE_CURRENT_SOURCE_DIR})

add_library(msprof_headers INTERFACE)
target_include_directories(msprof_headers INTERFACE
    $<BUILD_INTERFACE:${MSPROF_DIR}/inc>
    $<BUILD_INTERFACE:${MSPROF_DIR}/inc/toolchain>
    $<BUILD_INTERFACE:${MSPROF_DIR}/inc/external>
    $<INSTALL_INTERFACE:include>
    $<INSTALL_INTERFACE:include/msprof>
    $<INSTALL_INTERFACE:include/msprof/toolchain>
)

add_subdirectory(collector)

set(MSPROF_INSTALL_CONFIG_DIR  ${INSTALL_LIBRARY_DIR}/msprof/lib/cmake)

add_custom_target(profiling
    ${CMAKE_COMMAND} -E echo "begin to build profiling"
    && ${CMAKE_COMMAND} -E make_directory ${MSPROF_INSTALL_CONFIG_DIR}/profiling
    COMMAND cp -rf ${CMAKE_CURRENT_SOURCE_DIR}/* ${MSPROF_INSTALL_CONFIG_DIR}/profiling/
    && ${CMAKE_COMMAND} -E chdir ${MSPROF_INSTALL_CONFIG_DIR}/profiling/build/build_hiprof ./build_for_hiprof.sh "debug"
)

install(DIRECTORY
    ${MSPROF_INSTALL_CONFIG_DIR}/profiling # install_config_dir is a relative path, must Splicing it while install
    DESTINATION
    ${INSTALL_TOOLS_DIR}/profiler
    ${INSTALL_OPTIONAL}
    COMPONENT oam-tools
)
