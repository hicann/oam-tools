#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
"""
Function:
The file mainly involves main function of parsing input arguments.
Copyright Information:
Huawei Technologies Co., Ltd. All Rights Reserved © 2020
"""

import sys
import os
import time
import argparse
import tarfile
import traceback
from ms_interface import utils
from ms_interface.collection import Collection
from ms_interface.constant import Constant
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.dsmi_interface import DSMIInterface, get_soc_version
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.utils import screen_error


def handle_exception(exc_type, exc_value, exc_traceback):
    utils.GLOBAL_RESULT = False
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print('Uncaught exception:')
    traceback.print_exception(exc_type, exc_value, exc_traceback)


sys.excepthook = handle_exception


def extract_tar(tar_file, path):
    tar = tarfile.open(tar_file, "r")
    tar.extractall(path)
    tar.close()


def get_select_dir(path):
    subdir = os.listdir(path)
    if len(subdir) != 1:
        raise ValueError("[ERROR] found more than one subdir in collect tar")
    report_path = os.path.join(path, subdir[0])
    return report_path


def check_device_valid(device_id):
    if not verify_device_id(device_id):
        utils.print_error_log(f"Invalid device_id {device_id}")
        return False

    utils.print_info_log(f"Valid device_id {device_id}")
    return True


def analyse_report_path(args):
    if not check_device_valid(args.device_id):
        return Constant.MS_AICERR_INVALID_PARAM_ERROR

    if not args.output_path:
        utils.print_info_log("The current directory will be used to as the output directory of the analysis report.")
        args.output_path = os.getcwd()
    try:
        current_path = os.getcwd()
        input_path = os.path.abspath(args.report_path)
        if current_path.find(input_path) >= 0 or os.path.abspath(args.output_path).find(input_path) >= 0:
            utils.print_error_log("Do not run msaicerr in the directory specified by -p or its subdirectory." \
                        " Make sure -out specifies a different directory (including its subdirectory) from -p.")
            return Constant.MS_AICERR_INVALID_PATH_ERROR
        collect_time = time.localtime()
        cur_time_str = time.strftime("%Y%m%d%H%M%S", collect_time)
        utils.check_path_valid(os.path.realpath(args.output_path), isdir=True, output=True)
        output_path = os.path.join(os.path.realpath(args.output_path), "info_" + cur_time_str)
        utils.check_path_valid(output_path, isdir=True, output=True)
        # 解压路径存在就不需要再次解压了
        if not args.report_path and args.tar_file:
            utils.print_info_log("Start to unzip tar.gz package.")
            extract_path = "extract_" + cur_time_str
            extract_tar(args.tar_file, extract_path)
            args.report_path = get_select_dir(extract_path)

        # collect info
        collection = Collection(args.report_path, output_path)
        collect_succ = collection.collect()

        # parse ai core error
        parser = AicoreErrorParser(output_path, args.device_id, collect_succ)
        return parser.parse()

    except utils.AicErrException as error:
        utils.print_error_log(
            f"The aicore error analysis tool has an exception, and error code is {error.error_info}.")
        return Constant.MS_AICERR_INVALID_PATH_ERROR


# noinspection PyBroadException
def convert_dump_data(args, data_path):
    try:
        utils.check_path_valid(args.data)
        if not args.output_path:
            dump_file_path, _ = os.path.split(os.path.realpath(args.data))
            utils.check_path_valid(dump_file_path, isdir=True, output=True)
            utils.print_info_log(
                "The dump file directory will be used to as the output directory of the parsed results.")
        else:
            utils.check_path_valid(args.output_path, isdir=True, output=True)
    except Exception:
        return Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR

    try:
        info = AicErrorInfo()
        DumpDataParser(data_path, info, args.output_path).parse()
        utils.print_debug_log(info.dump_info)
        return Constant.MS_AICERR_NONE_ERROR
    except BaseException:
        return Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR


def verify_device_id(device_id):
    total_device_count = DSMIInterface().get_device_count()
    utils.print_info_log(f"Total device count: {total_device_count}")
    if device_id < 0 or device_id >= total_device_count:
        return False
    return True


@screen_error
def test_env(device_id=0):
    if not check_device_valid(device_id):
        return Constant.MS_AICERR_INVALID_PARAM_ERROR
    try:
        soc_version = get_soc_version()
        utils.print_info_log(f"Get soc_version: {soc_version}")
        utils.print_info_log("Start to test env with golden op.")
        result = AicoreErrorParser.run_test_env(soc_version, device_id=device_id)
        if result:
            utils.print_info_log(
                "The build-in sample operator runs successfully, The environment is normal.")
            return Constant.MS_AICERR_NONE_ERROR
        else:
            utils.print_error_log(
                "The built-in sample operator running failed. Check the software and hardware environment.")
            return Constant.MS_AICERR_HARDWARE_ERR
    except BaseException:
        return Constant.MS_AICERR_HARDWARE_ERR


class RequireOtherArgs(argparse.Action):

    def __init__(self, option_strings, dest, required_args=None, **kwargs):
        super().__init__(option_strings, dest, **kwargs)
        self.required_args = required_args or []

    @property
    def real_options(self):
        return [arg for arg in sys.argv[1:] if arg.startswith('-')]

    def inputted_dest(self, parser):
        inputted_dest = set()
        for arg in self.real_options:
            if arg not in parser._option_string_actions.keys():
                continue
            inputted_dest.add(parser._option_string_actions[arg].dest)
        return inputted_dest

    @staticmethod
    def formated_arg(dest, parser):
        return '/'.join(parser._option_string_actions[f'--{dest}'].option_strings)

    def __call__(self, parser, namespace, values, option_string=None):
        has_args = [arg for arg in self.required_args if arg in self.inputted_dest(parser)]
        if not has_args:
            args = list(map(lambda x: self.formated_arg(x, parser), self.required_args))
            formatted_args = ', '.join(args[:-1]) + f" or {args[-1]}" if len(args) > 1 else args[0]
            parser.error(f"{option_string} must be used with {formatted_args}")
        setattr(namespace, self.dest, values)


def main() -> int:
    """
    main function
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--report_path", dest="report_path", default="",
        help="Specify the directory where the AI Core error information is stored when analyzing the AI Core error.",
        required=False)
    parser.add_argument(
        "-d", "--data", dest="data", default="",
        help="Specify the dump file path when parsing the dump file.", required=False)
    parser.add_argument(
        "-e", "--env", dest="env", action="store_true",
        help="Check the environment when running the built-in sample operator.", required=False)
    parser.add_argument(
        "-out", "--output_path", dest="output_path", default="",
        help="Specify the output directory of the result. This argument is valid only for --report_path and --data.",
        required=False,
        action=RequireOtherArgs, required_args=['report_path', 'data'])
    parser.add_argument(
        "-dev", "--device_id", dest="device_id", default=0, type=int,
        help="Specify the ID of the device for running the operator. Defaults to 0 if not specified. "
             "This argument is valid only for --report_path and --env.", required=False,
        action=RequireOtherArgs, required_args=['report_path', 'env'])

    ascend_opp_path = os.environ.get("ASCEND_OPP_PATH")
    if not ascend_opp_path:
        utils.print_error_log("Environment variable not set after the CANN software is installed.")
        return Constant.MS_AICERR_INVALID_PATH_ERROR
    
    if len(sys.argv) <= 1:
        utils.print_error_log("Please execute : python msaicerr.py -h")
        parser.print_usage()
        return Constant.MS_AICERR_INVALID_PARAM_ERROR

    args, unknown = parser.parse_known_args()
    debug_log = 'debug_info.txt'
    if not os.access(os.getcwd(), os.W_OK) or (os.path.exists(debug_log) and not os.access(debug_log, os.W_OK)):
        utils._print_log("ERROR", "The current directory or debug_info.txt is immutable, Please check.")
        return Constant.MS_AICERR_INVALID_PATH_ERROR

    if args.data:
        return convert_dump_data(args, args.data)
    elif args.report_path:
        return analyse_report_path(args)
    elif args.env:
        return test_env(args.device_id)

    if unknown:
        utils.print_error_log(f"Invalid argument {unknown}, please run help to check the usage.")
        return Constant.MS_AICERR_INVALID_PARAM_ERROR
    return Constant.MS_AICERR_INVALID_PARAM_ERROR


if __name__ == '__main__':
    sys.exit(main())
