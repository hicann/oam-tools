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

#ifndef VARIABLE_BLOCK_BUFFER_H
#define VARIABLE_BLOCK_BUFFER_H

#include <atomic>
#include <string>
#include "securec.h"
#include "logger/msprof_dlog.h"
#include "prof_api.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace queue {
const size_t VARIABLE_BLOCK_BUFF_CAPACITY      = 262144; // 256K length queue
const size_t VARIABLE_BLOCK_BUFFER_MAX_CYCLES  = 2048; // min length is 256, 65536 / 256 = 256
const uint32_t VARIABLE_BLOCK_PUSH_WAIT_TIME   = 1;
const std::string VARIABLE_BLOCK_BUFFER_NAME   = "VariableBlockBuffer";

/**
 * @brief Customized buffer using for report api, compact or additional data
 */
template <class T>
class VariableBlockBuffer {
public:
    explicit VariableBlockBuffer(size_t maxCycles = VARIABLE_BLOCK_BUFFER_MAX_CYCLES)
        : capacity_(VARIABLE_BLOCK_BUFF_CAPACITY),
          maxCycles_(maxCycles),
          mask_(0),
          readIndex_(0),
          writeIndex_(0),
          lastWriteIndex_(0),
          isInited_(false),
          name_(VARIABLE_BLOCK_BUFFER_NAME),
          dataBuffer_(nullptr)
    {}

    virtual ~VariableBlockBuffer()
    {
        UnInit();
    }

public:
    /**
    * @brief Init variable block buffer
    * @param [in] name: the name of variable block buffer
    * @param [in] capacity: the length of varibale block buffer, which need to be 2^n and larger than VARIABLE_BLOCK_BUFF_CAPACITY
    * @return true: success, false: failed
    */
    bool Init(const std::string &name, size_t capacity = VARIABLE_BLOCK_BUFF_CAPACITY)
    {
        if (isInited_) {
            MSPROF_LOGW("Repeat init block buffer, capacity: %zu, buffer name: %s", 
                      capacity, name.c_str());
            return true;
        }

        if (capacity < VARIABLE_BLOCK_BUFF_CAPACITY) {
            MSPROF_LOGE("Failed to init block buffer, min capacity is %d, capacity: %zu, buffer name: %s", VARIABLE_BLOCK_BUFF_CAPACITY, capacity, name.c_str());
            return false;
        }

        capacity_ = capacity;
        name_ = name;
        mask_ = capacity - 1;
        
        // allocate data buffer
        dataBuffer_ = new (std::nothrow) T[capacity];
        if (dataBuffer_ == nullptr) {
            MSPROF_LOGE("Failed to new block buffer, capacity: %zu, buffer name: %s", 
                      capacity, name.c_str());
            return false;
        }

        isInited_ = true;
        MSPROF_EVENT("Init variable block buffer successfully, capacity: %zu, buffer name: %s", 
                   capacity_, name_.c_str());
        return true;
    }
    /**
    * @brief UnInit variable block buffer
    */
    void UnInit()
    {
        if (isInited_) {
            isInited_ = false;
            size_t currReadCursor = readIndex_.load(std::memory_order_relaxed);
            size_t currWriteCursor = writeIndex_.load(std::memory_order_relaxed);
            if ((currWriteCursor - currReadCursor) >= capacity_) {
                MSPROF_LOGE("Variable block buffer overflow, [%s] capacity: %zu, read count: %zu, "
                          "write count: %zu", name_.c_str(), capacity_, currReadCursor, currWriteCursor);
            }

            if (dataBuffer_ != nullptr) {
                delete[] dataBuffer_;
                dataBuffer_ = nullptr;
            }

            MSPROF_EVENT("total_size_report [%s] read count: %zu, write count: %zu",
                       name_.c_str(), readIndex_.exchange(0), writeIndex_.exchange(0));
            lastWriteIndex_.exchange(0);
        }
    }

    /**
    * @brief Batch push data into variable block buffer
    * @param [in] data: the data need to be pushed
    * @param [in] dataSize: the size of data, which need to be aligned with sizeof(T)
    * @return MSPROF_ERROR_NONE: success, MSPROF_ERROR_UNINITIALIZE: uninitialized
    */
    int32_t BatchPush(const T *data, size_t dataSize)
    {
        if (!isInited_) {
            MSPROF_LOGW("Variable block buffer %s is not initialized.", name_.c_str());
            return MSPROF_ERROR_UNINITIALIZE;
        }

        size_t currWriteCursor = 0;
        size_t currReadCursor = 0;
        size_t cycles = 0;
        size_t availableSpace = 0;
        
        do {
            cycles++;
            if (cycles >= maxCycles_) {
                MSPROF_LOGW("Variable Block cycle overflow, buffer name: %s, buffer capacity: %u", 
                          name_.c_str(), capacity_);
                return MSPROF_ERROR_NONE;
            }

            currWriteCursor = lastWriteIndex_.load();
            currReadCursor = readIndex_.load();
            
            // check whether there is sufficient space
            availableSpace = (currWriteCursor >= currReadCursor) ? 
                                  (capacity_ - currWriteCursor + currReadCursor) : 
                                  (currReadCursor - currWriteCursor);
            
            if (availableSpace < dataSize) {
                MSPROF_LOGW("Variable block buffer about to overflow, buffer name: %s, buffer capacity: %u, "
                          "currWriteCursor: %zu, currReadCursor: %zu, dataSize: %zu", 
                          name_.c_str(), capacity_, currWriteCursor, currReadCursor, dataSize);
                usleep(VARIABLE_BLOCK_PUSH_WAIT_TIME);
            }
        } while (availableSpace < dataSize ||
                !lastWriteIndex_.compare_exchange_strong(currWriteCursor, currWriteCursor + dataSize));

        // 处理环形缓冲区
        size_t writePos = currWriteCursor & mask_;
        
        // 写入数据
        if (writePos + dataSize <= capacity_) {
            // 数据不跨边界
            (void)memcpy_s(dataBuffer_ + writePos, dataSize, data, dataSize);
        } else {
            // 数据跨边界
            size_t endSize = capacity_ - writePos;
            size_t frontSize = dataSize - endSize;
            (void)memcpy_s(dataBuffer_ + writePos, endSize, data, endSize);
            (void)memcpy_s(dataBuffer_, frontSize, data + endSize, frontSize);
        }

        writeIndex_.fetch_add(dataSize);
        return MSPROF_ERROR_NONE;
    }
    /**
    * @brief Batch pop data from variable block buffer
    * @param [out] popSize: pop size of data, which is writeIndex - readIndex
    * @param [in] popForce: whether force pop data when data size is not enough
    */
    void *BatchPop(size_t &popSize)
    {
        if (!isInited_ || popSize == 0) {
            return nullptr;
        }

        size_t currReadCursor = readIndex_.load(std::memory_order_relaxed);
        size_t currWriteCursor = writeIndex_.load(std::memory_order_relaxed);
        // 检查是否有数据可读
        if ((currReadCursor & mask_) == (currWriteCursor & mask_)) {
            return nullptr;
        }

        size_t availSize = currWriteCursor > currReadCursor ? currWriteCursor - currReadCursor : currWriteCursor + capacity_ - currReadCursor;

        size_t currIndex = currReadCursor & mask_;
        popSize = availSize;

        return dataBuffer_ + currIndex;
    }
    /**
    * @brief update read index and clear data
    * @param [in] popPtr: pop start ptr
    * @param [in] popSize: pop size of data
    */
    void BatchPopBufferIndexShift(void *popPtr, const size_t popSize)
    {
        if (popPtr == nullptr || popSize == 0) {
            return;
        }

        (void)memset_s(popPtr, popSize, 0, popSize);
        readIndex_.fetch_add(popSize);
    }
    /**
    * @brief Get used size of variable block buffer
    * @return size_t: used size of variable block buffer
    */
    size_t GetUsedSize()
    {
        size_t readIndex = readIndex_.load(std::memory_order_relaxed);
        size_t writeIndex = writeIndex_.load(std::memory_order_relaxed);
        if (readIndex > writeIndex) {
            return ((std::numeric_limits<size_t>::max() - readIndex + writeIndex) % capacity_);
        }

        return ((writeIndex - readIndex) % capacity_);
    }

private:
    size_t capacity_;
    size_t maxCycles_;
    size_t mask_;
    std::atomic<size_t> readIndex_;
    std::atomic<size_t> writeIndex_;
    std::atomic<size_t> lastWriteIndex_;
    volatile bool isInited_;
    std::string name_;
    T *dataBuffer_;
    // BlockMeta *metas_;  // 新增元数据缓冲区
};
}
}
}
}

#endif
