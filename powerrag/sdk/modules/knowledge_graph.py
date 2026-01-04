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


class KnowledgeGraphNode(TypedDict, total=False):
    """知识图谱节点"""
    id: str
    label: str
    pagerank: Optional[float]
    properties: Optional[Dict[str, Any]]


class KnowledgeGraphEdge(TypedDict, total=False):
    """知识图谱边"""
    source: str
    target: str
    weight: Optional[float]
    label: Optional[str]
    properties: Optional[Dict[str, Any]]


class KnowledgeGraphData(TypedDict, total=False):
    """知识图谱数据"""
    graph: Dict[str, Any]  # 包含nodes和edges
    mind_map: Dict[str, Any]


class KnowledgeGraphTaskInfo(TypedDict, total=False):
    """知识图谱任务信息"""
    graphrag_task_id: str
    status: Optional[str]
    progress: Optional[float]
    progress_msg: Optional[str]
    begin_at: Optional[str]
    create_time: Optional[int]
    update_time: Optional[int]

