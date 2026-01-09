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


class TestChunkList:
    """测试切片列表"""
    
    def test_list_chunks(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试列出切片"""
        chunks, total, doc_info = client.chunk.list(kb_id, doc_id)
        assert isinstance(chunks, list)
        assert total >= 0
    
    def test_list_with_keywords(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试使用关键词搜索切片"""
        chunks, total, _ = client.chunk.list(kb_id, doc_id, keywords="test")
        assert isinstance(chunks, list)


class TestChunkGet:
    """测试切片查询"""
    
    def test_get_existing_chunk(self, client: PowerRAGClient, kb_id: str, doc_id: str, chunk_id: str):
        """测试获取存在的切片"""
        chunk = client.chunk.get(kb_id, doc_id, chunk_id)
        assert chunk["id"] == chunk_id
    
    def test_get_nonexistent_chunk(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试获取不存在的切片"""
        with pytest.raises(Exception) as exc_info:
            client.chunk.get(kb_id, doc_id, "nonexistent_id")
        assert "not found" in str(exc_info.value).lower()


class TestChunkCreate:
    """测试切片创建"""
    
    def test_create_chunk(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试创建切片"""
        chunk = client.chunk.create(
            kb_id,
            doc_id,
            content="Test chunk content",
            important_keywords=["test", "chunk"]
        )
        assert chunk["id"] is not None
        assert chunk["content"] == "Test chunk content"
        
        # 清理
        client.chunk.delete(kb_id, doc_id, [chunk["id"]])
    
    def test_create_chunk_with_questions(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试创建带问题的切片"""
        chunk = client.chunk.create(
            kb_id,
            doc_id,
            content="Test content",
            questions=["What is this?", "How does it work?"]
        )
        assert len(chunk.get("questions", [])) == 2
        
        # 清理
        client.chunk.delete(kb_id, doc_id, [chunk["id"]])


class TestChunkUpdate:
    """测试切片更新"""
    
    def test_update_content(self, client: PowerRAGClient, kb_id: str, doc_id: str, chunk_id: str):
        """测试更新切片内容"""
        updated_chunk = client.chunk.update(
            kb_id,
            doc_id,
            chunk_id,
            content="Updated content"
        )
        assert updated_chunk["content"] == "Updated content"
    
    def test_update_keywords(self, client: PowerRAGClient, kb_id: str, doc_id: str, chunk_id: str):
        """测试更新关键词"""
        updated_chunk = client.chunk.update(
            kb_id,
            doc_id,
            chunk_id,
            important_keywords=["new", "keywords"]
        )
        assert updated_chunk.get("important_keywords") == ["new", "keywords"]


class TestChunkDelete:
    """测试切片删除"""
    
    def test_delete_single_chunk(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试删除单个切片"""
        chunk = client.chunk.create(kb_id, doc_id, content="To be deleted")
        chunk_id = chunk["id"]
        
        client.chunk.delete(kb_id, doc_id, [chunk_id])
        
        with pytest.raises(Exception):
            client.chunk.get(kb_id, doc_id, chunk_id)
    
    def test_delete_multiple_chunks(self, client: PowerRAGClient, kb_id: str, doc_id: str):
        """测试批量删除切片"""
        chunk_ids = []
        for i in range(3):
            chunk = client.chunk.create(kb_id, doc_id, content=f"Chunk {i}")
            chunk_ids.append(chunk["id"])
        
        client.chunk.delete(kb_id, doc_id, chunk_ids)
        
        for chunk_id in chunk_ids:
            with pytest.raises(Exception):
                client.chunk.get(kb_id, doc_id, chunk_id)


class TestChunkSplitText:
    """测试文本切片"""
    
    def test_split_text(self, client: PowerRAGClient):
        """测试文本切片"""
        markdown_text = """
# 第一章

这是第一章的内容...

## 1.1 小节

这是小节内容...
"""
        result = client.chunk.split_text(
            text=markdown_text,
            parser_id="title",
            config={"title_level": 2, "chunk_token_num": 256}
        )
        assert result.get("total_chunks", 0) > 0 or len(result.get("chunks", [])) > 0
    
    def test_split_text_with_config(self, client: PowerRAGClient):
        """测试使用配置的文本切片"""
        text = "This is a test document with multiple paragraphs."
        result = client.chunk.split_text(
            text=text,
            parser_id="naive",
            config={"chunk_token_num": 128}
        )
        assert "chunks" in result or "total_chunks" in result

