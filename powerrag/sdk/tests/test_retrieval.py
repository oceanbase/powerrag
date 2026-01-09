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
from powerrag.sdk import PowerRAGClient


class TestRetrievalSearch:
    """测试检索"""
    
    def test_basic_search(self, client: PowerRAGClient, kb_id: str):
        """测试基本检索"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题"
        )
        assert "chunks" in result
        assert "total" in result
        assert isinstance(result["chunks"], list)
    
    def test_search_with_pagination(self, client: PowerRAGClient, kb_id: str):
        """测试分页检索"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题",
            page=1,
            page_size=10
        )
        assert len(result["chunks"]) <= 10
    
    def test_search_with_similarity_threshold(self, client: PowerRAGClient, kb_id: str):
        """测试相似度阈值"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题",
            similarity_threshold=0.5
        )
        # 验证所有结果的相似度都大于等于阈值（如果有结果）
        for chunk in result["chunks"]:
            assert chunk.get("similarity", 0) >= 0.5
    
    def test_search_with_document_filter(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试文档过滤"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题",
            document_ids=[doc_id]
        )
        # 验证所有结果都来自指定的文档（如果有结果）
        for chunk in result["chunks"]:
            assert chunk["document_id"] == doc_id
    
    def test_search_with_keyword(self, client: PowerRAGClient, kb_id: str):
        """测试关键词增强"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题",
            keyword=True
        )
        assert "chunks" in result
    
    def test_search_with_kg(self, client: PowerRAGClient, kb_id: str):
        """测试知识图谱检索"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题",
            use_kg=True
        )
        assert "chunks" in result
    
    def test_search_with_highlight(self, client: PowerRAGClient, kb_id: str):
        """测试高亮"""
        result = client.retrieval.search(
            kb_ids=[kb_id],
            question="测试问题",
            highlight=True
        )
        assert "chunks" in result


class TestRetrievalTest:
    """测试检索测试方法"""
    
    def test_retrieval_test(self, client: PowerRAGClient, kb_id: str):
        """测试检索测试方法"""
        result = client.retrieval.test(
            kb_ids=[kb_id],
            question="测试问题"
        )
        assert "chunks" in result
        assert "total" in result

