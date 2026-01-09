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

from typing import Optional, Dict, Any
from .raptor import RAPTORTaskInfo


class RAPTORManager:
    """RAPTOR管理模块"""
    
    def __init__(self, client):
        """
        初始化RAPTOR管理模块
        
        Args:
            client: PowerRAG客户端实例
        """
        self.client = client
    
    def build(self, kb_id: str) -> RAPTORTaskInfo:
        """
        构建RAPTOR（异步）
        
        注意：RAPTOR的配置参数从知识库的 `parser_config.raptor` 中读取。
        需要在创建或更新知识库时设置这些配置参数。
        
        Args:
            kb_id: 知识库ID
        
        Returns:
            任务信息，包含raptor_task_id
        
        Raises:
            Exception: API调用失败
        """
        # 使用SDK的RAPTOR接口
        url = f"/datasets/{kb_id}/run_raptor"
        res = self.client.post(url)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Build RAPTOR failed"))
        
        return res_json.get("data", {})
    
    def get_status(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """
        获取RAPTOR构建状态
        
        Args:
            kb_id: 知识库ID
        
        Returns:
            任务状态信息，如果不存在则返回None
        
        Raises:
            Exception: API调用失败
        """
        # 使用SDK的RAPTOR接口
        url = f"/datasets/{kb_id}/trace_raptor"
        res = self.client.get(url)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Get RAPTOR status failed"))
        
        data = res_json.get("data", {})
        return data if data else None
        

