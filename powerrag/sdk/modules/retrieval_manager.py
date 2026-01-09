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

from typing import Optional, List, Dict, Any
from .retrieval import RetrievalResult


class RetrievalManager:
    """检索管理模块"""
    
    def __init__(self, client):
        """
        初始化检索管理模块
        
        Args:
            client: PowerRAG客户端实例
        """
        self.client = client
    
    def search(
        self,
        kb_ids: List[str],
        question: str,
        document_ids: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 30,
        similarity_threshold: float = 0.2,
        vector_similarity_weight: float = 0.3,
        top_k: int = 1024,
        keyword: bool = False,
        use_kg: bool = False,
        rerank_id: Optional[str] = None,
        highlight: bool = True,
        cross_languages: Optional[List[str]] = None,
        metadata_condition: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        检索（向量/关键词/混合）
        
        Args:
            kb_ids: 知识库ID列表
            question: 查询问题
            document_ids: 文档ID列表（可选，用于过滤）
            page: 页码，默认1
            page_size: 每页数量，默认30
            similarity_threshold: 相似度阈值，默认0.2
            vector_similarity_weight: 向量相似度权重（混合检索时使用），默认0.3
            top_k: 最大返回数量，默认1024
            keyword: 是否使用关键词增强，默认False
            use_kg: 是否使用知识图谱检索，默认False
            rerank_id: 重排序模型ID（可选）
            highlight: 是否高亮匹配内容，默认True
            cross_languages: 跨语言列表（可选）
            metadata_condition: 元数据过滤条件（可选）
        
        Returns:
            检索结果，包含chunks列表和total数量
        
        Raises:
            Exception: API调用失败
        """
        payload = {
            "dataset_ids": kb_ids,
            "question": question,
            "page": page,
            "page_size": page_size,
            "similarity_threshold": similarity_threshold,
            "vector_similarity_weight": vector_similarity_weight,
            "top_k": top_k,
            "keyword": keyword,
            "use_kg": use_kg,
            "highlight": highlight,
        }
        
        if document_ids:
            payload["document_ids"] = document_ids
        if rerank_id:
            payload["rerank_id"] = rerank_id
        if cross_languages:
            payload["cross_languages"] = cross_languages
        if metadata_condition:
            payload["metadata_condition"] = metadata_condition
        
        url = "/retrieval"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Search failed"))
        
        return res_json.get("data", {"total": 0, "chunks": []})
    
    def test(
        self,
        kb_ids: List[str],
        question: str,
        document_ids: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 30,
        similarity_threshold: float = 0.2,
        vector_similarity_weight: float = 0.3,
        top_k: int = 1024,
        keyword: bool = False,
        use_kg: bool = False,
        rerank_id: Optional[str] = None,
        highlight: bool = True,
    ) -> RetrievalResult:
        """
        检索测试（与search方法相同，用于测试场景）
        
        Args:
            kb_ids: 知识库ID列表
            question: 查询问题
            document_ids: 文档ID列表（可选）
            page: 页码，默认1
            page_size: 每页数量，默认30
            similarity_threshold: 相似度阈值，默认0.2
            vector_similarity_weight: 向量相似度权重，默认0.3
            top_k: 最大返回数量，默认1024
            keyword: 是否使用关键词增强，默认False
            use_kg: 是否使用知识图谱检索，默认False
            rerank_id: 重排序模型ID（可选）
            highlight: 是否高亮匹配内容，默认True
        
        Returns:
            检索结果
        
        Raises:
            Exception: API调用失败
        """
        return self.search(
            kb_ids=kb_ids,
            question=question,
            document_ids=document_ids,
            page=page,
            page_size=page_size,
            similarity_threshold=similarity_threshold,
            vector_similarity_weight=vector_similarity_weight,
            top_k=top_k,
            keyword=keyword,
            use_kg=use_kg,
            rerank_id=rerank_id,
            highlight=highlight,
        )

