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
import threading


__all__ = ["log_debug", "log_info", "log_warning", "log_error", "close_log", "open_log"]

LOG_FORMAT = "%(asctime)s [ASYS] [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
_LOG_LOCK = threading.RLock()


def _log(log_func, log_str, force=False):
    with _LOG_LOCK:
        if not force:
            log_func(log_str)
            return

        disable_level = logging.getLogger().manager.disable
        logging.disable(logging.NOTSET)
        try:
            log_func(log_str)
        finally:
            logging.disable(disable_level)


def log_debug(log_str):
    _log(logging.debug, log_str)


def log_info(log_str, force=False):
    _log(logging.info, log_str, force)


def log_warning(log_str, force=False):
    _log(logging.warning, log_str, force)


def log_error(log_str):
    _log(logging.error, log_str)


def open_log():
    with _LOG_LOCK:
        logging.disable(logging.NOTSET)


def close_log():
    with _LOG_LOCK:
        logging.disable(logging.INFO)
        logging.disable(logging.DEBUG)
        logging.disable(logging.WARNING)
