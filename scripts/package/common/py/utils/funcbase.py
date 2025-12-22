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

"""函数基础库。"""

import operator
from typing import Callable, Iterator, TypeVar


A = TypeVar('A')


def constant(value: A) -> Callable[..., A]:
    """常量值。"""
    def constant_inner(*_args, **_kwargs) -> A:
        return value

    return constant_inner


def dispatch(*funcs):
    """分派应用。"""
    def dispatch_inner(*args, **kwargs) -> Iterator:
        return (func(*args, **kwargs) for func in funcs)

    return dispatch_inner


def pipe(*funcs):
    """串联多个函数。"""
    def pipe_func(*args, **k_args):
        result = funcs[0](*args, **k_args)
        for func in funcs[1:]:
            result = func(result)
        return result

    return pipe_func


def identity(value: A) -> A:
    """同一。"""
    return value


def invoke(func, *args, **kwargs):
    """调用。"""
    return func(*args, **kwargs)


def side_effect(*funcs):
    """调用函数，产生副作用，但不影响管道结果。"""
    def side_effect_func(arg):
        for func in funcs:
            # 不保留结果
            func(arg)
        return arg

    return side_effect_func


def star_apply(func):
    """列表展开再应用。"""
    def star_apply_func(arg):
        return func(*arg)

    return star_apply_func


def any_(*funcs) -> Callable:
    """高阶any。
    注意，any有短路效果。"""
    return pipe(
        dispatch(*funcs),
        any,
    )


def not_(func) -> Callable:
    """高阶not。"""
    return pipe(func, operator.not_)
