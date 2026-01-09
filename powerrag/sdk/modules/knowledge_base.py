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

from typing import TypedDict, Optional, Dict, Any


class KnowledgeBaseInfo(TypedDict, total=False):
    """知识库信息类型定义"""
    id: str
    name: str
    avatar: Optional[str]
    tenant_id: Optional[str]
    description: Optional[str]
    embedding_model: str
    permission: str
    document_count: int
    chunk_count: int
    chunk_method: str
    parser_config: Optional[Dict[str, Any]]
    pagerank: int

