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

from typing import TypedDict, Optional, List, Dict, Any


class ExtractionResult(TypedDict, total=False):
    """抽取结果类型定义"""
    doc_id: Optional[str]
    doc_name: Optional[str]
    extractor_type: str
    data: Dict[str, Any]  # 抽取的数据（entities/keywords/summary等）
    metadata: Dict[str, Any]


class EntityInfo(TypedDict, total=False):
    """实体信息"""
    text: str
    type: str
    start: int
    end: int
    confidence: Optional[float]


class KeywordInfo(TypedDict, total=False):
    """关键词信息"""
    keyword: str
    score: float
    frequency: Optional[int]


class StructExtractTaskInfo(TypedDict, total=False):
    """结构化抽取任务信息"""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]]

