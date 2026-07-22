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

import sys

from unittest.mock import Mock, patch, mock_open
import pytest

from conftest import MSAICERR_PATH, CommonAssert
sys.path.append(MSAICERR_PATH)


class TestParseTilingMethods(CommonAssert):
    def test_parse_tiling_data_writes_file(self, mocker):
        mock_parser = mocker.patch(
            "parse_tiling.TilingDataParser")
        mock_instance = mock_parser.return_value
        mock_instance.parse.return_value = b"fake_tiling_data"
        mocker.patch("parse_tiling.open", mock_open())
        mocker.patch("parse_tiling.time")
        mocker.patch("parse_tiling.utils")

        from parse_tiling import parse_tiling_data
        from ms_interface.constant import Constant
        result = parse_tiling_data("/path/to/plog")
        self.assertEqual(result, Constant.MS_AICERR_NONE_ERROR)

    def test_parse_tiling_data_parser_called_with_plog(self, mocker):
        mock_parser = mocker.patch(
            "parse_tiling.TilingDataParser")
        mock_instance = mock_parser.return_value
        mock_instance.parse.return_value = b"data"
        mocker.patch("parse_tiling.open", mock_open())
        mocker.patch("parse_tiling.time")
        mocker.patch("parse_tiling.utils")

        from parse_tiling import parse_tiling_data
        parse_tiling_data("/my/plog/file.log")
        mock_parser.assert_called_once_with("/my/plog/file.log")

    def test_main_with_tiling_data(self, mocker):
        mocker.patch("sys.argv", ["parse_tiling.py", "-t", "/path/to/plog"])
        mocker.patch("parse_tiling.parse_tiling_data",
                     return_value=0)
        mocker.patch("parse_tiling.utils")

        from parse_tiling import main
        result = main()
        self.assertEqual(result, 0)

    def test_main_without_tiling_data(self, mocker):
        mocker.patch("sys.argv", ["parse_tiling.py"])
        mocker.patch("parse_tiling.utils")

        from parse_tiling import main
        from ms_interface.constant import Constant
        result = main()
        self.assertEqual(result, Constant.MS_AICERR_NONE_ERROR)

    def test_main_with_long_option(self, mocker):
        mocker.patch("sys.argv",
                     ["parse_tiling.py", "--tiling_data", "/path/to/plog"])
        mocker.patch("parse_tiling.parse_tiling_data",
                     return_value=0)
        mocker.patch("parse_tiling.utils")

        from parse_tiling import main
        result = main()
        self.assertEqual(result, 0)

    def test_parse_tiling_data_file_write_error(self, mocker):
        mock_parser = mocker.patch(
            "parse_tiling.TilingDataParser")
        mock_instance = mock_parser.return_value
        mock_instance.parse.return_value = b"data"
        mocker.patch("parse_tiling.open",
                     side_effect=OSError("Permission denied"))
        mocker.patch("parse_tiling.time")
        mocker.patch("parse_tiling.utils")

        from parse_tiling import parse_tiling_data
        with pytest.raises(OSError):
            parse_tiling_data("/path/to/plog")
