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


class TestKnowledgeBaseCreate:
    """测试知识库创建"""
    
    def test_create_with_name_only(self, client: PowerRAGClient):
        """测试仅使用名称创建知识库"""
        kb = client.knowledge_base.create(name="test_kb")
        assert kb["id"] is not None
        assert kb["name"] == "test_kb"
        assert kb["chunk_method"] == "naive"
        assert kb["permission"] == "me"
        
        # 清理
        client.knowledge_base.delete([kb["id"]])
    
    def test_create_with_all_fields(self, client: PowerRAGClient):
        """测试使用所有字段创建知识库"""
        # 注意：pagerank 字段只能在更新时设置，创建时不能设置
        kb = client.knowledge_base.create(
            name="test_kb_full",
            description="Test description",
            embedding_model="BAAI/bge-small-en-v1.5@Builtin",
            permission="team",
            chunk_method="book",
            parser_config={"chunk_token_num": 256}
        )
        assert kb["name"] == "test_kb_full"
        assert kb["description"] == "Test description"
        assert kb["chunk_method"] == "book"
        assert kb["permission"] == "team"
        
        # 清理
        client.knowledge_base.delete([kb["id"]])
    
    def test_create_duplicate_name(self, client: PowerRAGClient):
        """测试创建重复名称的知识库"""
        name = "duplicate_test"
        kb1 = client.knowledge_base.create(name=name)
        
        try:
            # 某些系统可能允许重复名称，所以这里只检查是否创建成功
            kb2 = client.knowledge_base.create(name=name)
            # 如果创建成功，清理两个知识库
            client.knowledge_base.delete([kb1["id"], kb2["id"]])
        except Exception as e:
            # 如果抛出异常，说明不允许重复名称
            assert "already exists" in str(e).lower() or "duplicate" in str(e).lower()
            # 清理第一个知识库
            client.knowledge_base.delete([kb1["id"]])


class TestKnowledgeBaseGet:
    """测试知识库查询"""
    
    def test_get_existing_kb(self, client: PowerRAGClient):
        """测试获取存在的知识库"""
        kb = client.knowledge_base.create(name="get_test")
        try:
            fetched_kb = client.knowledge_base.get(kb["id"])
            assert fetched_kb["id"] == kb["id"]
            assert fetched_kb["name"] == kb["name"]
        finally:
            client.knowledge_base.delete([kb["id"]])
    
    def test_get_nonexistent_kb(self, client: PowerRAGClient):
        """测试获取不存在的知识库"""
        # 使用有效的UUID格式但不存在于系统中的ID
        # UUID v1格式：32位十六进制字符串
        nonexistent_id = "a" * 32  # 32个字符的十六进制字符串
        with pytest.raises(Exception) as exc_info:
            client.knowledge_base.get(nonexistent_id)
        # 检查错误信息中是否包含 "not found" 或 "invalid uuid"
        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg or "invalid uuid" in error_msg


class TestKnowledgeBaseList:
    """测试知识库列表"""
    
    def test_list_all(self, client: PowerRAGClient):
        """测试列出所有知识库"""
        kb_ids = []
        try:
            for i in range(3):
                kb = client.knowledge_base.create(name=f"list_test_{i}")
                kb_ids.append(kb["id"])
            
            kbs, total = client.knowledge_base.list()
            assert len(kbs) > 0
            assert total >= 3
        finally:
            if kb_ids:
                client.knowledge_base.delete(kb_ids)
    
    def test_list_with_filter(self, client: PowerRAGClient):
        """测试使用过滤器列出知识库"""
        name = "filter_test"
        kb = client.knowledge_base.create(name=name)
        try:
            kbs, total = client.knowledge_base.list(name=name)
            assert len(kbs) >= 1
            assert any(kb_item["name"] == name for kb_item in kbs)
        finally:
            client.knowledge_base.delete([kb["id"]])
    
    def test_list_with_pagination(self, client: PowerRAGClient):
        """测试分页列出知识库"""
        kb_ids = []
        try:
            for i in range(5):
                kb = client.knowledge_base.create(name=f"page_test_{i}")
                kb_ids.append(kb["id"])
            
            kbs_page1, total = client.knowledge_base.list(page=1, page_size=2)
            assert len(kbs_page1) <= 2
            assert total >= 5
        finally:
            if kb_ids:
                client.knowledge_base.delete(kb_ids)


class TestKnowledgeBaseUpdate:
    """测试知识库更新"""
    
    def test_update_name(self, client: PowerRAGClient):
        """测试更新知识库名称"""
        kb = client.knowledge_base.create(name="update_test")
        try:
            updated_kb = client.knowledge_base.update(kb["id"], name="updated_name")
            assert updated_kb["name"] == "updated_name"
        finally:
            client.knowledge_base.delete([kb["id"]])
    
    def test_update_multiple_fields(self, client: PowerRAGClient):
        """测试更新多个字段"""
        kb = client.knowledge_base.create(name="multi_update_test")
        try:
            updated_kb = client.knowledge_base.update(
                kb["id"],
                name="multi_updated",
                description="Updated description",
                permission="team"
            )
            assert updated_kb["name"] == "multi_updated"
            assert updated_kb["description"] == "Updated description"
            assert updated_kb["permission"] == "team"
        finally:
            client.knowledge_base.delete([kb["id"]])


class TestKnowledgeBaseDelete:
    """测试知识库删除"""
    
    def test_delete_single_kb(self, client: PowerRAGClient):
        """测试删除单个知识库"""
        kb = client.knowledge_base.create(name="delete_test")
        client.knowledge_base.delete([kb["id"]])
        
        with pytest.raises(Exception):
            client.knowledge_base.get(kb["id"])
    
    def test_delete_multiple_kbs(self, client: PowerRAGClient):
        """测试批量删除知识库"""
        kb_ids = []
        for i in range(3):
            kb = client.knowledge_base.create(name=f"batch_delete_{i}")
            kb_ids.append(kb["id"])
        
        client.knowledge_base.delete(kb_ids)
        
        for kb_id in kb_ids:
            with pytest.raises(Exception):
                client.knowledge_base.get(kb_id)

