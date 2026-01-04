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


class TestDocumentUpload:
    """测试文档上传"""
    
    def test_upload_single_file(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试上传单个文件"""
        docs = client.document.upload(kb_id, test_file_path)
        assert len(docs) == 1
        assert docs[0]["id"] is not None
        assert docs[0]["name"] is not None
        
        # 清理
        client.document.delete(kb_id, [docs[0]["id"]])
    
    def test_upload_multiple_files(self, client: PowerRAGClient, kb_id: str, test_files: list):
        """测试批量上传文件"""
        docs = client.document.upload(kb_id, test_files)
        assert len(docs) == len(test_files)
        
        # 清理
        doc_ids = [doc["id"] for doc in docs]
        client.document.delete(kb_id, doc_ids)
    
    def test_upload_nonexistent_file(self, client: PowerRAGClient, kb_id: str):
        """测试上传不存在的文件"""
        with pytest.raises(FileNotFoundError):
            client.document.upload(kb_id, "nonexistent.pdf")


class TestDocumentList:
    """测试文档列表"""
    
    def test_list_all_documents(self, client: PowerRAGClient, kb_id: str):
        """测试列出所有文档"""
        docs, total = client.document.list(kb_id)
        assert isinstance(docs, list)
        assert total >= 0
    
    def test_list_with_filter(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试使用过滤器列出文档"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_name = uploaded_docs[0]["name"]
        
        try:
            docs, total = client.document.list(kb_id, name=doc_name)
            assert len(docs) >= 1
            assert any(doc["name"] == doc_name for doc in docs)
        finally:
            client.document.delete(kb_id, [uploaded_docs[0]["id"]])


class TestDocumentGet:
    """测试文档查询"""
    
    def test_get_existing_document(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试获取存在的文档"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            doc = client.document.get(kb_id, doc_id)
            assert doc["id"] == doc_id
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_get_nonexistent_document(self, client: PowerRAGClient, kb_id: str):
        """测试获取不存在的文档"""
        # 使用有效的UUID格式但不存在于系统中的ID
        nonexistent_id = "a" * 32  # 32个字符的十六进制字符串
        with pytest.raises(Exception) as exc_info:
            client.document.get(kb_id, nonexistent_id)
        # 检查错误信息中是否包含 "not found" 或 "don't own"
        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg or "don't own" in error_msg


class TestDocumentUpdate:
    """测试文档更新"""
    
    def test_update_name(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试更新文档名称"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            # 注意：不能更改文件扩展名，所以保持 .html 扩展名
            updated_doc = client.document.update(kb_id, doc_id, name="updated_name.html")
            assert updated_doc["name"] == "updated_name.html"
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_rename(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试重命名文档"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            # 注意：不能更改文件扩展名，所以保持 .html 扩展名
            renamed_doc = client.document.rename(kb_id, doc_id, "renamed.html")
            assert renamed_doc["name"] == "renamed.html"
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_set_meta(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试设置元数据"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            meta_fields = {"author": "Test Author", "category": "Test"}
            updated_doc = client.document.set_meta(kb_id, doc_id, meta_fields)
            assert updated_doc.get("meta_fields") == meta_fields
        finally:
            client.document.delete(kb_id, [doc_id])


class TestDocumentDelete:
    """测试文档删除"""
    
    def test_delete_single_document(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试删除单个文档"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        client.document.delete(kb_id, [doc_id])
        
        with pytest.raises(Exception):
            client.document.get(kb_id, doc_id)
    
    def test_delete_multiple_documents(self, client: PowerRAGClient, kb_id: str, test_files: list):
        """测试批量删除文档"""
        uploaded_docs = client.document.upload(kb_id, test_files)
        doc_ids = [doc["id"] for doc in uploaded_docs]
        
        client.document.delete(kb_id, doc_ids)
        
        for doc_id in doc_ids:
            with pytest.raises(Exception):
                client.document.get(kb_id, doc_id)


class TestDocumentDownload:
    """测试文档下载"""
    
    def test_download_to_bytes(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试下载为字节流"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            content = client.document.download(kb_id, doc_id)
            assert isinstance(content, bytes)
            assert len(content) > 0
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_download_to_file(self, client: PowerRAGClient, kb_id: str, test_file_path: str, tmp_path):
        """测试下载到文件"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            save_path = tmp_path / "downloaded_file.html"
            result_path = client.document.download(kb_id, doc_id, save_path=str(save_path))
            
            assert result_path == str(save_path)
            assert save_path.exists()
            assert save_path.stat().st_size > 0
        finally:
            client.document.delete(kb_id, [doc_id])


class TestDocumentParse:
    """测试文档解析"""
    
    def test_parse_to_chunk_sync(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试同步解析为切片"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            results = client.document.parse_to_chunk(kb_id, [doc_id], wait=True)
            assert len(results) == 1
            assert results[0]["status"] == "DONE"
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_parse_to_chunk_async(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试异步解析为切片"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            task_id = client.document.parse_to_chunk(kb_id, [doc_id], wait=False)
            assert task_id is not None
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_cancel_parse(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试取消解析"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            client.document.parse_to_chunk(kb_id, [doc_id], wait=False)
            client.document.cancel_parse(kb_id, [doc_id])
            
            doc = client.document.get(kb_id, doc_id)
            assert doc["run"] in ["CANCEL", "UNSTART"]
        finally:
            client.document.delete(kb_id, [doc_id])


class TestDocumentParseToMD:
    """测试文档解析为 Markdown（不切分）"""
    
    def test_parse_to_md_basic(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试基本的 parse_to_md 功能"""
        # 上传文档
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            # 解析为 Markdown
            result = client.document.parse_to_md(doc_id)
            
            # 验证返回结果
            assert "doc_id" in result
            assert "doc_name" in result
            assert "markdown" in result
            assert "markdown_length" in result
            assert result["doc_id"] == doc_id
            assert isinstance(result["markdown"], str)
            assert result["markdown_length"] > 0
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_parse_to_md_with_config(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试带配置参数的 parse_to_md"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            # 使用配置解析
            config = {
                "layout_recognize": "mineru",
                "enable_ocr": False,
                "enable_formula": False,
                "enable_table": True
            }
            result = client.document.parse_to_md(doc_id, config=config)
            
            # 验证返回结果
            assert result["doc_id"] == doc_id
            assert "markdown" in result
            assert len(result["markdown"]) > 0
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_parse_to_md_nonexistent_doc(self, client: PowerRAGClient):
        """测试解析不存在的文档"""
        nonexistent_id = "nonexistent_doc_id_123"
        
        with pytest.raises(Exception) as exc_info:
            client.document.parse_to_md(nonexistent_id)
        
        # 验证错误信息
        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg or "failed" in error_msg
    
    def test_parse_to_md_with_images(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试解析带图片的文档"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            result = client.document.parse_to_md(doc_id)
            
            # 验证图片相关字段
            assert "images" in result
            assert "total_images" in result
            assert isinstance(result["images"], dict)
            assert isinstance(result["total_images"], int)
            assert result["total_images"] >= 0
        finally:
            client.document.delete(kb_id, [doc_id])


class TestDocumentParseToMDAsync:
    """测试异步解析文档为 Markdown"""
    
    def test_parse_to_md_async_basic(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试异步解析基本功能"""
        # 上传文档
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            # 提交异步任务
            task_id = client.document.parse_to_md_async(doc_id)
            assert task_id
            assert len(task_id) > 0
            
            # 查询任务状态
            status = client.document.get_parse_to_md_status(task_id)
            assert "task_id" in status
            assert "status" in status
            assert status["status"] in ["pending", "processing", "success", "failed"]
            
            # 等待任务完成
            result = client.document.wait_for_parse_to_md(task_id, timeout=300)
            assert result["status"] == "success"
            assert "result" in result
            assert "markdown" in result["result"]
            assert result["result"]["markdown_length"] > 0
            
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_parse_to_md_async_with_config(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试异步解析带配置"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            # 提交带配置的异步任务
            task_id = client.document.parse_to_md_async(
                doc_id,
                config={
                    "layout_recognize": "mineru",
                    "enable_ocr": False,
                    "enable_table": True
                }
            )
            
            # 等待完成
            result = client.document.wait_for_parse_to_md(task_id, timeout=300)
            assert result["status"] == "success"
            assert result["result"]["markdown_length"] > 0
            
        finally:
            client.document.delete(kb_id, [doc_id])
    
    def test_parse_to_md_async_nonexistent_doc(self, client: PowerRAGClient):
        """测试异步解析不存在的文档"""
        with pytest.raises(Exception) as exc_info:
            client.document.parse_to_md_async("nonexistent_doc_id")
        
        assert "not found" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()
    
    def test_get_parse_to_md_status_not_found(self, client: PowerRAGClient):
        """测试查询不存在的任务状态"""
        status = client.document.get_parse_to_md_status("nonexistent_task_id")
        assert status["status"] == "not_found"
    
    def test_wait_for_parse_to_md_timeout(self, client: PowerRAGClient, kb_id: str, test_file_path: str):
        """测试等待任务超时（使用极短超时时间）"""
        uploaded_docs = client.document.upload(kb_id, test_file_path)
        doc_id = uploaded_docs[0]["id"]
        
        try:
            task_id = client.document.parse_to_md_async(doc_id)
            
            # 使用极短的超时时间（0.1秒）来触发超时
            with pytest.raises(TimeoutError):
                client.document.wait_for_parse_to_md(task_id, timeout=0.1, interval=0.05)
            
        finally:
            client.document.delete(kb_id, [doc_id])


class TestDocumentParseToMDUpload:
    """测试直接上传文件并解析为 Markdown"""
    
    def test_parse_to_md_upload_json_response(self, client: PowerRAGClient, test_file_path: str):
        """测试上传文件并返回 JSON 响应"""
        result = client.document.parse_to_md_upload(test_file_path)
        
        # 验证返回结果
        assert "filename" in result
        assert "markdown" in result
        assert "markdown_length" in result
        assert "images" in result
        assert "total_images" in result
        assert isinstance(result["markdown"], str)
        assert result["markdown_length"] > 0
    
    def test_parse_to_md_upload_with_config(self, client: PowerRAGClient, test_file_path: str):
        """测试带配置参数上传并解析"""
        config = {
            "layout_recognize": "mineru",
            "enable_ocr": False
        }
        result = client.document.parse_to_md_upload(test_file_path, config=config)
        
        assert "markdown" in result
        assert len(result["markdown"]) > 0
    
    def test_parse_to_md_upload_nonexistent_file(self, client: PowerRAGClient):
        """测试上传不存在的文件"""
        with pytest.raises(FileNotFoundError):
            client.document.parse_to_md_upload("nonexistent_file.pdf")
    
    def test_parse_to_md_upload_different_formats(self, client: PowerRAGClient, test_file_path: str):
        """测试上传不同格式的文件"""
        # 注意：这个测试需要实际的不同格式文件
        # 这里我们只测试 txt 文件，实际使用时可以添加更多格式
        result = client.document.parse_to_md_upload(test_file_path)
        
        assert "markdown" in result
        assert result["markdown_length"] > 0