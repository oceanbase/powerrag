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

import pytest
import time
from powerrag.sdk import PowerRAGClient


class TestKnowledgeGraphBuild:
    """测试知识图谱构建"""
    
    def test_build_knowledge_graph(self, client: PowerRAGClient, kb_with_docs: str):
        """测试构建知识图谱"""
        task_info = client.knowledge_graph.build(kb_with_docs)
        assert "graphrag_task_id" in task_info
    
    def test_build_knowledge_graph_already_running(self, client: PowerRAGClient, kb_with_docs: str):
        """测试构建知识图谱时任务已在运行"""
        # 先启动一个任务
        client.knowledge_graph.build(kb_with_docs)
        
        # 再次启动可能会失败或返回已有任务
        try:
            task_info = client.knowledge_graph.build(kb_with_docs)
            # 如果成功，说明系统允许重复构建
            assert "graphrag_task_id" in task_info
        except Exception as e:
            # 如果失败，应该是因为任务已在运行
            assert "already running" in str(e).lower() or "running" in str(e).lower()


class TestKnowledgeGraphGet:
    """测试知识图谱查询"""
    
    def test_get_knowledge_graph(self, client: PowerRAGClient, kb_with_docs: str):
        """测试获取知识图谱"""
        kg_data = client.knowledge_graph.get(kb_with_docs)
        assert "graph" in kg_data
        assert "mind_map" in kg_data
    
    def test_get_knowledge_graph_empty(self, client: PowerRAGClient, kb_with_docs: str):
        """测试获取空的知识图谱"""
        # 确保没有知识图谱数据
        try:
            client.knowledge_graph.delete(kb_with_docs)
        except Exception:
            pass
        
        kg_data = client.knowledge_graph.get(kb_with_docs)
        assert kg_data["graph"] == {}
        assert kg_data["mind_map"] == {}


class TestKnowledgeGraphStatus:
    """测试知识图谱状态查询"""
    
    def test_get_status(self, client: PowerRAGClient, kb_with_docs: str):
        """测试获取知识图谱状态"""
        # 先构建
        task_info = client.knowledge_graph.build(kb_with_docs)
        
        # 查询状态
        status = client.knowledge_graph.get_status(kb_with_docs)
        assert status is not None
        assert "progress" in status
    
    def test_get_status_not_exists(self, client: PowerRAGClient, kb_with_docs: str):
        """测试获取不存在的知识图谱状态"""
        # 确保没有运行的任务 - 只在存在时删除
        try:
            if client.knowledge_graph.get_status(kb_with_docs) is not None:
                client.knowledge_graph.delete(kb_with_docs)
        except Exception:
            pass
        
        status = client.knowledge_graph.get_status(kb_with_docs)
        assert status is None