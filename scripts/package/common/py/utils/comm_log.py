#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import time
import inspect
import logging

logging.basicConfig(format='[%(asctime)s] [%(levelname)s] [%(pathname)s] [line:%(lineno)d] %(message)s',
                    level=logging.INFO)


class CommLog:
    @staticmethod
    def cilog_get_timestamp():
        return time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())

    @staticmethod
    def cilog_print_element(cilog_element):
        print("["+cilog_element+"]", end=' ')
        return

    @staticmethod
    def cilog_logmsg(log_level, filename, line_no, log_msg, *log_paras):
        log_timestamp = CommLog.cilog_get_timestamp()
        CommLog.cilog_print_element(log_timestamp)
        CommLog.cilog_print_element(log_level)
        CommLog.cilog_print_element(filename)
        CommLog.cilog_print_element(str(line_no))
        print(log_msg % log_paras[0])
        return

    @staticmethod
    def cilog_error(log_msg, *log_paras):
        frame = inspect.currentframe().f_back
        line_no = frame.f_lineno
        filename = frame.f_code.co_filename
        CommLog.cilog_logmsg("ERROR", filename, line_no, log_msg, log_paras)
        return

    @staticmethod
    def cilog_warning(log_msg, *log_paras):
        frame = inspect.currentframe().f_back
        line_no = frame.f_lineno
        filename = frame.f_code.co_filename
        CommLog.cilog_logmsg("WARNING", filename, line_no, log_msg, log_paras)
        return

    @staticmethod
    def cilog_info(log_msg, *log_paras):
        frame = inspect.currentframe().f_back
        line_no = frame.f_lineno
        filename = frame.f_code.co_filename
        CommLog.cilog_logmsg("INFO", filename, line_no, log_msg, log_paras)
        return
