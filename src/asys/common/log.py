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

import logging


__all__ = ["log_debug", "log_info", "log_warning", "log_error", "close_log", "open_log"]

LOG_FORMAT = "%(asctime)s [ASYS] [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def log_debug(log_str):
    logging.debug(log_str)


def log_info(log_str):
    logging.info(log_str)


def log_warning(log_str):
    logging.warning(log_str)


def log_error(log_str):
    logging.error(log_str)


def open_log():
    logging.disable(logging.NOTSET)


def close_log():
    logging.disable(logging.INFO)
    logging.disable(logging.DEBUG)
    logging.disable(logging.WARNING)
