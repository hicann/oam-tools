#!/bin/bash
# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

set -x
echo $(grep -E "^VERSION_ID=" /etc/os-release | cut -d'"' -f2)
sudo update-alternatives --set gcc /usr/bin/gcc-14
gcc --version
source /home/jenkins/Ascend/cann/bin/setenv.bash
set +e

CANN_3RD_LIB_PATH="${CANN_3RD_LIB_PATH:-/home/jenkins/opensource}"

if [ "$TARGET_BRANCH" = "master" ];then
    case "${ut_type}" in
        asys)
            bash build.sh -u --component asys --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}" --cov
            ret=$?
            coverage_save="true"
            ;;
        msaicerr)
            bash build.sh -u --component msaicerr --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}" --cov
            ret=$?
            coverage_save="true"
            ;;
        msprof)
            bash build.sh -u --component msprof --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}" --cov
            ret=$?
            coverage_save="true"
            ;;
        ut_package)
            bash build.sh --make_clean --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}"
            ret=$?
            if [ $ret -eq 0 ]; then
                bash scripts/run_tests.sh --component install --st
                test_ret=$?
                [ $test_ret -eq 0 ] || ret=$test_ret
                bash scripts/run_tests.sh --component upgrade --st
                test_ret=$?
                [ $test_ret -eq 0 ] || ret=$test_ret
                bash scripts/run_tests.sh --component uninstall --st
                test_ret=$?
                [ $test_ret -eq 0 ] || ret=$test_ret
            fi
            coverage_save="false"
            ;;
        *)
            echo "Skip UT test execution for ${ut_type} on non-master branch"
            exit 0
            ;;
    esac
else
    bash build.sh --make_clean -u --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}"
    ret=$?
    coverage_save="false"
fi

if [ $ret -ne 200 ] && [ $ret -ne 0 ]; then
    echo "run ut fail"
    exit 1
fi
if [ $ret -eq 0 ]; then
    if [ "$coverage_save" = "true" ];then
    echo "ut_process=coverage" >> $ATOMGIT_OUTPUT
    else
    echo "ut_process=ut_cov" >> $ATOMGIT_OUTPUT
    fi
fi
exit 0
