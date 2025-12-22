#!/bin/sh
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

logging() {
  echo "[INFO] $@"
}

mk_dir() {
  local create_dir="$1"
  mkdir -pv "${create_dir}"
  logging "Created ${create_dir}"
}

# using lcov to generate coverage for cpp files
generate_coverage() {
  local _source_dir="$1"
  local _coverage_file="$2"

  if [[ -z "${_source_dir}" ]]; then
    logging "directory required to find the .da files"
    exit 1
  fi

  if [[ ! -d "${_source_dir}" ]]; then
    logging "directory is not exist, please check ${_source_dir}"
    exit 1
  fi

  if [[ -z "${_coverage_file}" ]]; then
    _coverage_file="coverage.info"
    logging "using default file name to generate coverage"
  fi

  which lcov >/dev/null 2>&1
  if [[ $? -ne 0 ]]; then
    logging "lcov is required to generate coverage data, please install"
    exit 1
  fi

  local _path_to_gen="$(dirname ${_coverage_file})"
  if [[ ! -d "${_path_to_gen}" ]]; then
    mk_dir "${_path_to_gen}"
  fi

  lcov -c -d "${_source_dir}" -o "${_coverage_file}"
  lcov --ignore-errors inconsistent -r "${_coverage_file}" "${ASCEND_PARENT_PATH}/*" -o "${_coverage_file}"
  logging "generated coverage file ${_coverage_file}"
}

# filter out some unused directories or files
filter_coverage() {
  local _coverage_file="$1"
  local _filtered_file="$2"

  if [[ ! -f "${_coverage_file}" ]]; then
    logging "coverage data file required"
    exit 1
  fi

  which lcov >/dev/null 2>&1
  if [[ $? -ne 0 ]]; then
    logging "lcov is required to generate coverage data, please install"
    exit 1
  fi

  lcov --remove "${_coverage_file}" '${ASCEND_PARENT_PATH}/*'\
                                    '/usr/include/*'          \
                                    '*/third_party/*' \
                                    '*/common/*'    \
                                    '*/ops-nn-dev/tests/*'  \
                                    '*/ops-nn-dev/*/*/tests/*' -o "${_filtered_file}" --ignore-errors inconsistent
}

# generate html report
generate_html() {
  local _filtered_file="$1"
  local _out_path="$2"

  which genhtml >/dev/null 2>&1
  if [[ $? -ne 0 ]]; then
    logging "genhtml is required to generate coverage html report, please install"
    exit 1
  fi

  if [[ ! -d "${_out_path}" ]]; then
    mk_dir "${_out_path}"
  fi
  genhtml "${_filtered_file}" -o "${_out_path}"
}


if [[ $# -ne 3 ]]; then
  logging "Usage: $0 DIR COV_FILE OUT_PATH"
  exit 1
fi

_src="$1"
_cov_file="$2"
_out="$3"

ASCEND_PARENT_PATH=$(dirname "${ASCEND_HOME_PATH}")
if [[ -z "${ASCEND_PARENT_PATH}" ]]; then
  logging "ASCEND_HOME_PATH is not set"
  exit 1
fi

generate_coverage "${_src}" "${_cov_file}"
filter_coverage   "${_cov_file}" "${_cov_file}_filtered"
generate_html     "${_cov_file}_filtered" "${_out}"