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
import sys
import os
import csv
from pathlib import Path

import pytest
from testcase.conftest import ASYS_SRC_PATH, ut_root_path
sys.path.insert(0, ASYS_SRC_PATH)

from common import FileOperate as f
from common import file_operate
from ..conftest import AssertTest

def setup_module():
    print("TestFileOperate ut test start.")

def teardown_module():
    print("TestFileOperate ut test finsh.")

class TestFileOperate(AssertTest):

    test_file_path = os.path.join(ut_root_path, "test_file")

    def setup_method(self):
        testfile = Path(self.test_file_path)
        testfile.touch(exist_ok=True)
        self.fp = open(testfile)

    def teardown_method(self):
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_check_file_success(self, mocker):
        mocker.patch("os.path.isfile", return_value=True)
        self.assertTrue(f.check_file(__file__))

    def test_check_file_failed(self, mocker):
        mocker.patch("os.path.isfile", return_value=False)
        self.assertTrue(not f.check_file(__file__))

    def test_check_dir_success(self, mocker):
        mocker.patch("os.path.isdir", return_value=True)
        self.assertTrue(f.check_dir(ut_root_path))

    def test_check_dir_failed(self, mocker):
        mocker.patch("os.path.isdir", return_value=False)
        self.assertTrue(not f.check_dir(ut_root_path))

    def test_create_dir_success(self, mocker):
        mocker.patch("os.makedirs", return_value=True)
        self.assertTrue(f.create_dir("./test_dir"))

    def test_create_dir_failed(self, mocker):
        mocker.patch("os.makedirs", side_effect=OSError)
        self.assertTrue(not f.create_dir("./test_dir"))

    def test_remove_dir_success(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("shutil.rmtree", return_value=True)
        self.assertTrue(f.remove_dir("./test_dir"))

    @pytest.mark.parametrize("access_set, output", [
        ([False, False], False),
        ([True, False], False),
    ])
    def test_remove_dir_failed(self, access_set, output, mocker):
        mocker.patch("os.access", side_effect=access_set)
        mocker.patch("shutil.rmtree", return_value=True)
        self.assertTrue(not f.remove_dir("./test_dir"))

    @pytest.mark.parametrize("remove_dir, err_res", [
        (True, False),
        (False, True),
    ])
    def test_delete_dirs(self, remove_dir, err_res, mocker, capsys, caplog):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.remove_dir", return_value=remove_dir)
        f.delete_dirs(["./test1", "./test2"])
        self.assertTrue(("failed in asys clean work" in caplog.text) == err_res)

    def test_walk_dir_success(self, mocker):
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.walk", return_value=[])
        self.assertTrue(f.walk_dir("./test_dir") == [])

    def test_walk_dir_failed(self, mocker):
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.walk_dir("./test_dir"))

    def test_list_dir_success(self, mocker):
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.listdir", return_value=[])
        self.assertTrue(f.list_dir("./test_dir") == [])

    def test_list_dir_failed(self, mocker):
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.list_dir("./test_dir"))

    def test_copy_dir_success(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.isdir", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("shutil.copytree")
        self.assertTrue(f.copy_dir("./test_src", "./test_dst"))

    def test_copy_dir_failed(self, mocker):
        mocker.patch("shutil.copytree")
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.access", return_value=True)
        self.assertTrue(not f.copy_dir("./test_src", "./test_dst"))
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.copy_dir("./test_src", "./test_dst"))
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.copy_dir("./test_src", "./test_dst"))
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.isdir", return_value=True)
        mocker.patch("os.path.relpath", return_value='..')
        self.assertTrue(not f.copy_dir("./test_src", "./test_dst"))

    def test_move_dir_success(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.isdir", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("shutil.rmtree")
        mocker.patch("shutil.move")
        self.assertTrue(f.move_dir("./test_src", "./test_dst"))

    def test_move_dir_failed(self, mocker):
        mocker.patch("os.path.exists", return_value=False)
        self.assertTrue(not f.move_dir("./test_src", "./test_dst"))

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.move_dir("./test_src", "./test_dst"))

    def test_copy_file_to_dir_success(self, mocker):
        mocker.patch("shutil.copy")
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.path.isfile", return_vale=True)
        self.assertTrue(f.copy_file_to_dir("./test_file", "./test_dst"))
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.path.exists", return_vale=False)
        mocker.patch("os.makedirs")
        self.assertTrue(f.copy_file_to_dir("./test_file", "./test_dst"))


    def test_copy_file_to_dir_failed(self, mocker):
        mocker.patch("shutil.copy")
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.access", return_value=True)
        self.assertTrue(not f.copy_file_to_dir(self.test_file_path, "./test_dst"))
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.copy_file_to_dir(self.test_file_path, "./test_dst"))
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.copy_file_to_dir(self.test_file_path, "./test_dst"))
        mocker.patch("os.path.relpath")
        self.assertTrue(not f.copy_file_to_dir(self.test_file_path, "./test_dst"))

    def test_move_file_to_dir_success(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("shutil.move")
        self.assertTrue(f.move_file_to_dir("./test_file", "./test_dst"))

    def test_move_file_to_dir_failed(self, mocker):
        mocker.patch("os.path.exists", return_value=False)
        self.assertTrue(not f.move_file_to_dir("./test_file", "./test_dst"))

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not f.move_file_to_dir("./test_file", "./test_dst"))

    def test_write_file(self, mocker):
        mocker.patch('builtins.open')
        f.write_file(self.test_file_path, "test_info")

    def test_write_file_no_prepath(self, mocker):
        mocker.patch('builtins.open')
        mocker.patch('os.path.exists', return_value=False)
        mocker.patch('common.FileOperate.create_dir', return_value=False)
        f.write_file(self.test_file_path, "test_info")

    def test_read_plain_file(self, mocker):
        mocker.patch('builtins.open')
        self.assertTrue(f.read_file(self.test_file_path))

    def test_read_ini_file(self, mocker):
        mocker.patch('configparser.ConfigParser')
        self.assertTrue(f.read_file("./test_file.ini"))

    def test_read_csv_file(self, mocker):
        mocker.patch('builtins.open')
        self.assertTrue(f.read_file("./test_file.csv") == [])

    def test_check_valid_dir(self):
        self.assertTrue(f.check_valid_dir(ut_root_path))

    def test_check_valid_dir_error(self):
        self.assertTrue(not f.check_valid_dir(os.path.join(ut_root_path, "abs")))

    def test_check_vaild_error(self):
        self.assertTrue(not f.check_file(None))
        self.assertTrue(not f.check_dir(False))
        self.assertTrue(f.check_emtpy(''))
        self.assertTrue(not f.check_access(0))
        f.write_file(None, "test_info")
        self.assertTrue(not f.remove_file(''))
    
    def test_read_config_exec(self, mocker, caplog):
        temp_file = '/tmp/test_config_table.csv'
        if os.path.exists(temp_file):
            os.remove(temp_file)
        mocker.patch.object(file_operate, 'CONFIG_TABLE_FILE', temp_file)
        result = f().read_config()
        self.assertTrue(result == {})
        self.assertTrue('does not exist' in caplog.text)
 
        with open(temp_file, 'w') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(['Key', 'cfg_get', 'cfg_set', 'cfg_restore'])
            writer.writerow(['Setting1', 'get1,get2', 'set1,set2', 'restore1,restore2'])
            writer.writerow(['Setting2', 'get3,get4', 'set3'])
            writer.writerow(['Setting2', 'get3,get4', 'restore3'])
        os.chmod(temp_file, 0o111)
        self.assertTrue(f().read_config() == {})
        self.assertTrue("Error: Permission denied for file" in caplog.text)
        os.chmod(temp_file, 0o644)
 
        self.assertTrue(f().read_config() == {})
        self.assertTrue("format or content is error" in caplog.text)
        os.remove(temp_file)

    def test_append_write_file_failed(self, mocker, caplog):
        mocker.patch('os.path.exists', return_value=False)
        mocker.patch.object(f, 'create_dir', return_value=False)
        f.append_write_file(self.test_file_path, "test_info")
        self.assertTrue("failed in write file" in caplog.text)

    @pytest.mark.parametrize("mode, res", [
        ('m', True),
        ('c', True),
        ('b', False)
    ])
    def test_collect_file_to_dir(self, mode, res, mocker, caplog):
        mocker.patch.object(f, 'copy_file_to_dir', return_value=True)
        mocker.patch.object(f, 'move_file_to_dir', return_value=True)
        mocker.patch.object(f, 'move_dir', return_value=True)
        mocker.patch.object(f, 'copy_dir', return_value=True)
        self.assertTrue(f.collect_file_to_dir(self.test_file_path, "./dst", mode) == res)
        self.assertTrue(f.collect_dir(self.test_file_path, "./dst", mode) == res)
