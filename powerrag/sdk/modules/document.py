#
#  Copyright 2025 The OceanBase Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from typing import TypedDict, Optional, Dict, Any, List


class DocumentInfo(TypedDict, total=False):
    """文档信息类型定义"""
    id: str
    name: str
    dataset_id: str  # 知识库ID
    chunk_count: int
    token_count: int
    chunk_method: str
    run: str  # UNSTART, RUNNING, CANCEL, DONE, FAIL
    progress: float  # 0.0-1.0
    progress_msg: Optional[str]
    type: str  # 文件类型
    size: int  # 文件大小（字节）
    suffix: str  # 文件后缀
    thumbnail: Optional[str]  # 缩略图
    create_time: int  # 创建时间戳
    update_time: int  # 更新时间戳
    meta_fields: Optional[Dict[str, Any]]  # 元数据字段
    enabled: bool  # 是否启用
    parser_config: Optional[Dict[str, Any]]  # 解析器配置

