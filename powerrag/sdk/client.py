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

import requests
from typing import Optional, Dict, Any

from .modules.knowledge_base_manager import KnowledgeBaseManager
from .modules.document_manager import DocumentManager
from .modules.chunk_manager import ChunkManager
from .modules.extraction_manager import ExtractionManager
from .modules.raptor_manager import RAPTORManager
from .modules.knowledge_graph_manager import KnowledgeGraphManager
from .modules.retrieval_manager import RetrievalManager


class PowerRAGClient:
    """PowerRAG SDK 主客户端"""
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:9380", version: str = "v1"):
        """
        初始化客户端
        
        Args:
            api_key: API密钥
            base_url: 服务地址
            version: API版本，默认v1
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/{version}"
        self.authorization_header = {"Authorization": f"Bearer {self.api_key}"}
        
        # 初始化各个管理模块
        self.knowledge_base = KnowledgeBaseManager(self)
        self.document = DocumentManager(self)
        self.chunk = ChunkManager(self)
        self.extraction = ExtractionManager(self)
        self.raptor = RAPTORManager(self)
        self.knowledge_graph = KnowledgeGraphManager(self)
        self.retrieval = RetrievalManager(self)
    
    def post(self, url: str, json=None, files=None, data=None, stream=False):
        """
        POST请求
        
        Args:
            url: 请求URL
            json: JSON数据
            files: 文件数据
            data: 表单数据
            stream: 是否流式传输
        
        Returns:
            Response对象
        """
        headers = self.authorization_header.copy()
        
        # 如果有文件上传，不设置Content-Type，让requests自动设置
        if files:
            res = requests.post(
                url=self.api_url + url,
                json=json,
                files=files,
                data=data,
                headers=headers,
                stream=stream
            )
        else:
            if json:
                headers["Content-Type"] = "application/json"
            res = requests.post(
                url=self.api_url + url,
                json=json,
                data=data,
                headers=headers,
                stream=stream
            )
        return res
    
    def get(self, url: str, params=None, stream=False):
        """
        GET请求
        
        Args:
            url: 请求URL
            params: 查询参数
            stream: 是否流式传输
        
        Returns:
            Response对象
        """
        res = requests.get(
            url=self.api_url + url,
            params=params,
            headers=self.authorization_header,
            stream=stream
        )
        return res
    
    def put(self, url: str, json=None):
        """
        PUT请求
        
        Args:
            url: 请求URL
            json: JSON数据
        
        Returns:
            Response对象
        """
        headers = self.authorization_header.copy()
        headers["Content-Type"] = "application/json"
        res = requests.put(
            url=self.api_url + url,
            json=json,
            headers=headers
        )
        return res
    
    def delete(self, url: str, json=None, params=None):
        """
        DELETE请求
        
        Args:
            url: 请求URL
            json: JSON数据
            params: 查询参数
        
        Returns:
            Response对象
        """
        headers = self.authorization_header.copy()
        if json:
            headers["Content-Type"] = "application/json"
        res = requests.delete(
            url=self.api_url + url,
            json=json,
            params=params,
            headers=headers
        )
        return res

