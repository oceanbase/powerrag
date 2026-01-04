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


class TestExtractFromDocument:
    """测试从文档抽取"""
    
    def test_extract_entities(self, client: PowerRAGClient, doc_id: str):
        """测试抽取实体"""
        result = client.extraction.extract_from_document(
            doc_id,
            extractor_type="entity",
            config={"entity_types": ["PERSON", "ORG"]}
        )
        assert result["extractor_type"] == "entity"
        assert "data" in result
    
    def test_extract_keywords(self, client: PowerRAGClient, doc_id: str):
        """测试抽取关键词"""
        result = client.extraction.extract_from_document(
            doc_id,
            extractor_type="keyword",
            config={"max_keywords": 20}
        )
        assert result["extractor_type"] == "keyword"
        assert "data" in result
    
    def test_extract_summary(self, client: PowerRAGClient, doc_id: str):
        """测试抽取摘要"""
        result = client.extraction.extract_from_document(
            doc_id,
            extractor_type="summary",
            config={"max_length": 200}
        )
        assert result["extractor_type"] == "summary"
        assert "data" in result


class TestExtractFromText:
    """测试从文本抽取"""
    
    def test_extract_entities_from_text(self, client: PowerRAGClient):
        """测试从文本抽取实体"""
        text = "John works at Microsoft in Seattle."
        result = client.extraction.extract_from_text(
            text,
            extractor_type="entity",
            config={"entity_types": ["PERSON", "ORG", "LOCATION"]}
        )
        assert result["extractor_type"] == "entity"
        assert "data" in result
    
    def test_extract_keywords_from_text(self, client: PowerRAGClient):
        """测试从文本抽取关键词"""
        text = "This is a test document about artificial intelligence and machine learning."
        result = client.extraction.extract_from_text(
            text,
            extractor_type="keyword",
            config={"max_keywords": 10}
        )
        assert result["extractor_type"] == "keyword"
        assert "data" in result


class TestExtractBatch:
    """测试批量抽取"""
    
    def test_extract_batch(self, client: PowerRAGClient, doc_ids: list):
        """测试批量抽取"""
        results = client.extraction.extract_batch(
            doc_ids,
            extractor_type="entity"
        )
        assert len(results) == len(doc_ids)
        assert all("success" in r for r in results)


class TestStructExtract:
    """测试结构化抽取"""
    
    def test_struct_extract(self, client: PowerRAGClient):
        """测试结构化抽取"""
        text = "John attended a conference in New York on January 1, 2024."
        examples = [
            {
                "text": "John attended a conference in New York on January 1, 2024.",
                "extractions": [
                    {"extraction_class": "name", "extraction_text": "John"},
                    {"extraction_class": "location", "extraction_text": "New York"},
                    {"extraction_class": "date", "extraction_text": "January 1, 2024"}
                ]
            }
        ]
        
        task_info = client.extraction.struct_extract(
            text_or_documents=text,
            prompt_description="Extract names, locations, and dates from the text.",
            examples=examples
        )
        assert "task_id" in task_info
    
    def test_get_struct_extract_status(self, client: PowerRAGClient):
        """测试获取结构化抽取任务状态"""
        text = "Test text for extraction."
        examples = [
            {
                "text": "Test text for extraction.",
                "extractions": []
            }
        ]
        
        task_info = client.extraction.struct_extract(
            text_or_documents=text,
            prompt_description="Extract information.",
            examples=examples
        )
        task_id = task_info["task_id"]
        
        status = client.extraction.get_struct_extract_status(task_id)
        assert "status" in status or "task_id" in status

