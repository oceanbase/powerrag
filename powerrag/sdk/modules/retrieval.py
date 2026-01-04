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


class RetrievalChunk(TypedDict, total=False):
    """检索结果切片"""
    id: str
    content: str
    document_id: str
    dataset_id: str
    similarity: float
    important_keywords: List[str]
    questions: List[str]
    docnm_kwd: str
    image_id: Optional[str]
    available: bool
    positions: List[List[int]]


class RetrievalResult(TypedDict, total=False):
    """检索结果"""
    total: int
    chunks: List[RetrievalChunk]
    doc_aggs: Dict[str, Any]  # 文档聚合信息
    labels: Optional[Dict[str, Any]]  # 标签信息

