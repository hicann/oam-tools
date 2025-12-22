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
#include "profile_drv_user_stub.h"
#include "mmpa_api.h"

int prof_drv_start(unsigned int device_id, unsigned int channel_id, struct prof_start_para *start_para) {
    return PROF_OK;
}

/*
   函数原型	int prof_stop(unsigned int device_id, unsigned int channel_id)

   函数功能	触发Prof采集结束;
   输入说明	dev_id, Device 的ID
                channel_id, 通道ID(0--63)
   输出说明
   返回值说明	0：表示成功;  非0：获取失败;
   使用说明
   注意事项
 */
int prof_stop(unsigned int device_id, unsigned int channel_id) {
    return PROF_OK;
}
/*
   函数原型	int prof_channel_read(unsigned int device_id, unsigned int channel_id, char *out_buf,
		      unsigned int buf_size)

   函数功能	读采集Profile信息
   输入说明	int device_id             设备编号
                int channel_id            通道ID(0--63)
                char *out_buf                存储read的Profile信息
                unsigned int buf_size		 存储需要读取的profile的长度
   输出说明
   返回值说明	0：成功  正数：可读的buffer长度 -1:获取失败
   使用说明
   注意事项
 */
int prof_channel_read(unsigned int device_id, unsigned int channel_id, char *out_buf,
          unsigned int buf_size) {
    return PROF_OK;
}

int prof_channel_poll(struct prof_poll_info *out_buf, int num, int timeout) {
#ifdef MSPROF_C
   return 1;
#else
   return PROF_OK;
#endif
}

int prof_drv_get_channels(unsigned int device_id, channel_list_t *channels) {
    channels->chip_type = 1910;
    channels->channel_num = PROF_CHANNEL_NUM_MAX;
    for (int i = 0; i < PROF_CHANNEL_NUM_MAX; i++) {
        channel_info info = {0};
        info.channel_id = i;
        channels->channel[i] = info;
    }
    return PROF_OK;
}
