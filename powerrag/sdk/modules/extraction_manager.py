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

from typing import Optional, List, Dict, Any, Union
from .extraction import ExtractionResult, StructExtractTaskInfo


class ExtractionManager:
    """抽取管理模块"""
    
    def __init__(self, client):
        """
        初始化抽取管理模块
        
        Args:
            client: PowerRAG客户端实例
        """
        self.client = client
    
    def extract_from_document(
        self,
        doc_id: str,
        extractor_type: str = "entity",
        config: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """
        从文档抽取信息
        
        Args:
            doc_id: 文档ID
            extractor_type: 抽取类型，'entity'、'keyword' 或 'summary'
            config: 抽取配置（可选）
                - entity: {"entity_types": ["PERSON", "ORG"], "use_regex": True, "use_llm": False}
                - keyword: {"max_keywords": 20, "min_word_length": 3}
                - summary: {"max_length": 200, "min_length": 50}
        
        Returns:
            抽取结果
        
        Raises:
            Exception: API调用失败
        """
        payload = {
            "doc_id": doc_id,
            "extractor_type": extractor_type,
        }
        
        if config:
            payload["config"] = config
        
        url = "/powerrag/extract"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Extract from document failed"))
        
        return res_json.get("data", {})
    
    def extract_from_text(
        self,
        text: str,
        extractor_type: str = "entity",
        config: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """
        从文本抽取信息
        
        Args:
            text: 文本内容
            extractor_type: 抽取类型，'entity'、'keyword' 或 'summary'
            config: 抽取配置（可选）
        
        Returns:
            抽取结果
        
        Raises:
            Exception: API调用失败
        """
        payload = {
            "text": text,
            "extractor_type": extractor_type,
        }
        
        if config:
            payload["config"] = config
        
        url = "/powerrag/extract/text"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Extract from text failed"))
        
        return res_json.get("data", {})
    
    def extract_batch(
        self,
        doc_ids: List[str],
        extractor_type: str = "entity",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        批量从文档抽取信息
        
        Args:
            doc_ids: 文档ID列表
            extractor_type: 抽取类型
            config: 抽取配置（可选）
        
        Returns:
            抽取结果列表，每个结果包含success字段
        
        Raises:
            Exception: API调用失败
        """
        payload = {
            "doc_ids": doc_ids,
            "extractor_type": extractor_type,
        }
        
        if config:
            payload["config"] = config
        
        url = "/powerrag/extract/batch"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Batch extract failed"))
        
        return res_json.get("data", [])
    
    def struct_extract(
        self,
        text_or_documents: Union[str, List[Dict[str, str]]],
        prompt_description: str,
        examples: List[Dict[str, Any]],
        fetch_urls: bool = False,
        max_char_buffer: int = 1000,
        temperature: Optional[float] = None,
        extraction_passes: int = 1,
        additional_context: Optional[str] = None,
        prompt_validation_level: str = "WARNING",
        prompt_validation_strict: bool = False,
        resolver_params: Optional[Dict[str, Any]] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> StructExtractTaskInfo:
        """
        结构化抽取（LangExtract）
        
        Args:
            text_or_documents: 文本内容或文档列表
            prompt_description: 抽取提示描述
            examples: 示例列表，每个示例包含text和extractions
            fetch_urls: 是否获取URL（默认False）
            max_char_buffer: 最大字符缓冲区（默认1000）
            temperature: 温度参数（可选）
            extraction_passes: 抽取轮数（默认1）
            additional_context: 额外上下文（可选）
            prompt_validation_level: 提示验证级别（默认"WARNING"）
            prompt_validation_strict: 是否严格验证（默认False）
            resolver_params: 解析器参数（可选）
            model_parameters: 模型参数（可选）
            timeout: 超时时间（可选）
        
        Returns:
            任务信息，包含task_id
        
        Raises:
            Exception: API调用失败
        """
        payload = {
            "text_or_documents": text_or_documents,
            "prompt_description": prompt_description,
            "examples": examples,
            "fetch_urls": fetch_urls,
            "max_char_buffer": max_char_buffer,
            "extraction_passes": extraction_passes,
            "prompt_validation_level": prompt_validation_level,
            "prompt_validation_strict": prompt_validation_strict,
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if additional_context:
            payload["additional_context"] = additional_context
        if resolver_params:
            payload["resolver_params"] = resolver_params
        if model_parameters:
            payload["model_parameters"] = model_parameters
        if timeout:
            payload["timeout"] = timeout
        
        url = "/powerrag/struct_extract/submit"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Struct extract failed"))
        
        return res_json.get("data", {})
    
    def get_struct_extract_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取结构化抽取任务状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务状态信息
        
        Raises:
            Exception: API调用失败
        """
        url = f"/powerrag/struct_extract/status/{task_id}"
        res = self.client.get(url)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Get struct extract status failed"))
        
        return res_json.get("data", {})

