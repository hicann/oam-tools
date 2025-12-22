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

#include "dump_proto_to_json.h"
#include <stdlib.h>
#include <iostream>
#include <fstream>
#include <google/protobuf/util/json_util.h>
#include "proto/proto_parse/dump_data.pb.h"

static int32_t SaveToFile(std::string &jsonData, std::string path)
{
    auto index = path.find_last_of("/");
    std::string filename = path.substr(index + 1, -1);
    std::string directory = path.substr(0, index);
    char *canonicalPath = realpath(directory.c_str(), nullptr);
    if (canonicalPath == nullptr) {
        std::cerr << "Failed to get canonical path, " << strerror(errno) << std::endl;
        return -1;
    }
    std::string jsonPath = std::string(canonicalPath) + "/" + filename;
    free(canonicalPath);
    std::ofstream jsonFile(jsonPath);
    if (!jsonFile.is_open()) {
        std::cerr << "Failed to open json file, path:" << path << ", " << strerror(errno) << std::endl;
        return -1;
    }
    jsonFile << jsonData;
    jsonFile.close();
    return 0;
}

int32_t ParseDumpProtoToJson(const char *data, size_t dataLength, const char *path)
{
    if (data == nullptr || path == nullptr) {
        std::cerr << "Input param check failed, data:" << data << ", path:" << path << std::endl;
        return -1;
    }
    if (dataLength < sizeof(uint64_t)) {
        std::cerr << "Input param check failed, dataLength must be greater than " << sizeof(uint64_t)
                  << ", get dataLength: " << dataLength << std::endl;
        return -1;
    }
    uint64_t headLength = *(reinterpret_cast<const uint64_t*>(data));
    if (dataLength < headLength + sizeof(uint64_t)) {
        std::cerr << "Input param check failed, dataLength needs to be greater than " << headLength + sizeof(uint64_t)
                  << ", get dataLength: " << dataLength << std::endl;
        return -1;
    }
    std::string protoData(data + sizeof(uint64_t), headLength);

    toolkit::dumpdata::DumpData dumpData;
    bool ret = dumpData.ParseFromString(protoData);
    if (!ret) {
        std::cerr << "Failed to parse proto data" << std::endl;
        return -1;
    }
    google::protobuf::util::JsonPrintOptions options;
    options.always_print_primitive_fields = true;
    options.always_print_enums_as_ints = true;
    options.preserve_proto_field_names = true;
    std::string jsonData;
    auto status = google::protobuf::util::MessageToJsonString(dumpData, &jsonData, options);
    if (!status.ok()) {
        std::cerr << "Failed to convert proto data to json." << std::endl;
        return -1;
    }

    return SaveToFile(jsonData, path);
}
