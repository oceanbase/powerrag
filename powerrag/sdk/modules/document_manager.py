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
from pathlib import Path
from .document import DocumentInfo


class DocumentManager:
    """文档管理模块"""
    
    def __init__(self, client):
        """
        初始化文档管理模块
        
        Args:
            client: PowerRAG客户端实例
        """
        self.client = client
    
    def upload(
        self,
        kb_id: str,
        file_paths: Union[str, List[str]],
        parent_path: Optional[str] = None,
    ) -> List[DocumentInfo]:
        """
        上传文档到知识库
        
        Args:
            kb_id: 知识库ID
            file_paths: 文件路径（单个文件或文件列表）
            parent_path: 父路径（可选，用于嵌套文件夹）
        
        Returns:
            文档信息列表
        
        Raises:
            Exception: API调用失败
        """
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        
        files = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(path, "rb") as f:
                files.append(("file", (path.name, f.read())))
        
        form_data = {}
        if parent_path:
            form_data["parent_path"] = parent_path
        
        url = f"/datasets/{kb_id}/documents"
        res = self.client.post(url, json=None, files=files, data=form_data)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Upload documents failed"))
        
        return res_json.get("data", [])
    
    def upload_from_url(
        self,
        kb_id: str,
        url: str,
        name: str,
    ) -> bool:
        """
        从URL上传文档到知识库
        
        Args:
            kb_id: 知识库ID
            url: 文档URL
            name: 文档名称
        
        Returns:
            是否成功
        
        Raises:
            Exception: API调用失败
        """
        form_data = {
            "kb_id": kb_id,
            "name": name,
            "url": url,
        }
        
        res = self.client.post("/document/web_crawl", json=None, data=form_data)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Upload from URL failed"))
        
        return res_json.get("data", False)
    
    def list(
        self,
        kb_id: str,
        id: Optional[str] = None,
        name: Optional[str] = None,
        keywords: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
        orderby: str = "create_time",
        desc: bool = True,
        create_time_from: int = 0,
        create_time_to: int = 0,
        suffix: Optional[List[str]] = None,
        run: Optional[List[str]] = None,
    ) -> tuple[List[DocumentInfo], int]:
        """
        列出知识库中的文档
        
        Args:
            kb_id: 知识库ID
            id: 文档ID（可选）
            name: 文档名称（可选）
            keywords: 关键词搜索（可选）
            page: 页码，默认1
            page_size: 每页数量，默认30
            orderby: 排序字段，默认create_time
            desc: 是否降序，默认True
            create_time_from: 创建时间起始（时间戳）
            create_time_to: 创建时间结束（时间戳）
            suffix: 文件后缀过滤（可选）
            run: 运行状态过滤（可选，UNSTART/RUNNING/CANCEL/DONE/FAIL）
        
        Returns:
            (文档列表, 总数)
        
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
        if keywords:
            params["keywords"] = keywords
        if create_time_from:
            params["create_time_from"] = create_time_from
        if create_time_to:
            params["create_time_to"] = create_time_to
        if suffix:
            params["suffix"] = suffix
        if run:
            params["run"] = run
        
        url = f"/datasets/{kb_id}/documents"
        res = self.client.get(url, params=params)
        res_json = res.json()
        
        if res_json.get("code") == 0:
            data = res_json.get("data", {})
            return data.get("docs", []), data.get("total", 0)
        
        raise Exception(res_json.get("message", "List documents failed"))
    
    def get(self, kb_id: str, doc_id: str) -> DocumentInfo:
        """
        获取文档信息
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
        
        Returns:
            文档信息
        
        Raises:
            Exception: API调用失败或文档不存在
        """
        docs, _ = self.list(kb_id, id=doc_id, page_size=1)
        if not docs:
            raise Exception(f"Document '{doc_id}' not found")
        return docs[0]
    
    def update(
        self,
        kb_id: str,
        doc_id: str,
        name: Optional[str] = None,
        meta_fields: Optional[Dict[str, Any]] = None,
        chunk_method: Optional[str] = None,
        parser_config: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None,
    ) -> DocumentInfo:
        """
        更新文档
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            name: 文档名称（可选）
            meta_fields: 元数据字段（可选）
            chunk_method: 切片方法（可选）
            parser_config: 解析器配置（可选）
            enabled: 是否启用（可选）
        
        Returns:
            更新后的文档信息
        
        Raises:
            Exception: API调用失败
        """
        update_data = {}
        
        if name is not None:
            update_data["name"] = name
        if meta_fields is not None:
            update_data["meta_fields"] = meta_fields
        if chunk_method is not None:
            update_data["chunk_method"] = chunk_method
        if parser_config is not None:
            update_data["parser_config"] = parser_config
        if enabled is not None:
            update_data["enabled"] = enabled
        
        if not update_data:
            raise Exception("No fields to update")
        
        url = f"/datasets/{kb_id}/documents/{doc_id}"
        res = self.client.put(url, json=update_data)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Update document failed"))
        
        return res_json.get("data", {})
    
    def rename(self, kb_id: str, doc_id: str, new_name: str) -> DocumentInfo:
        """
        重命名文档
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            new_name: 新名称
        
        Returns:
            更新后的文档信息
        
        Raises:
            Exception: API调用失败
        """
        return self.update(kb_id, doc_id, name=new_name)
    
    def set_meta(self, kb_id: str, doc_id: str, meta_fields: Dict[str, Any]) -> DocumentInfo:
        """
        设置文档元数据
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            meta_fields: 元数据字段字典
        
        Returns:
            更新后的文档信息
        
        Raises:
            Exception: API调用失败
        """
        return self.update(kb_id, doc_id, meta_fields=meta_fields)
    
    def delete(self, kb_id: str, doc_ids: Optional[List[str]] = None) -> None:
        """
        删除文档
        
        Args:
            kb_id: 知识库ID
            doc_ids: 文档ID列表，如果为None则删除所有文档
        
        Raises:
            Exception: API调用失败
        """
        payload = {"ids": doc_ids}
        url = f"/datasets/{kb_id}/documents"
        res = self.client.delete(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Delete documents failed"))
    
    def download(self, kb_id: str, doc_id: str, save_path: Optional[str] = None) -> Union[bytes, str]:
        """
        下载文档
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            save_path: 保存路径（可选），如果提供则保存到文件，否则返回字节流
        
        Returns:
            如果提供save_path则返回文件路径，否则返回文件字节流
        
        Raises:
            Exception: API调用失败
        """
        url = f"/datasets/{kb_id}/documents/{doc_id}"
        res = self.client.get(url, stream=True)
        
        if res.status_code != 200:
            res_json = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
            raise Exception(res_json.get("message", "Download document failed"))
        
        file_content = res.content
        
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(file_content)
            return save_path
        
        return file_content
    
    def parse_to_chunk(
        self,
        kb_id: str,
        doc_ids: List[str],
        wait: bool = True,
        delete_existing: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> Union[List[Dict[str, Any]], str]:
        """
        解析文档为切片
        
        Args:
            kb_id: 知识库ID
            doc_ids: 文档ID列表
            wait: 是否等待解析完成（默认True）
            delete_existing: 是否删除已存在的切片（默认False）
            config: 解析配置（可选）
        
        Returns:
            如果wait=True，返回解析结果列表；如果wait=False，返回任务ID
        
        Raises:
            Exception: API调用失败
        """
        payload = {
            "document_ids": doc_ids,
        }
        
        if delete_existing:
            payload["delete_existing"] = True
        if config:
            payload["config"] = config
        
        url = f"/datasets/{kb_id}/chunks"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Parse documents failed"))
        
        if wait:
            return self._wait_for_parse(kb_id, doc_ids)
        
        return res_json.get("data", {}).get("task_id", "")
    
    def parse_to_md_async(
        self,
        doc_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        异步解析文档为 Markdown（不切分）
        
        提交异步解析任务，立即返回任务 ID。
        适用于大文档或需要长时间处理的场景。
        
        支持的文件格式:
        - PDF (.pdf)
        - Office 文档 (.doc, .docx, .ppt, .pptx)
        - 图片 (.jpg, .png)
        - HTML (.html, .htm)
        
        Args:
            doc_id: 文档ID
            config: 解析配置（可选）
                - layout_recognize: 布局识别引擎 (mineru 或 dots_ocr，默认 mineru)
                - enable_ocr: 是否启用 OCR (默认 False)
                - enable_formula: 是否识别公式 (默认 False)
                - enable_table: 是否识别表格 (默认 True)
                - from_page: 起始页（仅 PDF，默认 0）
                - to_page: 结束页（仅 PDF，默认 100000）
        
        Returns:
            task_id: 任务ID，用于查询任务状态和结果
        
        Raises:
            Exception: API调用失败
        
        Example:
            >>> # 提交异步任务
            >>> task_id = client.document.parse_to_md_async(
            ...     doc_id="doc_123",
            ...     config={"layout_recognize": "mineru"}
            ... )
            >>> print(f"Task ID: {task_id}")
            
            >>> # 查询任务状态
            >>> status = client.document.get_parse_to_md_status(task_id)
            >>> if status["status"] == "success":
            ...     print(f"Markdown: {status['result']['markdown']}")
        """
        payload = {
            "doc_id": doc_id,
        }
        if config:
            payload["config"] = config
        
        url = "/powerrag/parse_to_md/async"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Submit parse_to_md task failed"))
        
        return res_json.get("data", {}).get("task_id", "")
    
    def get_parse_to_md_status(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """
        查询 parse_to_md 异步任务状态
        
        Args:
            task_id: 任务ID（由 parse_to_md_async 返回）
        
        Returns:
            任务状态字典:
            {
                "task_id": "...",
                "status": "pending|processing|success|failed|not_found",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "result": {  # 仅当 status="success" 时存在
                    "doc_id": "...",
                    "doc_name": "...",
                    "markdown": "...",
                    "markdown_length": 5000,
                    "images": {...},
                    "total_images": 2
                },
                "error": "..."  # 仅当 status="failed" 时存在
            }
        
        Raises:
            Exception: API调用失败
        
        Example:
            >>> status = client.document.get_parse_to_md_status(task_id)
            >>> print(f"Status: {status['status']}")
            >>> 
            >>> if status["status"] == "success":
            ...     result = status["result"]
            ...     print(f"Markdown length: {result['markdown_length']}")
            >>> elif status["status"] == "failed":
            ...     print(f"Error: {status['error']}")
            >>> elif status["status"] in ["pending", "processing"]:
            ...     print("Task is still running...")
        """
        url = f"/powerrag/parse_to_md/status/{task_id}"
        res = self.client.get(url)
        res_json = res.json()
        
        # For 404, still return the data (with status="not_found")
        if res_json.get("code") == 404:
            return res_json.get("data", {"task_id": task_id, "status": "not_found"})
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Get task status failed"))
        
        return res_json.get("data", {})
    
    def wait_for_parse_to_md(
        self,
        task_id: str,
        timeout: int = 300,
        interval: float = 2.0,
    ) -> Dict[str, Any]:
        """
        等待 parse_to_md 异步任务完成
        
        轮询任务状态直到完成（成功或失败）或超时。
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒），默认 300 秒（5 分钟）
            interval: 轮询间隔（秒），默认 2 秒
        
        Returns:
            任务最终状态（同 get_parse_to_md_status）
        
        Raises:
            TimeoutError: 超时
            Exception: 任务失败或 API 调用失败
        
        Example:
            >>> task_id = client.document.parse_to_md_async(doc_id)
            >>> result = client.document.wait_for_parse_to_md(task_id, timeout=600)
            >>> print(f"Markdown: {result['result']['markdown']}")
        """
        import time
        
        start_time = time.time()
        terminal_states = {"success", "failed", "not_found"}
        
        while True:
            status = self.get_parse_to_md_status(task_id)
            
            if status["status"] in terminal_states:
                if status["status"] == "failed":
                    raise Exception(f"Task failed: {status.get('error', 'Unknown error')}")
                elif status["status"] == "not_found":
                    raise Exception(f"Task not found: {task_id}")
                return status
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
            
            # Sleep before next poll
            time.sleep(interval)
    
    def parse_to_md(
        self,
        doc_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        解析文档为Markdown（不切分）
        
        将已上传的文档解析为 Markdown 格式，但不进行切分。
        适用于需要完整文档内容或外部系统自行处理切分的场景。
        
        支持的文件格式:
        - PDF (.pdf)
        - Office 文档 (.doc, .docx, .ppt, .pptx)
        - 图片 (.jpg, .png)
        - HTML (.html, .htm)
        
        Args:
            doc_id: 文档ID
            config: 解析配置（可选）
                - layout_recognize: 布局识别引擎 (mineru 或 dots_ocr，默认 mineru)
                - enable_ocr: 是否启用 OCR (默认 False)
                - enable_formula: 是否识别公式 (默认 False)
                - enable_table: 是否识别表格 (默认 True)
                - from_page: 起始页（仅 PDF，默认 0）
                - to_page: 结束页（仅 PDF，默认 100000）
        
        Returns:
            解析结果字典:
            {
                "doc_id": "...",
                "doc_name": "...",
                "markdown": "...",          # 完整的 Markdown 内容
                "markdown_length": 5000,    # Markdown 长度
                "images": {...},            # 图片字典 (base64)
                "total_images": 2           # 图片总数
            }
        
        Raises:
            Exception: API调用失败
        
        Example:
            >>> result = doc_manager.parse_to_md(
            ...     doc_id="doc_123",
            ...     config={"layout_recognize": "mineru", "enable_ocr": False}
            ... )
            >>> print(f"Markdown length: {result['markdown_length']}")
            >>> print(f"First 200 chars: {result['markdown'][:200]}")
        """
        payload = {
            "doc_id": doc_id,
        }
        
        if config:
            payload["config"] = config
        
        url = "/powerrag/parse_to_md"
        res = self.client.post(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Parse to markdown failed"))
        
        return res_json.get("data", {})
    
    def parse_to_md_upload(
        self,
        file_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        上传文件并解析为Markdown（不切分）
        
        直接上传文件并解析为 Markdown 格式，不进行切分。
        不需要先上传到知识库，适合一次性解析场景。
        
        支持的文件格式:
        - PDF (.pdf)
        - Office 文档 (.doc, .docx, .ppt, .pptx)
        - 图片 (.jpg, .png)
        - HTML (.html, .htm)
        
        Args:
            file_path: 文件路径
            config: 解析配置（可选），同 parse_to_md
        
        Returns:
            解析结果字典，包含以下字段：
            - filename: 文件名
            - markdown: Markdown 内容
            - markdown_length: Markdown 长度
            - images: 图片字典
            - total_images: 图片总数
        
        Raises:
            FileNotFoundError: 文件不存在
            Exception: API调用失败
        
        Example:
            >>> result = doc_manager.parse_to_md_upload(
            ...     file_path="document.pdf",
            ...     config={"layout_recognize": "mineru"}
            ... )
            >>> print(result['markdown'])
            >>> print(f"Parsed {result['total_images']} images")
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Prepare files
        with open(path, "rb") as f:
            files = [("file", (path.name, f.read()))]
        
        # Prepare form data
        import json
        form_data = {}
        if config:
            form_data["config"] = json.dumps(config)
        
        url = "/powerrag/parse_to_md/upload"
        res = self.client.post(url, json=None, files=files, data=form_data)
        
        # Parse JSON response
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Parse to markdown (upload) failed"))
        
        return res_json.get("data", {})
    
    def parse_url(
        self,
        kb_id: str,
        url: str,
        name: str,
        wait: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> Union[DocumentInfo, str]:
        """
        解析URL文档
        
        Args:
            kb_id: 知识库ID
            url: 文档URL
            name: 文档名称
            wait: 是否等待解析完成（默认True）
            config: 解析配置（可选）
        
        Returns:
            如果wait=True，返回文档信息；如果wait=False，返回任务ID
        
        Raises:
            Exception: API调用失败
        """
        self.upload_from_url(kb_id, url, name)
        
        docs, _ = self.list(kb_id, name=name)
        if not docs:
            raise Exception(f"Failed to upload document from URL: {url}")
        
        doc_id = docs[0]["id"]
        
        if wait:
            self.parse_to_chunk(kb_id, [doc_id], wait=True, config=config)
            return self.get(kb_id, doc_id)
        
        task_id = self.parse_to_chunk(kb_id, [doc_id], wait=False, config=config)
        return task_id
    
    def cancel_parse(self, kb_id: str, doc_ids: List[str]) -> None:
        """
        取消解析任务
        
        Args:
            kb_id: 知识库ID
            doc_ids: 文档ID列表
        
        Raises:
            Exception: API调用失败
        """
        payload = {"document_ids": doc_ids}
        url = f"/datasets/{kb_id}/chunks"
        res = self.client.delete(url, json=payload)
        res_json = res.json()
        
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "Cancel parse failed"))
    
    def _wait_for_parse(self, kb_id: str, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """
        等待解析完成（内部方法）
        
        Args:
            kb_id: 知识库ID
            doc_ids: 文档ID列表
        
        Returns:
            解析结果列表
        """
        import time
        
        terminal_states = {"DONE", "FAIL", "CANCEL"}
        interval_sec = 1
        pending = set(doc_ids)
        results = []
        
        while pending:
            for doc_id in list(pending):
                try:
                    doc = self.get(kb_id, doc_id)
                    run_status = doc.get("run", "")
                    
                    if run_status in terminal_states:
                        results.append({
                            "doc_id": doc_id,
                            "status": run_status,
                            "chunk_count": doc.get("chunk_count", 0),
                            "token_count": doc.get("token_count", 0),
                        })
                        pending.discard(doc_id)
                    elif doc.get("progress", 0.0) >= 1.0:
                        results.append({
                            "doc_id": doc_id,
                            "status": "DONE",
                            "chunk_count": doc.get("chunk_count", 0),
                            "token_count": doc.get("token_count", 0),
                        })
                        pending.discard(doc_id)
                except Exception:
                    pass
            
            if pending:
                time.sleep(interval_sec)
        
        return results

