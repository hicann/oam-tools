/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "securec.h"
#include "osal_linux.h"
#include "osal_mem.h"

class OSAL_LINUX_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown()
    {
        GlobalMockObject::verify();
        GlobalMockObject::reset();
    }
};

TEST_F(OSAL_LINUX_TEST, LinuxSleep)
{
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxSleep(OSAL_ZERO));

    MOCKER(usleep).stubs().will(returnValue(OSAL_EN_ERROR));
    EXPECT_EQ(OSAL_EN_ERROR, LinuxSleep(OSAL_MAX_SLEEP_MILLSECOND_USING_USLEEP));
}

TEST_F(OSAL_LINUX_TEST, LinuxGetPid) { EXPECT_GE(LinuxGetPid(), 0); }

TEST_F(OSAL_LINUX_TEST, LinuxGetTid) { EXPECT_EQ(OSAL_EN_ERROR, LinuxGetTid()); }

TEST_F(OSAL_LINUX_TEST, LinuxSocket)
{
    OsalSockHandle listenfd, connfd;
    struct sockaddr_in serv_add;
    OsalSocklen stAddrLen = sizeof(serv_add);

    listenfd = LinuxSocket(AF_INET, SOCK_STREAM, 0);
    ASSERT_EQ(OSAL_EN_ERROR, listenfd);

    memset_s(&serv_add, sizeof(serv_add), '0', sizeof(serv_add));
    int32_t p = 50001;
    serv_add.sin_family = AF_INET;
    serv_add.sin_addr.s_addr = 0;
    serv_add.sin_port = htons(p);

    int32_t ret = LinuxBind(listenfd, (OsalSockAddr*)&serv_add, stAddrLen);
    ASSERT_EQ(OSAL_EN_ERROR, ret);

    ret = LinuxListen(listenfd, 5);
    ASSERT_EQ(OSAL_EN_ERROR, ret);

    connfd = LinuxAccept(listenfd, (OsalSockAddr*)nullptr, nullptr);
    ASSERT_EQ(OSAL_EN_ERROR, connfd);

    ret = LinuxConnect(listenfd, (OsalSockAddr*)&serv_add, stAddrLen);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
}

TEST_F(OSAL_LINUX_TEST, LinuxSocketSend)
{
    char msg[50] = {"test socket send!"};
    int32_t result = 0;

    result = LinuxSocketSend(-1, msg, 50, 0);
    ASSERT_EQ(OSAL_EN_ERROR, result);

    result = LinuxSocketRecv(1, nullptr, 50, 0);
    ASSERT_EQ(OSAL_EN_ERROR, result);
}

TEST_F(OSAL_LINUX_TEST, LinuxGetErrorCode) { ASSERT_EQ(errno, LinuxGetErrorCode()); }

TEST_F(OSAL_LINUX_TEST, LinuxCreateProcess)
{
    int pid = -1;
    char* argv[] = {(char*)"ls", (char*)"-al", nullptr};
    char* envp[] = {(char*)"PATH=/bin", nullptr};
    char* filename = (char*)"/bin/ls";
    char redirectLog[1024] = "/tmp/osal_linux_utest_createprocess.txt";
    int status = 0;
    OsalArgvEnv env;
    env.argv = argv;
    env.argvCount = 2;
    env.envp = envp;
    env.envpCount = 1;
    int ret = LinuxCreateProcess(filename, &env, nullptr, nullptr);
    ASSERT_EQ(OSAL_EN_ERROR, ret);

    ASSERT_EQ(OSAL_EN_ERROR, LinuxWaitPid(pid, &status, 0));
}

VOID* UTtest_callback(VOID* pstArg)
{
    int32_t pid = LinuxGetPid();
    int32_t tid = LinuxGetTid();
    printf("UTtest_callback, the pid = %d, the tid = %d.\r\n", pid, tid);
    LinuxSleep(100);
    return nullptr;
}

TEST_F(OSAL_LINUX_TEST, LinuxCreateTaskWithThreadAttr)
{
    OsalThread stThreadHandle;
    OsalUserBlock stFuncBlock;
    stFuncBlock.procFunc = UTtest_callback;
    stFuncBlock.pulArg = nullptr;

    OsalThreadAttr attr;
    memset_s(&attr, sizeof(attr), 0, sizeof(attr));
    attr.detachFlag = 0; // not detach
    attr.policyFlag = 1;
    attr.policy = OSAL_THREAD_SCHED_RR;
    attr.priorityFlag = 1;
    attr.priority = 1; // 1-99
    attr.stackFlag = 1;
    attr.stackSize = 20480; // 20K

    int32_t ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, nullptr, &attr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    attr.stackSize = 1024; // 1k
    ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    attr.priority = 100; // 1-99
    ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    attr.policy = -1;
    ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    MOCKER(pthread_attr_init).stubs().will(returnValue(OSAL_EN_ERROR));
    ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();

    MOCKER(pthread_attr_setinheritsched).stubs().will(returnValue(OSAL_EN_ERROR));
    ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();

    MOCKER(pthread_attr_setschedpolicy).stubs().will(returnValue(OSAL_EN_ERROR));
    ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxJoinTask)
{
    OsalThread stThreadHandle;
    OsalUserBlock stFuncBlock;
    stFuncBlock.procFunc = UTtest_callback;
    stFuncBlock.pulArg = nullptr;
    pthread_create(&stThreadHandle, nullptr, stFuncBlock.procFunc, stFuncBlock.pulArg);
    MOCKER(pthread_join).stubs().will(returnValue(OSAL_EN_ERROR));
    int32_t ret = LinuxJoinTask(&stThreadHandle);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();
    ret = LinuxJoinTask(&stThreadHandle);
    ASSERT_EQ(OSAL_EN_OK, ret);
}

TEST_F(OSAL_LINUX_TEST, LinuxGetTickCount)
{
    OsalTimespec rts = LinuxGetTickCount();
    EXPECT_TRUE(rts.tv_nsec != 0);
}

TEST_F(OSAL_LINUX_TEST, LinuxGetFileSize)
{
    char* pathname = (CHAR*)"./llt/abl/msprof/ut/common/CMakeLists.txt";

    uint64_t length = 0;
    int32_t ret = LinuxGetFileSize(pathname, &length);
    ASSERT_EQ(-1, ret);
    printf("file size is %lld,\n", length);
    ret = LinuxGetFileSize(nullptr, &length);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    MOCKER(lstat).stubs().will(returnValue(-1));
    ret = LinuxGetFileSize(pathname, &length);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxGetDiskFreeSpace)
{
    char* pathname = (CHAR*)"/var/";
    struct statvfs buf;
    fsblkcnt_t total_size;
    fsblkcnt_t used_size;
    fsblkcnt_t avail_size;
    int error;
    OsalDiskSize dsize = {0};
    error = LinuxGetDiskFreeSpace(pathname, &dsize);
    printf("error =%d \n", error);
    EXPECT_TRUE(error == OSAL_EN_OK);
    printf("totalSize: %lld\n", dsize.totalSize);
    printf("availSize: %lld\n", dsize.availSize);
    printf("freeSize: %lld\n", dsize.freeSize);
    error = LinuxGetDiskFreeSpace(nullptr, &dsize);
    EXPECT_TRUE(error == OSAL_EN_INVALID_PARAM);

    MOCKER(statvfs).stubs().will(returnValue(-1));
    error = LinuxGetDiskFreeSpace(pathname, &dsize);
    ASSERT_EQ(OSAL_EN_ERROR, error);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxIsDir)
{
    char* pathname = (CHAR*)"./llt/abl/msprof/ut/common/CMakeLists.txt";
    int32_t ret = LinuxIsDir(pathname);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    pathname = (CHAR*)"./llt/abl/msprof/ut/common";
    ret = LinuxIsDir(pathname);
    ASSERT_EQ(-1, ret);

    ret = LinuxIsDir(nullptr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    MOCKER(lstat).stubs().will(returnValue(-1));
    ret = LinuxIsDir(pathname);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxDirName)
{
    char* path = "llt/abl/msprof/ut/common/";
    char* tmp = "llt/abl/msprof/ut";
    MOCKER(dirname).stubs().will(returnValue(tmp));
    char* dir = LinuxDirName(path);
    printf("dir=%s,dirname\n", dir);
    ASSERT_NE(nullptr, dir);

    MOCKER(basename).stubs().will(returnValue(tmp));
    char* base = LinuxBaseName(path);
    printf("base=%s,basename\n", base);
    ASSERT_NE(nullptr, base);

    dir = LinuxDirName(nullptr);
    ASSERT_EQ(nullptr, dir);
    dir = LinuxBaseName(nullptr);
    ASSERT_EQ(nullptr, dir);
}

TEST_F(OSAL_LINUX_TEST, LinuxMkdir)
{
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, LinuxMkdir(nullptr, 0755));

    CHAR newPath[256] = "./llt/abl/msprof/ut/common/mkdir";
    MOCKER(mkdir).stubs().will(returnValue(OSAL_EN_ERROR));
    int32_t ret = LinuxMkdir(newPath, 0755);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxChdir)
{
    char currentDir[OSAL_MAX_PATH] = "./";
    char targetDir[] = "/var/";
    int32_t ret = LinuxChdir(targetDir);
    ASSERT_EQ(OSAL_EN_ERROR, ret);

    ret = LinuxRealPath(nullptr, currentDir, OSAL_MAX_PATH);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);
    ret = LinuxRealPath("./", currentDir, OSAL_MAX_PATH);
    ASSERT_EQ(OSAL_EN_OK, ret);
}

int testFilter(const struct dirent* entry) { return entry->d_name[0] == 't'; }

TEST_F(OSAL_LINUX_TEST, LinuxScandir)
{
    OsalDirent** entryList;
    int count;
    int i;
    char testDir[64] = "./llt/abl/msprof/ut/common/";

    count = LinuxScandir(nullptr, &entryList, testFilter, alphasort);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, count);

    MOCKER(scandir).stubs().will(returnValue(OSAL_EN_ERROR));
    count = LinuxScandir(testDir, &entryList, testFilter, alphasort);
    ASSERT_EQ(OSAL_EN_ERROR, count);
    GlobalMockObject::reset();

    count = LinuxScandir(testDir, &entryList, testFilter, alphasort);

    printf("count is %d\n", count);
    for (i = 0; i < count; i++) {
        printf("%s\n", entryList[i]->d_name);
    }
}

TEST_F(OSAL_LINUX_TEST, LinuxGetCwd)
{
    int32_t ret = 0;
    char bufff[260];
    ret = LinuxGetCwd(bufff, sizeof(bufff));
    ASSERT_EQ(OSAL_EN_OK, ret);
    printf("current working directory : %s\n", bufff);

    ret = LinuxGetCwd(nullptr, 0);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    ret = LinuxGetCwd(bufff, 0);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
}

TEST_F(OSAL_LINUX_TEST, LinuxGetLocalTime)
{
    OsalTimeval tv;
    OsalTimezone tz;
    int32_t ret = LinuxGetTimeOfDay(&tv, &tz);
    ASSERT_EQ(OSAL_EN_OK, ret);
    OsalSystemTime st;

    printf("ret=%d\n", ret);
    printf("LinuxGetTimeOfDay tv_sec:%ld\n", tv.tv_sec);
    printf("LinuxGetTimeOfDay tv_usec:%d\n", tv.tv_usec);
    LinuxGetLocalTime(&st);
    printf("%d-%d-%d %d-%d-%d\n ", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);

    MOCKER(localtime_r).stubs().will(returnValue((struct tm*)nullptr));
    ret = LinuxGetLocalTime(&st);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();

    ret = LinuxGetTimeOfDay(nullptr, &tz);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);
}

TEST_F(OSAL_LINUX_TEST, LinuxSetCurrentThreadName)
{
    char threadName[] = "test-thread-name";
    MOCKER((int (*)(char*))prctl).stubs().will(returnValue(OSAL_EN_ERROR));
    int32_t ret = LinuxSetCurrentThreadName(threadName);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();

    ret = LinuxSetCurrentThreadName(nullptr);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);
}

TEST_F(OSAL_LINUX_TEST, LinuxGetOsName)
{
    char osName[OSAL_MIN_OS_NAME_SIZE] = {};
    int32_t ret = LinuxGetOsName(osName, OSAL_MIN_OS_NAME_SIZE);
    ASSERT_EQ(OSAL_EN_OK, ret);
    printf("osName is %s\n", osName);

    ret = LinuxGetOsName(nullptr, OSAL_MIN_OS_NAME_SIZE);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    MOCKER(gethostname).stubs().will(returnValue(-1));
    ret = LinuxGetOsName(osName, OSAL_MIN_OS_NAME_SIZE);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxGetOsVersion)
{
    char osVersionInfo[OSAL_MIN_OS_VERSION_SIZE] = {};
    int32_t ret = LinuxGetOsVersion(osVersionInfo, OSAL_MIN_OS_VERSION_SIZE);
    ASSERT_EQ(OSAL_EN_OK, ret);
    printf("osVersionInfo is %s\n", osVersionInfo);

    ret = ret = LinuxGetOsVersion(nullptr, OSAL_MIN_OS_VERSION_SIZE);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    MOCKER(uname).stubs().will(returnValue(-1));
    ret = LinuxGetOsVersion(osVersionInfo, OSAL_MIN_OS_VERSION_SIZE);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();

    MOCKER((int (*)(char*, long unsigned int, long unsigned int))snprintf_s).stubs().will(returnValue(-1));
    ret = LinuxGetOsVersion(osVersionInfo, OSAL_MIN_OS_VERSION_SIZE);
    ASSERT_EQ(OSAL_EN_ERROR, ret);
    GlobalMockObject::reset();
}

int32_t CpuInfoStrToIntStub(const char* str)
{
    if (str == NULL) {
        return 0;
    }

    errno = 0;
    char* endPtr = NULL;
    const int32_t decimalBase = 10;
    int64_t out = strtol(str, &endPtr, decimalBase);
    if (endPtr == str || *endPtr != '\0') {
        return 0;
    } else if ((out == LONG_MIN || out == LONG_MAX) && (errno == ERANGE)) {
        return 0;
    }

    if (out <= INT_MAX && out >= INT_MIN) {
        return (int32_t)out;
    } else {
        return 0;
    }
}

TEST_F(OSAL_LINUX_TEST, LinuxGetCpuInfo)
{
    OsalCpuDesc* desc = nullptr;
    int32_t count = 0;
    int32_t ret = 0;

    int32_t cnt = 1;
    ret = LinuxGetCpuInfo(nullptr, &cnt);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    ret = LinuxGetCpuInfo(&desc, &count);
    ASSERT_EQ(OSAL_EN_OK, ret);
    free(desc);

    GlobalMockObject::reset();
    char hisiVersion[100] = "CPU implementer: 0x48";
    char* stubChar = nullptr;
    MOCKER(fgets).stubs().will(returnValue(&hisiVersion[0])).then(returnValue(stubChar));
    MOCKER(uname).stubs().will(returnValue(OSAL_EN_OK));
    ret = LinuxGetCpuInfo(&desc, &count);
    free(desc);
    desc = NULL;
    ASSERT_EQ(OSAL_EN_OK, ret);
    GlobalMockObject::reset();

    ret = LinuxCpuInfoFree(nullptr, count);
    ASSERT_EQ(OSAL_EN_INVALID_PARAM, ret);

    EXPECT_EQ(CpuInfoStrToIntStub("-2147483648"), -2147483648);
    EXPECT_EQ(CpuInfoStrToIntStub("2147483647"), 2147483647);
    EXPECT_EQ(CpuInfoStrToIntStub("2147483648"), 0);
    EXPECT_EQ(CpuInfoStrToIntStub("-9223372036854775808"), 0);
    EXPECT_EQ(CpuInfoStrToIntStub("9223372036854775807"), 0);
    EXPECT_EQ(CpuInfoStrToIntStub(NULL), 0);
}

TEST_F(OSAL_LINUX_TEST, LinuxDlopen)
{
    MOCKER(dlopen).stubs().will(returnValue((void*)1));
    EXPECT_EQ(nullptr, LinuxDlopen(nullptr, 0));
    EXPECT_NE(nullptr, LinuxDlopen("test.so", RTLD_LAZY));

    MOCKER(dlsym).stubs().will(returnValue((void*)1));
    EXPECT_EQ(nullptr, LinuxDlsym(nullptr, nullptr));
    EXPECT_NE(nullptr, LinuxDlsym((void*)1, "test"));

    MOCKER(dlclose).stubs().will(returnValue(0));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxDlclose(nullptr));
    EXPECT_EQ(OSAL_EN_OK, LinuxDlclose((void*)1));

    char* ret = "test";
    MOCKER(dlerror).stubs().will(returnValue(ret));
    EXPECT_EQ(ret, LinuxDlerror());
}

TEST_F(OSAL_LINUX_TEST, LinuxGetOptLong)
{
    MOCKER(getopt_long).stubs().will(returnValue(0));
    int32_t longIndex = 0;
    char* argv[] = {"test"};
    char* opts = "";
    OsalStructOption options[0] = {};
    EXPECT_EQ(0, LinuxGetOptLong(0, argv, opts, options, &longIndex));
}

TEST_F(OSAL_LINUX_TEST, LinuxSleep_LongDuration)
{
    EXPECT_EQ(OSAL_EN_OK, LinuxSleep(OSAL_MAX_SLEEP_MILLSECOND_USING_USLEEP + 1));
}

TEST_F(OSAL_LINUX_TEST, LinuxCreateTaskWithThreadAttr_Success)
{
    OsalThread stThreadHandle;
    OsalUserBlock stFuncBlock;
    stFuncBlock.procFunc = UTtest_callback;
    stFuncBlock.pulArg = nullptr;

    OsalThreadAttr attr;
    (void)memset_s(&attr, sizeof(attr), 0, sizeof(attr));
    attr.detachFlag = 1;
    attr.policyFlag = 0;
    attr.priorityFlag = 0;
    attr.stackFlag = 0;

    int32_t ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    EXPECT_EQ(OSAL_EN_OK, ret);
    pthread_join(stThreadHandle, nullptr);
}

TEST_F(OSAL_LINUX_TEST, LinuxCreateTaskWithThreadAttr_StackAndDetach)
{
    OsalThread stThreadHandle;
    OsalUserBlock stFuncBlock;
    stFuncBlock.procFunc = UTtest_callback;
    stFuncBlock.pulArg = nullptr;

    OsalThreadAttr attr;
    (void)memset_s(&attr, sizeof(attr), 0, sizeof(attr));
    attr.detachFlag = 1;
    attr.policyFlag = 0;
    attr.priorityFlag = 0;
    attr.stackFlag = 1;
    attr.stackSize = OSAL_THREAD_MIN_STACK_SIZE;

    int32_t ret = LinuxCreateTaskWithThreadAttr(&stThreadHandle, &stFuncBlock, &attr);
    EXPECT_EQ(OSAL_EN_OK, ret);
    pthread_join(stThreadHandle, nullptr);
}

TEST_F(OSAL_LINUX_TEST, LinuxJoinTask_NullHandle) { EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxJoinTask(nullptr)); }

TEST_F(OSAL_LINUX_TEST, LinuxGetFileSize_Success)
{
    const CHAR* path = (CHAR*)"./test_osal_tmp_file.txt";
    FILE* fp = fopen(path, "w");
    ASSERT_NE(nullptr, fp);
    (void)fprintf(fp, "hello");
    (void)fclose(fp);

    uint64_t length = 0;
    int32_t ret = LinuxGetFileSize(path, &length);
    EXPECT_EQ(OSAL_EN_OK, ret);
    EXPECT_EQ(5u, length);
    (void)unlink(path);
}

TEST_F(OSAL_LINUX_TEST, LinuxIsDir_Success)
{
    const CHAR* dirPath = (CHAR*)"./test_osal_tmp_dir";
    (void)mkdir(dirPath, 0755);
    EXPECT_EQ(OSAL_EN_OK, LinuxIsDir(dirPath));
    (void)rmdir(dirPath);
}

TEST_F(OSAL_LINUX_TEST, LinuxAccess)
{
    const CHAR* path = (CHAR*)"./test_osal_access.txt";
    FILE* fp = fopen(path, "w");
    ASSERT_NE(nullptr, fp);
    (void)fclose(fp);

    EXPECT_EQ(OSAL_EN_OK, LinuxAccess(path));
    EXPECT_EQ(OSAL_EN_OK, LinuxAccess2(path, F_OK));
    EXPECT_EQ(OSAL_EN_ERROR, LinuxAccess("./nonexistent_file_xyz"));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxAccess(nullptr));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxAccess2(nullptr, F_OK));
    (void)unlink(path);
}

TEST_F(OSAL_LINUX_TEST, LinuxMkdir_Success)
{
    const CHAR* dirPath = (CHAR*)"./test_osal_mkdir_tmp";
    (void)rmdir(dirPath);
    int32_t ret = LinuxMkdir(dirPath, 0755);
    EXPECT_EQ(OSAL_EN_OK, ret);
    (void)rmdir(dirPath);
}

TEST_F(OSAL_LINUX_TEST, LinuxChmod)
{
    const CHAR* path = (CHAR*)"./test_osal_chmod.txt";
    FILE* fp = fopen(path, "w");
    ASSERT_NE(nullptr, fp);
    (void)fclose(fp);

    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxChmod(nullptr, 0755));
    (void)LinuxChmod(path, 0644);
    (void)unlink(path);
}

TEST_F(OSAL_LINUX_TEST, LinuxScandirFree)
{
    OsalDirent** entryList = (OsalDirent**)OsalMalloc(sizeof(OsalDirent*) * 2);
    ASSERT_NE(nullptr, entryList);
    entryList[0] = (OsalDirent*)OsalMalloc(sizeof(OsalDirent));
    entryList[1] = nullptr;
    LinuxScandirFree(entryList, 2);

    LinuxScandirFree(nullptr, 0);
    SUCCEED();
}

TEST_F(OSAL_LINUX_TEST, LinuxRmdir)
{
    const CHAR* dirPath = (CHAR*)"./test_osal_rmdir_tmp";
    (void)mkdir(dirPath, 0755);
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxRmdir(nullptr));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxRmdir("./nonexistent_dir_xyz"));
    EXPECT_EQ(OSAL_EN_OK, LinuxRmdir(dirPath));
}

TEST_F(OSAL_LINUX_TEST, LinuxUnlink)
{
    const CHAR* path = (CHAR*)"./test_osal_unlink.txt";
    FILE* fp = fopen(path, "w");
    ASSERT_NE(nullptr, fp);
    (void)fclose(fp);

    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxUnlink(nullptr));
    EXPECT_EQ(OSAL_EN_OK, LinuxUnlink(path));
    EXPECT_NE(OSAL_EN_OK, LinuxAccess(path));
}

TEST_F(OSAL_LINUX_TEST, LinuxRealPath_Error)
{
    char realPath[OSAL_MAX_PATH];
    EXPECT_EQ(OSAL_EN_ERROR, LinuxRealPath("./nonexistent_path_xyz", realPath, OSAL_MAX_PATH));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxRealPath("./", realPath, OSAL_MAX_PATH - 1));
}

TEST_F(OSAL_LINUX_TEST, LinuxGetErrorFormatMessage)
{
    char buf[256];
    EXPECT_EQ(nullptr, LinuxGetErrorFormatMessage(0, buf, sizeof(buf)));
}

TEST_F(OSAL_LINUX_TEST, LinuxStatGet) { EXPECT_EQ(OSAL_EN_ERROR, LinuxStatGet("./test.txt", nullptr)); }

TEST_F(OSAL_LINUX_TEST, LinuxDup) { EXPECT_EQ(OSAL_EN_ERROR, LinuxDup(0, 1)); }

TEST_F(OSAL_LINUX_TEST, LinuxOpen_Close_Write)
{
    const CHAR* path = (CHAR*)"./test_osal_open.txt";
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxOpen(nullptr, O_RDONLY, 0644));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxOpen(path, -1, 0644));

    int32_t fd = LinuxOpen(path, O_WRONLY | O_CREAT | O_TRUNC, S_IRUSR | S_IWUSR);
    EXPECT_GE(fd, 0);

    const char* data = "hello world";
    OsalSsize written = LinuxWrite(fd, (VOID*)data, strlen(data));
    EXPECT_EQ((OsalSsize)strlen(data), written);

    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxWrite(-1, (VOID*)data, strlen(data)));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxWrite(fd, nullptr, 10));

    EXPECT_EQ(OSAL_EN_OK, LinuxClose(fd));
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxClose(-1));
    (void)unlink(path);
}

TEST_F(OSAL_LINUX_TEST, LinuxOpen_InvalidMode)
{
    const CHAR* path = (CHAR*)"./test_osal_open_invalid.txt";
    EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxOpen(path, O_WRONLY | O_CREAT, 0));
}

TEST_F(OSAL_LINUX_TEST, LinuxSetCurrentThreadName_Success)
{
    const char threadName[] = "ut-thread";
    MOCKER((int (*)(char*))prctl).stubs().will(returnValue(0));
    int32_t ret = LinuxSetCurrentThreadName(threadName);
    EXPECT_EQ(OSAL_EN_OK, ret);
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxGetOptInd_Arg)
{
    EXPECT_GE(LinuxGetOptInd(), 0);
    EXPECT_EQ(nullptr, LinuxGetOptArg());
}

TEST_F(OSAL_LINUX_TEST, LinuxDlclose_Error)
{
    MOCKER(dlclose).stubs().will(returnValue(-1));
    EXPECT_EQ(OSAL_EN_ERROR, LinuxDlclose((void*)0x1));
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, LinuxGetLocalTime_Null) { EXPECT_EQ(OSAL_EN_INVALID_PARAM, LinuxGetLocalTime(nullptr)); }

TEST_F(OSAL_LINUX_TEST, LinuxGetTimeOfDay_Error)
{
    MOCKER(gettimeofday).stubs().will(returnValue(-1));
    OsalTimeval tv;
    EXPECT_EQ(OSAL_EN_ERROR, LinuxGetTimeOfDay(&tv, nullptr));
    GlobalMockObject::reset();
}

TEST_F(OSAL_LINUX_TEST, OsalMalloc)
{
    EXPECT_EQ(nullptr, OsalMalloc(0));
    void* ptr = OsalMalloc(100);
    ASSERT_NE(nullptr, ptr);
    OsalFree(ptr);
    OsalFree(nullptr);
}

TEST_F(OSAL_LINUX_TEST, OsalCalloc)
{
    void* ptr = OsalCalloc(100);
    ASSERT_NE(nullptr, ptr);
    for (int i = 0; i < 100; i++) {
        EXPECT_EQ(0, ((char*)ptr)[i]);
    }
    OsalFree(ptr);
    EXPECT_EQ(nullptr, OsalCalloc(0));
}

TEST_F(OSAL_LINUX_TEST, OsalConstFree)
{
    void* ptr = OsalMalloc(50);
    ASSERT_NE(nullptr, ptr);
    OsalConstFree(ptr);
    OsalConstFree(nullptr);
}
