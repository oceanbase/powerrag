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
from .knowledge_base import KnowledgeBaseInfo


class KnowledgeBaseManager:
    """知识库管理模块"""
    
    def __init__(self, client):
        """
        初始化知识库管理模块
        
        Args:
            client: PowerRAG客户端实例
        """
        self.client = client
    
    def create(
        self,
        name: str,
        description: Optional[str] = None,
        avatar: Optional[str] = None,
        embedding_model: Optional[str] = None,
        permission: str = "me",
        chunk_method: str = "naive",
        parser_config: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeBaseInfo:
        """
        创建知识库
        
        Args:
            name: 知识库名称（必填）
            description: 描述（可选）
            avatar: 头像，base64编码（可选）
            embedding_model: 嵌入模型名称（可选，默认使用租户默认模型）
            permission: 权限，'me' 或 'team'（默认'me'）
            chunk_method: 切片方法（默认'naive'）
            parser_config: 解析器配置（可选）
        
        Returns:
            创建的知识库信息
        
        Raises:
            Exception: API调用失败
        
        Note:
            pagerank 字段只能在更新时设置，创建时不能设置
        """
        payload = {
            "name": name,
        }
        
        if description is not None:
            payload["description"] = description
        if avatar is not None:
            payload["avatar"] = avatar
        if embedding_model is not None:
            payload["embedding_model"] = embedding_model
        if permission:
            payload["permission"] = permission
        if chunk_method:
            payload["chunk_method"] = chunk_method
        if parser_config is not None:
            payload["parser_config"] = parser_config
        
        res = self.client.post("/datasets", json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Create knowledge base failed"))
        
        return res_json.get("data", {})
    
    def get(self, kb_id: str) -> KnowledgeBaseInfo:
        """
        获取知识库
        
        Args:
            kb_id: 知识库ID
        
        Returns:
            知识库信息
        
        Raises:
            Exception: API调用失败或知识库不存在
        """
        kbs, _ = self.list(id=kb_id, page_size=1)
        if not kbs:
            raise Exception(f"Knowledge base '{kb_id}' not found")
        return kbs[0]
    
    def list(
        self,
        id: Optional[str] = None,
        name: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
        orderby: str = "create_time",
        desc: bool = True,
    ) -> tuple[List[KnowledgeBaseInfo], int]:
        """
        列出知识库
        
        Args:
            id: 知识库ID（可选，用于精确查询）
            name: 知识库名称（可选，用于模糊查询）
            page: 页码，默认1
            page_size: 每页数量，默认30
            orderby: 排序字段，默认create_time
            desc: 是否降序，默认True
        
        Returns:
            (知识库列表, 总数)
        
        Raises:
            Exception: API调用失败
        """
        params = {
            "page": page,
            "page_size": page_size,
            "orderby": orderby,
            "desc": desc,
        }
        
        if id:
            params["id"] = id
        if name:
            params["name"] = name
        
        res = self.client.get("/datasets", params=params)
        res_json = res.json()
        
        if res_json.get("code") == 0:
            # API返回的字段名是 total_datasets，不是 total
            return res_json.get("data", []), res_json.get("total_datasets", 0)
        
        raise Exception(res_json.get("message", "List knowledge bases failed"))
    
    def update(
        self,
        kb_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        avatar: Optional[str] = None,
        embedding_model: Optional[str] = None,
        permission: Optional[str] = None,
        chunk_method: Optional[str] = None,
        parser_config: Optional[Dict[str, Any]] = None,
        pagerank: Optional[int] = None,
    ) -> KnowledgeBaseInfo:
        """
        更新知识库
        
        Args:
            kb_id: 知识库ID
            name: 知识库名称（可选）
            description: 描述（可选）
            avatar: 头像（可选）
            embedding_model: 嵌入模型（可选）
            permission: 权限（可选）
            chunk_method: 切片方法（可选）
            parser_config: 解析器配置（可选）
            pagerank: 页面排名（可选）
        
        Returns:
            更新后的知识库信息
        
        Raises:
            Exception: API调用失败
        """
        # 字段名映射：SDK字段 -> API字段
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if avatar is not None:
            update_data["avatar"] = avatar
        if embedding_model is not None:
            update_data["embd_id"] = embedding_model
        if permission is not None:
            update_data["permission"] = permission
        if chunk_method is not None:
            update_data["parser_id"] = chunk_method
        if parser_config is not None:
            update_data["parser_config"] = parser_config
        if pagerank is not None:
            update_data["pagerank"] = pagerank
        
        if not update_data:
            raise Exception("No fields to update")
        
        res = self.client.put(f"/datasets/{kb_id}", json=update_data)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Update knowledge base failed"))
        
        return res_json.get("data", {})
    
    def delete(self, ids: Optional[List[str]] = None) -> None:
        """
        删除知识库
        
        Args:
            ids: 知识库ID列表，如果为None则删除所有知识库
        
        Raises:
            Exception: API调用失败
        """
        payload = {"ids": ids}
        res = self.client.delete("/datasets", json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Delete knowledge bases failed"))

