if(NOT PROJECT_SOURCE_DIR)
    if(CANN_3RD_LIB_PATH AND IS_DIRECTORY "${CANN_3RD_LIB_PATH}/cann-cmake")
        include("${CANN_3RD_LIB_PATH}/cann-cmake/function/prepare.cmake")
    else()
        include(FetchContent)

        set(CANN_CMAKE_TAG "9.2.0-001")
        if(CANN_3RD_LIB_PATH AND EXISTS "${CANN_3RD_LIB_PATH}/cmake-${CANN_CMAKE_TAG}.tar.gz")
            FetchContent_Declare(
                cann-cmake
                URL "${CANN_3RD_LIB_PATH}/cmake-${CANN_CMAKE_TAG}.tar.gz"
                URL_HASH SHA256=d0709c53d6c89259a2cd229842c8ab92f5f39315d0ae1a1f53ef1a8b58bdb73f
            )
        else()
            FetchContent_Declare(
                cann-cmake
                GIT_REPOSITORY https://gitcode.com/cann/cmake.git
                GIT_TAG        ${CANN_CMAKE_TAG}
                GIT_SHALLOW    TRUE
            )
        endif()
        FetchContent_GetProperties(cann-cmake)
        if(NOT cann-cmake_POPULATED)
            FetchContent_Populate(cann-cmake)
        endif()
    include("${cann-cmake_SOURCE_DIR}/function/prepare.cmake")
    endif()
endif()
