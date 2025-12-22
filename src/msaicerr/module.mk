#build for tensor_utils

LOCAL_PATH := ${call my-dir}

include $(CLEAR_VARS)

TU_TAR_NAME := msaicerr_pyc.tgz

TENSOR_UTIL_DIR := $(HOST_OUT_ROOT)/tensor_utils/msaicerr

$(TENSOR_UTIL_DIR):
	@mkdir -p $@
	@cd toolchain/tensor_utils/msaicerr/ && ./build.sh $(TU_TAR_NAME) $(HI_PYTHON)
	@mv toolchain/tensor_utils/msaicerr/$(TU_TAR_NAME) $@ && tar zxvf $@/$(TU_TAR_NAME) -C $@
	@rm -rf $@/$(TU_TAR_NAME)

