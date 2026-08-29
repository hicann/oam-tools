/*
 * Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

#include <gtest/gtest.h>
#include <cstdint>
#include <cstring>

extern "C" {
int32_t ParseDumpProtoToJson(const char *data, size_t dataLength, const char *path);
}

class TestDumpProtoToJson : public ::testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override {}
};

TEST_F(TestDumpProtoToJson, NullDataReturnsMinusOne) {
    int32_t result = ParseDumpProtoToJson(nullptr, 10, "/tmp/out.json");
    EXPECT_EQ(result, -1);
}

TEST_F(TestDumpProtoToJson, NullPathReturnsMinusOne) {
    const char data[] = "test data";
    int32_t result = ParseDumpProtoToJson(data, sizeof(data), nullptr);
    EXPECT_EQ(result, -1);
}

TEST_F(TestDumpProtoToJson, DataLengthLessThanUint64ReturnsMinusOne) {
    const char data[] = "abc";
    int32_t result = ParseDumpProtoToJson(data, 1, "/tmp/out.json");
    EXPECT_EQ(result, -1);
}

TEST_F(TestDumpProtoToJson, DataLengthLessThanHeadLengthPlusUint64ReturnsMinusOne) {
    uint64_t headLength = 100;
    char data[sizeof(uint64_t) + 1];
    (void)memcpy_s(data, sizeof(data), &headLength, sizeof(uint64_t));
    int32_t result = ParseDumpProtoToJson(data, sizeof(uint64_t) + 1, "/tmp/out.json");
    EXPECT_EQ(result, -1);
}
