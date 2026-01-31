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

import re
import struct
from ms_interface import utils
from ms_interface.constant import Constant, RetCode


class AicErrorInfo:
    """
    AI core Error info
    """

    def __init__(self: any) -> None:
        self.aic_error_info = {}
        self.error_code_all = ""
        self.task_id = ""
        self.stream_id = ""
        self.node_name = ""
        self.kernel_name = ""
        self.flip_num = ""
        self.instr = ""
        self.graph_file = ""
        self.extra_info = ""
        self.err_time_obj = None
        self.ifu_err_type = ""
        self.mte_err_type = ""
        self.args_num_in_json = None
        self.dump_file = []
        self.dump_info = ""
        self.aval_addrs = []
        self.necessary_addr = {}
        self.atomic_add_err = False
        self.single_op_test_result = RetCode.NOT_RUN
        self.single_op_mem_monitor = ""
        self.data_dump_result = True
        self.atomic_clean_check = True
        self.args_before_list = []
        self.args_after_list = []
        self.addr_valid = True
        self.env_available = True
        self.flag_check = ""
        self.check_args_result = True
        self.debug_level = 0
        self.kernel_path = ""
        self.data_path = ""
        self.tiling_key = 0
        self.tiling_data = ""
        self.tiling_data_bytes = None
        self.block_dim = -1
        self.input_list = []
        self.output_list = []
        self.workspace_list = []
        self.bin_list = []
        self.cce_file = ""
        self.bin_file = ""
        self.json_file = ""
        self.run_device_id = 0
        self.sub_ptr_addrs = {}
        self.ffts_addrs_num = 0
        self.rts_block_dim = -1
        self.driver_aicore_num = -1
        self.workspace = 0
        self.hash_id = 0
        self.single_op_log_path = ""

    def analyse(self: any) -> str:
        """
        AI core error analyse
        """
        # 此步骤会解析出 mte_err_type ifu_err_type
        aicerror_info = self._get_aicerror_info()

        addr_check_str = self._get_addr_check_str()

        result_msg = {
            RetCode.SUCCESS: "Single-operator test case executed successfully.",
            RetCode.FAILED: "Single-operator test case failed to be executed.",
            RetCode.NOT_RUN: "Single-operator test case not executed."

        }
        single_op_mem_monitor = self.single_op_mem_monitor

        msg = f"""{self.root_cause_conclusion}

***********************1. Basic information********************
error time        : {self.aic_error_info.get('err_time', '')}
device id         : {self.aic_error_info.get('dev_id', '')}
core id           : {self.aic_error_info.get('core_id', '')}
task id           : {self.task_id}
stream id         : {self.stream_id}
node name         : {self.graph_file}
kernel name       : {self.kernel_name}
flip num          : {self.flip_num}
kernel file       : {self.bin_file}
json file         : {self.json_file}
cce file          : {self.cce_file}
rts_block_dim     : {self.rts_block_dim}
driver_aicore_num : {self.driver_aicore_num}

***********************2. AI Core DFX Register***********************
AIC_ERROR        : {self.error_code_all if self.error_code_all else self.aic_error_info.get('error_code', '')}
{aicerror_info}

***********************3. Operator Error Line Number************************
start pc          : {self.aic_error_info.get('start_pc', '')}
current pc        : {self.aic_error_info.get('current_pc', '')}
{self.instr}

****************4. Operator Input/Output Memory*******************
{addr_check_str}
args before execution: {self._get_args_str(self.args_before_list)}
args after  execution: {self._get_args_str(self.args_after_list)}

***********************5. Operator Dump File Parsing*************************
{self._get_tiling_str()}
{self.dump_info}

********************6. Execution Result of the Single-Operator Test Case***********************
{result_msg.get(self.single_op_test_result)}

{single_op_mem_monitor}
"""
        return msg

    def get_conclusion(self: any) -> str:
        conclusion = ""
        num_default = -1
        if not self.atomic_clean_check:
            conclusion = ("The memset or atomic_clean operator is not inserted before this operator in the graph,"
                          " while memory cleanup is required before operator execution.\n")
        elif self.flag_check:
            conclusion = "The set_flag and wait_flag instructions are not used together in the operator code.\n"
        elif (self.rts_block_dim != num_default and self.driver_aicore_num != num_default and
              self.rts_block_dim > self.driver_aicore_num * 2):
            conclusion = "The number of AI Cores in the environment is less than that required by the operator.\n"
        elif self.aic_error_info.get('current_pc', '') == "0x0":
            conclusion = "The line number of the operator error instruction is 0.\n"
        elif self.atomic_add_err:
            conclusion = ("Atomic add has a precision overflow. Check the operator precision."
                          "Note that if tasks are concurrently executed on the NPU, a false warning may be reported.\n")
        elif "data invalid" in self.dump_info:
            conclusion = ("The maintenance and test information is insufficient or the format is "
                          "incorrect, contact technical support.\n")
        elif self.single_op_test_result is RetCode.FAILED:
            conclusion = "Failed to execute the single-operator test case. The operator logic may be incorrect.\n"
        elif not self.check_args_result:
            conclusion = ("If the arguments are inconsistent before and after operator execution, "
                          "memory access may be out of bounds. You are advised to use the memory error detection model "
                          "to locate the fault.\n")
        elif not self.addr_valid or not self.data_dump_result:
            conclusion = ("The input/output memory address of the operator is abnormal "
                          "(or the original dumped data fails). Check the framework or application.\n")
        elif not self.env_available:
            conclusion = "Failed to execute the built-in sample operator. Check the environment.\n"
        elif self.single_op_test_result is True:
            conclusion = ("The single-operator test case is successfully executed. In case of an unknown error mode, "
                          "you are advised to:\n"
                          "(1) check the operator again by using the msSanitizer tool.\n"
                          "(2) If out-of-bounds memory access occurs on other operators, you are advised to enable "
                          "memory error detection with op_debug_config=oom and then check the operators, "
                          "For details: https://www.hiascend.com/zh/document.\n"
                          "(3) For details about the framework, contact technical support.\n")

        if not conclusion:
            if not utils.ExceptionRootCause().causes:
                conclusion = "Internal error. Contact technical support.\n"
            else:
                conclusion = ("The maintenance and test information is insufficient or the format is incorrect, "
                              "contact technical support.\n")
            conclusion += utils.ExceptionRootCause().format_causes()
        return conclusion

    @property
    def root_cause_conclusion(self):
        return self.get_conclusion()

    @staticmethod
    def _get_args_str(input_list: list) -> str:
        args_str = ""
        for arg in input_list:
            args_str += f"[{arg}],"
        return f"[{args_str[:-1]}]"

    def _get_tiling_str(self: any) -> str:
        if not self.tiling_data:
            return "\n"
        binfile = open(self.tiling_data, "rb")  # rb表示以二进制模式读取
        # 读取文件内容，返回一个bytes对象
        content = binfile.read()
        # 关闭文件
        binfile.close()
        result_str = f"tiling_data: {self.tiling_data}\n"
        tiling_datas = content
        int32_size = struct.calcsize('i')
        int64_size = struct.calcsize('q')
        float16_size = struct.calcsize('e')

        def parse_data(data, size, format):
            try:
                result = [struct.unpack(format, data[i:i + size])[0] for i in range(0, len(data), size)]
            except Exception as e:
                result = "Cannot decode in this dtype"
            return result

        int32_values = parse_data(tiling_datas, int32_size, 'i')
        result_str += f"tiling data in int32: {int32_values}\n"

        int64_values = parse_data(tiling_datas, int64_size, 'q')
        result_str += f"tiling data in int64: {int64_values}\n"

        float16_values = parse_data(tiling_datas, float16_size, 'e')
        result_str += f"tiling data in float16: {float16_values}\n"

        return result_str + "\n"

    def _get_addr_check_str(self: any) -> str:
        result_str = ""
        used_addrs = self.necessary_addr

        if not used_addrs:
            input_params, output_params = [], []
        else:
            input_params = used_addrs.get("input_addr")
            output_params = used_addrs.get("output_addr")

        for input_param in input_params:
            index = input_param.get("index")
            if not input_param.get("in_range"):
                result_str += f"*[ERROR]input[{index}] is out of range\n"
                self.addr_valid = False

        for output_param in output_params:
            index = output_param.get("index")
            if not output_param.get("in_range"):
                result_str += f"*[ERROR]output[{index}] is out of range\n"
                self.addr_valid = False
        result_str += "\n"
        for input_param in input_params:
            index = int(input_param.get("index"))
            size = int(input_param.get("size"))
            if input_param.get("addr").startswith("0x"):
                addr = int(input_param.get("addr"), 16)
            else:
                addr = int(input_param.get("addr"))
            end_addr = addr + size
            result_str += f"input[{index}] addr: {hex(addr)} end_addr:{hex(end_addr)} size: {hex(size)}\n"

        for output_param in output_params:
            index = int(output_param.get("index"))
            size = int(output_param.get("size"))
            if output_param.get("addr").startswith("0x"):
                addr = int(output_param.get("addr"), 16)
            else:
                addr = int(output_param.get("addr"))
            end_addr = addr + size
            result_str += f"output[{index}] addr: {hex(addr)} end_addr:{hex(end_addr)} size: {hex(size)}\n"

        fault_arg_indexes = used_addrs.get("fault_arg_index")
        need_check_args = used_addrs.get("need_check_args")
        if fault_arg_indexes:
            for arg_index in fault_arg_indexes:
                result_str += f"arg[{arg_index}][0x{need_check_args[arg_index]:X}] cannot find alloc log, " \
                              "if it is not tiling_gm, please check \n"

        workspace = used_addrs.get("workspace")
        if workspace:
            result_str += f"workspace_bytes:{workspace}\n"

        return result_str

    def _get_aicerror_info(self: any) -> str:
        aicerror_info_list = []
        handled_err_type = []
        ret = utils.hexstr_to_list_bin(self.aic_error_info.get('error_code', ''))
        if not ret:
            ret = [0]
        for i in ret:
            aicerr_info = Constant.AIC_ERROR_INFO_DICT.get(i)
            err_type = aicerr_info.split('_')[0].lower()
            if err_type in handled_err_type:
                continue
            handled_err_type.append(err_type)
            if err_type == "vec":
                aicerror_info_list.append("\nVEC_ERR_INFO : " + self._analyse_vec_errinfo())
            elif err_type == "ifu":
                aicerror_info_list.append("\nIFU_ERR_INFO : " + self._analyse_ifu_errinfo())
            elif err_type == "mte":
                aicerror_info_list.append("\nMTE_ERR_INFO : " + self._analyse_mte_errinfo(i))
            elif err_type == "cube":
                aicerror_info_list.append("\nCUBE_ERR_INFO: " + self._analyse_cube_errinfo())
            elif err_type == "ccu":
                aicerror_info_list.append("\nCCU_ERR_INFO : " + self._analyse_ccu_errinfo())
            elif err_type == "biu":
                aicerror_info_list.append("\nBIU_ERR_INFO : " + self._analyse_biu_errinfo())
            aicerror_info_list.append(f"\n{aicerr_info}")
            aicerror_info_list.append("\n\n")
        aicerror_info = "".join(aicerror_info_list).strip("\n")
        return aicerror_info

    # Error PC [9:2]
    def find_extra_pc(self: any) -> str:
        """
        find extra pc
        """
        ret = utils.hexstr_to_list_bin(self.aic_error_info.get('error_code', ''))
        if not ret:
            ret = [0]
        extra_err_key = ""
        key_map = {
            "vec": Constant.VEC_KEY,
            "mte": Constant.MTE_KEY,
            "cube": Constant.CUBE_KEY,
            "ccu": Constant.CCU_KEY,
            "biu": Constant.BIU_KEY,
            "ifu": Constant.IFU_KEY
        }
        for ret_a in ret:
            error_info = Constant.AIC_ERROR_INFO_DICT.get(ret_a)
            err_type = error_info.split('_')[0].lower()
            if err_type == "ccu":
                return ""
            if err_type in key_map.keys():
                extra_err_key = key_map.get(err_type)
                break

        if extra_err_key == "":
            return ""
        regexp = extra_err_key + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return ""
        if extra_err_key == Constant.MTE_KEY:
            high = utils.get_01_from_hexstr(ret[0], 39, 32)
            low = utils.get_01_from_hexstr(ret[0], 7, 0)
            return high + low
        return utils.get_01_from_hexstr(ret[0], 7, 0)

    def _analyse_ifu_errinfo(self: any) -> str:
        regexp = Constant.IFU_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No IFU_ERR_INFO found"

        errinfo = ret[0]
        # ifu_err_type
        code = utils.get_01_from_hexstr(ret[0], 50, 48)
        self.ifu_err_type = code

        if code in Constant.SOC_ERR_INFO_DICT:
            info = Constant.SOC_ERR_INFO_DICT.get(code)
        else:
            info = "NA"
        errinfo += f"\nifu_err_type bit[50:48]={code}  meaning:{info}"

        # ifu_err_addr
        code = utils.get_01_from_hexstr(ret[0], 47, 2)
        info = "IFU Error Address [47:2]"
        # 补2位0，猜测值
        approximate = hex(int(code + "00", 2))
        errinfo += f"\nifu_err_addr bit[47:2]={code}  meaning:{info}  approximate:{approximate}"
        return errinfo

    def _analyse_mte_errinfo(self: any, err_bit: any) -> str:
        regexp = Constant.MTE_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No MTE_ERR_INFO found"

        errinfo = ret[0]
        # mte_err_type
        code = utils.get_01_from_hexstr(ret[0], 26, 24)
        self.mte_err_type = code

        if err_bit == 46:
            mte_dict = Constant.UNZIP_ERR_INFO_DICT
        elif err_bit == 34:
            mte_dict = Constant.FMC_ERR_INFO_DICT
        elif err_bit == 25:
            mte_dict = Constant.FMD_ERR_INFO_DICT
        elif err_bit == 23:
            mte_dict = Constant.SOC_ERR_INFO_DICT
        elif err_bit == 21:
            mte_dict = Constant.AIPP_ERR_INFO_DICT
        else:
            mte_dict = {}

        if code in mte_dict:
            info = mte_dict.get(code)
        else:
            info = "NA"
        errinfo += "\nmte_err_type bit[26:24]={0:<14}  meaning:{1:}".format(code, info)

        # mte_err_addr
        code = utils.get_01_from_hexstr(ret[0], 22, 8)
        info = "MTE Error Address [19:5]"
        # 补5位0，猜测值
        approximate = hex(int(code + "00000", 2))
        errinfo += "\nmte_err_addr bit[22:8]={0:<15}  meaning:{1:}  approximate:{2:}".format(code, info, approximate)
        return errinfo

    def _analyse_biu_errinfo(self: any) -> str:
        regexp = Constant.BIU_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No BIU_ERR_INFO found"

        errinfo = ret[0]
        # biu_err_addr
        code = utils.get_01_from_hexstr(ret[0], 24, 0)
        approximate = hex(int(code, 2))
        errinfo += f"\nbiu_err_addr bit[24:0]={code}  in hex:{approximate}"
        return errinfo

    def _analyse_ccu_errinfo(self: any) -> str:
        regexp = Constant.CCU_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No CCU_ERR_INFO found"

        errinfo = ret[0]
        # ccu_err_addr
        code = utils.get_01_from_hexstr(ret[0], 22, 8)
        info = "CCU Error Address [17:3]"
        # 补3位0，猜测值
        approximate = hex(int(code + "000", 2))
        errinfo += f"\nccu_err_addr bit[22:8]={code}  meaning:{info}  approximate:{approximate}"
        return errinfo

    def _analyse_cube_errinfo(self: any) -> str:
        regexp = Constant.CUBE_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No CUBE_ERR_INFO found"

        errinfo = ret[0]
        # cube_err_addr
        code = utils.get_01_from_hexstr(ret[0], 16, 8)
        info = "CUBE Error Address [17:9]"
        # 补9位0，猜测值
        approximate = hex(int(code + "000000000", 2))
        errinfo += f"\ncube_err_addr bit[16:8]={code}  meaning:{info}  approximate:{approximate}"
        return errinfo

    def _analyse_vec_errinfo(self: any) -> str:
        regexp = f"{Constant.VEC_KEY}=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if not ret:
            return "No VEC_ERR_INFO found"

        errinfo = ret[0]
        # vec_err_addr
        code = utils.get_01_from_hexstr(ret[0], 28, 16)
        info = "VEC Error Address [17:5]"
        # 补5位0，猜测值
        approximate = hex(int(code + "00000", 2))
        errinfo += "\nvec_err_addr bit[28:16]={0:<13}  meaning:{1:<28}  approximate:{2}".format(code, info, approximate)

        # vec_err_rcnt
        code = utils.get_01_from_hexstr(ret[0], 15, 8)
        info = "VEC Error repeat count [7:0]"
        repeats = str(int(code, 2))
        errinfo += "\nvec_err_rcnt bit[15:8]={0:<13}  meaning:{1:<28}  repeats:{2}".format(code, info, repeats)
        return errinfo
