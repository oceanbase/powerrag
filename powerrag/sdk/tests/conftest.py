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

import os
import time
import pytest
from pathlib import Path

from powerrag.sdk import PowerRAGClient

# 从环境变量获取配置
HOST_ADDRESS = os.getenv("HOST_ADDRESS", "http://127.0.0.1:9222")
API_KEY = os.getenv("POWERRAG_API_KEY", "ragflow-MAln1FNDn9PhIcqv1axaaUT3mM-efUZ83O5LVcroe9E")


@pytest.fixture(scope="session")
def client():
    """
    创建PowerRAG客户端实例
    
    Returns:
        PowerRAGClient实例
    """
    return PowerRAGClient(api_key=API_KEY, base_url=HOST_ADDRESS)


@pytest.fixture(scope="function")
def kb_id(client: PowerRAGClient):
    """
    创建测试用的知识库
    
    Args:
        client: PowerRAG客户端实例
    
    Yields:
        知识库ID
    
    Returns:
        知识库ID
    """
    kb = client.knowledge_base.create(name=f"test_kb_{os.getpid()}")
    yield kb["id"]
    # 清理：删除测试知识库
    try:
        client.knowledge_base.delete([kb["id"]])
    except Exception:
        pass


@pytest.fixture(scope="function")
def doc_id(client: PowerRAGClient, kb_id: str, test_file_path: str):
    """
    创建测试用的文档
    
    Args:
        client: PowerRAG客户端实例
        kb_id: 知识库ID
        test_file_path: 测试文件路径
    
    Yields:
        文档ID
    """
    docs = client.document.upload(kb_id, test_file_path)
    yield docs[0]["id"]
    # 清理：删除测试文档
    try:
        client.document.delete(kb_id, [docs[0]["id"]])
    except Exception:
        pass


@pytest.fixture(scope="function")
def chunk_id(client: PowerRAGClient, kb_id: str, doc_id: str):
    """
    创建测试用的切片
    
    Args:
        client: PowerRAG客户端实例
        kb_id: 知识库ID
        doc_id: 文档ID
    
    Yields:
        切片ID
    """
    chunk = client.chunk.create(
        kb_id,
        doc_id,
        content="Test chunk content for testing"
    )
    yield chunk["id"]
    # 清理：删除测试切片
    try:
        client.chunk.delete(kb_id, doc_id, [chunk["id"]])
    except Exception:
        pass


@pytest.fixture(scope="function")
def test_file_path(tmp_path):
    """
    创建测试文件（HTML 格式，parse_to_md 支持）
    
    Args:
        tmp_path: pytest临时路径
    
    Returns:
        测试文件路径
    """
    test_file = tmp_path / "test_document.html"
    test_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Document</title>
</head>
<body>
    <h1>Test Document</h1>
    <p>This is a test document for PowerRAG SDK testing.</p>
    
    <h2>Section 1</h2>
    <p>This is the first section with some content.</p>
    
    <h2>Section 2</h2>
    <p>This is the second section with more content.</p>
</body>
</html>
""")
    return str(test_file)


@pytest.fixture(scope="function")
def test_files(tmp_path):
    """
    创建多个测试文件（HTML 格式）
    
    Args:
        tmp_path: pytest临时路径
    
    Returns:
        测试文件路径列表
    """
    files = []
    for i in range(3):
        test_file = tmp_path / f"test_document_{i}.html"
        test_file.write_text(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Document {i}</title>
</head>
<body>
    <h1>Test Document {i}</h1>
    <p>This is test document {i} for PowerRAG SDK testing.</p>
    
    <h2>Content</h2>
    <p>Sample content for document {i}.</p>
</body>
</html>
""")
        files.append(str(test_file))
    return files


@pytest.fixture(scope="function")
def doc_ids(client: PowerRAGClient, kb_id: str, test_files: list):
    """
    创建多个测试文档
    
    Args:
        client: PowerRAG客户端实例
        kb_id: 知识库ID
        test_files: 测试文件路径列表
    
    Yields:
        文档ID列表
    """
    docs = client.document.upload(kb_id, test_files)
    doc_ids = [doc["id"] for doc in docs]
    yield doc_ids
    # 清理：删除测试文档
    try:
        client.document.delete(kb_id, doc_ids)
    except Exception:
        pass


@pytest.fixture(scope="function")
def kb_with_docs(client: PowerRAGClient, test_files: list):
    """
    创建带有已解析文档的知识库（用于RAPTOR等需要文档的测试）
    
    Args:
        client: PowerRAG客户端实例
        test_files: 测试文件路径列表
    
    Yields:
        知识库ID
    """
    # 创建知识库
    kb = client.knowledge_base.create(name=f"test_kb_with_docs_{os.getpid()}")
    kb_id = kb["id"]
    
    try:
        # 上传文档
        docs = client.document.upload(kb_id, test_files)
        doc_ids = [doc["id"] for doc in docs]
        
        # 解析文档（wait=True 会等待解析完成）
        client.document.parse_to_chunk(kb_id, doc_ids, wait=True)
        
        yield kb_id
    finally:
        # 清理：删除测试知识库
        try:
            client.knowledge_base.delete([kb_id])
        except Exception:
            pass

