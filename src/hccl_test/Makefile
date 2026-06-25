#
#loading path
#--------------------------------------------------------------------------------------------------------------------------------------------------
CXXFLAGS := -std=c++11\
        -Werror\
        -fstack-protector-strong\
        -fPIE -pie\
        -O2\
        -s\
        -Wl,-z,relro\
        -Wl,-z,now\
        -Wl,-z,noexecstack\
        -Wl,--copy-dt-needed-entries


ifneq (,$(filter HCCL_TEST_LOG_ENABLE, $(MAKECMDGOALS)))
	CXXFLAGS+= -DHCCL_TEST_LOG_ENABLE
endif

Common_DIR = ./common/src
Opbase_DIR = ./opbase_test

Common_SRC = $(wildcard ${Common_DIR}/*.cc)

HCCL_INC_DIR = ${ASCEND_DIR}/include
HCCL_LIB_DIR = ${ASCEND_DIR}/lib64

ACL_INC_DIR = ${ASCEND_DIR}/include
ACL_LIB_DIR = ${ASCEND_DIR}/lib64

MPI_INC_DIR = ${MPI_HOME}/include
MPI_LIB_DIR = ${MPI_HOME}/lib

PROF_INC_DIR = ${ASCEND_DIR}/include
PROF_LIB_DIR = ${ASCEND_DIR}/lib64

LIST = all_gather_test all_gatherv_test all_reduce_test alltoallv_test alltoall_test broadcast_test reduce_scatter_test reduce_scatterv_test reduce_test scatter_test alltoallvc_test

#
#library flags
#--------------------------------------------------------------------------------------------------------------------------------------------------
LIBS = -L$(HCCL_LIB_DIR) -lhccl\
		-L$(ACL_LIB_DIR) -lacl_rt\
		-L$(MPI_LIB_DIR) -lmpi\
        -L$(PROF_LIB_DIR) -lmsprofiler

INCLUDEDIRS = -I$(Common_DIR)\
				-I$(Opbase_DIR)\
				-I$(HCCL_INC_DIR)\
				-I$(ACL_INC_DIR)\
				-I$(MPI_INC_DIR)\
                -I$(PROF_INC_DIR)

.DEFAULT_GOAL := all

all_gather_test: SRC = hccl_allgather_rootinfo_test.cc
all_gatherv_test: SRC = hccl_allgatherv_rootinfo_test.cc
all_reduce_test: SRC = hccl_allreduce_rootinfo_test.cc
alltoallv_test: SRC = hccl_alltoallv_rootinfo_test.cc
alltoall_test: SRC = hccl_alltoall_rootinfo_test.cc
broadcast_test: SRC = hccl_brocast_rootinfo_test.cc
reduce_scatter_test: SRC = hccl_reducescatter_rootinfo_test.cc
reduce_scatterv_test: SRC = hccl_reducescatterv_rootinfo_test.cc
reduce_test: SRC = hccl_reduce_rootinfo_test.cc
scatter_test: SRC = hccl_scatter_rootinfo_test.cc
alltoallvc_test: SRC = hccl_alltoallvc_rootinfo_test.cc

#
#make
#--------------------------------------------------------------------------------------------------------------------------------------------------

.PHONY: HCCL_TEST_LOG_ENABLE
HCCL_TEST_LOG_ENABLE: all

all: $(LIST)

.PHONY: all $(LIST) clean

$(LIST):
	@mkdir -p bin
	g++ $(CXXFLAGS) $(Common_SRC) $(Opbase_DIR)/$(SRC) $(INCLUDEDIRS) -o bin/$@ $(LIBS)
	@printf "\033[0;32;32m$@ compile completed\n\033[m"

clean:
	rm -rf ./bin/*_test
