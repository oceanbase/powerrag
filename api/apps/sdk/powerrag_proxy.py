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

"""
PowerRAG API Proxy

将 PowerRAG API 请求代理转发到独立的 PowerRAG server（端口6000）
这样 SDK 可以通过主 RAGFlow 服务访问 PowerRAG 功能，无需直接连接到 PowerRAG server
"""

import os
import logging
import httpx
from quart import request, jsonify
from api.utils.api_utils import token_required, get_error_data_result

logger = logging.getLogger(__name__)

# manager 变量由 api/apps/__init__.py 的 register_page 函数自动注入
# 这里使用 # noqa: F821 来忽略未定义的警告

# PowerRAG server 地址配置
# 可以通过环境变量 POWERRAG_SERVER_URL 配置，默认为 http://localhost:6000
POWERRAG_SERVER_URL = os.environ.get("POWERRAG_SERVER_URL", "http://localhost:6000")
POWERRAG_API_PREFIX = f"{POWERRAG_SERVER_URL}/api/v1/powerrag"

# 创建异步 HTTP 客户端（使用连接池提高性能）
_http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(300.0, connect=10.0),  # 5分钟总超时，10秒连接超时
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    follow_redirects=True,
)


async def _forward_request(method: str, endpoint: str, tenant_id: str = None):
    """
    将请求转发到 PowerRAG server（使用异步 HTTP 客户端）
    
    Args:
        method: HTTP 方法 (GET, POST, PUT, DELETE)
        endpoint: PowerRAG API 端点（不包含 /api/v1/powerrag 前缀）
        tenant_id: 租户ID（可选，用于日志）
    
    Returns:
        PowerRAG server 的响应
    """
    url = f"{POWERRAG_API_PREFIX}{endpoint}"
    
    # 获取请求数据
    if method == "GET":
        params = dict(request.args)
        json_data = None
        files = None
        data = None
    else:
        params = None
        json_data = None
        files = None
        data = None
        
        # 尝试获取 JSON 数据
        try:
            json_data = await request.get_json(silent=True)
        except Exception:
            pass
        
        # 如果没有 JSON 数据，尝试获取表单数据或文件
        if json_data is None:
            try:
                form = await request.form
                if form:
                    data = dict(form)
            except Exception:
                pass
            
            try:
                files_dict = await request.files
                if files_dict:
                    # 保留文件名信息！重要：不能直接 dict(files_dict)
                    # 因为会丢失文件名。需要构造 httpx 期望的格式
                    files = {}
                    for field_name, file_storage in files_dict.items():
                        # httpx 期望格式: (filename, content, content_type)
                        files[field_name] = (
                            file_storage.filename,
                            file_storage.read(),
                            file_storage.content_type or 'application/octet-stream'
                        )
            except Exception:
                pass
    
    # 获取请求头（传递 Authorization）
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]
    
    try:
        logger.info(f"Forwarding {method} {endpoint} to PowerRAG server: {url}")
        
        # 使用异步 HTTP 客户端发送请求
        response = await _http_client.request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            data=data,
            files=files,
            headers=headers,
        )
        
        logger.info(f"PowerRAG server response status: {response.status_code}")
        
        # 返回响应
        try:
            response_json = response.json()
            logger.debug(f"Response JSON: {response_json}")
            return jsonify(response_json), response.status_code
        except Exception as e:
            # 如果不是 JSON 响应，记录错误并返回错误信息
            logger.error(f"Failed to parse response as JSON: {e}", exc_info=True)
            logger.error(f"Response status: {response.status_code}")
            
            # 尝试读取响应文本
            try:
                response_text = response.text
                error_msg = response_text[:200] if response_text else "(empty response body)"
            except Exception:
                error_msg = "(unable to read response body)"
            
            logger.error(f"Response content (first 200 chars): {error_msg}")
            logger.error(f"Response headers: {dict(response.headers)}")
            
            # 返回错误响应
            return get_error_data_result(
                message=f"PowerRAG server returned invalid JSON response: {error_msg}"
            ), response.status_code if response.status_code >= 400 else 500
    
    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to PowerRAG server at {POWERRAG_SERVER_URL}: {e}", exc_info=True)
        return get_error_data_result(
            message=f"PowerRAG server is not available at {POWERRAG_SERVER_URL}. "
                   f"Please ensure the PowerRAG server is running on port 6000."
        ), 503
    
    except httpx.TimeoutException as e:
        logger.error(f"Request to PowerRAG server timed out: {url}", exc_info=True)
        return get_error_data_result(
            message="Request to PowerRAG server timed out"
        ), 504
    
    except httpx.HTTPStatusError as e:
        logger.error(f"PowerRAG server returned error status {e.response.status_code}: {e}", exc_info=True)
        try:
            error_json = e.response.json()
            return jsonify(error_json), e.response.status_code
        except Exception:
            return get_error_data_result(
                message=f"PowerRAG server error: {e.response.status_code} {e.response.text[:200]}"
            ), e.response.status_code
    
    except Exception as e:
        logger.error(f"Error forwarding request to PowerRAG server: {e}", exc_info=True)
        error_msg = str(e)
        if hasattr(e, '__class__'):
            error_msg = f"{e.__class__.__name__}: {error_msg}"
        return get_error_data_result(
            message=f"Error forwarding request to PowerRAG server: {error_msg}"
        ), 500


@manager.route("/powerrag/split", methods=["POST"])  # noqa: F821
@token_required
async def split_text_proxy(tenant_id):
    """
    智能路由文本切片请求：
    - PowerRAG chunkers (title, regex, smart) -> 转发到 PowerRAG server
    - RAGFlow chunkers (naive, paper, book 等) -> 使用 RAGFlow 的实现
    
    ---
    tags:
      - PowerRAG Proxy
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        description: Split text parameters.
        required: true
        schema:
          type: object
          properties:
            text:
              type: string
              description: Text to split.
            parser_id:
              type: string
              description: Parser ID.
            config:
              type: object
              description: Parser configuration.
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer token for authentication.
    responses:
      200:
        description: Split result.
    """
    try:
        # 获取请求数据
        data = await request.get_json()
        if not data:
            return get_error_data_result(message="No JSON data provided"), 400
        
        text = data.get("text")
        parser_id = data.get("parser_id", "title")
        config = data.get("config", {})
        
        if not text:
            return get_error_data_result(message="text is required"), 400
        
        # PowerRAG 支持的纯文本 chunker（专为文本切片设计）
        POWERRAG_CHUNKERS = {"title", "regex", "smart"}
        
        # RAGFlow 支持纯文本切片的 chunker（使用 naive_merge）
        RAGFLOW_TEXT_CHUNKERS = {"naive", "general"}
        
        # RAGFlow 需要文件处理的 chunker（不支持纯文本切片）
        # RAGFLOW_DOCUMENT_CHUNKERS = {
        #     "paper", "book", "laws", "presentation", "manual", 
        #     "qa", "table", "resume", "picture", "one", 
        #     "knowledge_graph", "email", "tag"
        # }
        
        if parser_id.lower() in POWERRAG_CHUNKERS:
            # 转发到 PowerRAG server
            logger.info(f"Forwarding '{parser_id}' chunker to PowerRAG server")
            return await _forward_request("POST", "/split", tenant_id)
            
        elif parser_id.lower() in RAGFLOW_TEXT_CHUNKERS:
            # 使用 RAGFlow 的 naive_merge 处理纯文本
            logger.info(f"Using RAGFlow naive_merge for '{parser_id}' chunker")
            from rag.nlp import naive_merge
            
            # 默认配置
            chunk_token_num = config.get("chunk_token_num", 128)
            delimiter = config.get("delimiter", "\n!?。；！？")
            
            # naive_merge 需要 sections 参数，格式为 [(text, position), ...]
            sections = [(text, "")]
            
            # 调用 RAGFlow 的 naive_merge
            chunks = naive_merge(sections, chunk_token_num=chunk_token_num, delimiter=delimiter)
            
            # 过滤掉空白块
            chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
            
            # 返回结果
            return jsonify({
                "code": 0,
                "data": {
                    "parser_id": parser_id,
                    "chunks": chunks,
                    "total_chunks": len(chunks),
                    "text_length": len(text),
                    "metadata": {
                        "chunker": "ragflow",
                        "config": config
                    }
                },
                "message": "success"
            }), 200            
        # elif parser_id.lower() in RAGFLOW_DOCUMENT_CHUNKERS:
        #     # 这些 chunker 需要文档文件，不支持纯文本切片
        #     return get_error_data_result(
        #         message=f"Chunker '{parser_id}' requires document file processing and does not support pure text splitting. "
        #                 f"Supported text chunkers are: {', '.join(sorted(POWERRAG_CHUNKERS | RAGFLOW_TEXT_CHUNKERS))}"
        #     ), 400
        else:
            # 未知的 chunker
            return get_error_data_result(
                message=f"Unknown chunker '{parser_id}'. "
                        f"Supported text chunkers are: {', '.join(sorted(POWERRAG_CHUNKERS | RAGFLOW_TEXT_CHUNKERS))}"
            ), 400
            
    except Exception as e:
        logger.error(f"Error in split_text_proxy: {e}", exc_info=True)
        return get_error_data_result(message=f"Failed to split text: {str(e)}"), 500


@manager.route("/powerrag/extract", methods=["POST"])  # noqa: F821
@token_required
async def extract_from_document_proxy(tenant_id):
    """
    代理 extract_from_document API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/extract", tenant_id)


@manager.route("/powerrag/extract/text", methods=["POST"])  # noqa: F821
@token_required
async def extract_from_text_proxy(tenant_id):
    """
    代理 extract_from_text API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/extract/text", tenant_id)


@manager.route("/powerrag/extract/batch", methods=["POST"])  # noqa: F821
@token_required
async def extract_batch_proxy(tenant_id):
    """
    代理 extract_batch API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/extract/batch", tenant_id)


@manager.route("/powerrag/struct_extract/submit", methods=["POST"])  # noqa: F821
@token_required
async def struct_extract_submit_proxy(tenant_id):
    """
    代理 struct_extract/submit API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/struct_extract/submit", tenant_id)


@manager.route("/powerrag/struct_extract/status/<task_id>", methods=["GET"])  # noqa: F821
@token_required
async def struct_extract_status_proxy(tenant_id, task_id):
    """
    代理 struct_extract/status API 请求到 PowerRAG server
    """
    return await _forward_request("GET", f"/struct_extract/status/{task_id}", tenant_id)


@manager.route("/powerrag/parse", methods=["POST"])  # noqa: F821
@token_required
async def parse_document_proxy(tenant_id):
    """
    代理 parse API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/parse", tenant_id)


@manager.route("/powerrag/parse/batch", methods=["POST"])  # noqa: F821
@token_required
async def parse_batch_proxy(tenant_id):
    """
    代理 parse/batch API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/parse/batch", tenant_id)


@manager.route("/powerrag/parse/upload", methods=["POST"])  # noqa: F821
@token_required
async def parse_upload_proxy(tenant_id):
    """
    代理 parse/upload API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/parse/upload", tenant_id)


@manager.route("/powerrag/convert", methods=["POST"])  # noqa: F821
@token_required
async def convert_document_proxy(tenant_id):
    """
    代理 convert API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/convert", tenant_id)


@manager.route("/powerrag/convert/upload", methods=["POST"])  # noqa: F821
@token_required
async def convert_upload_proxy(tenant_id):
    """
    代理 convert/upload API 请求到 PowerRAG server
    """
    return await _forward_request("POST", "/convert/upload", tenant_id)


@manager.route("/powerrag/parse_to_md", methods=["POST"])  # noqa: F821
@token_required
async def parse_to_md_proxy(tenant_id):
    """
    代理 parse_to_md API 请求到 PowerRAG server
    
    将文档解析为 Markdown 格式，但不进行切分。
    适用于需要完整文档内容或外部系统自行处理切分的场景。
    
    支持的文件格式:
    - PDF (.pdf)
    - Office 文档 (.doc, .docx, .ppt, .pptx)
    - 图片 (.jpg, .png)
    - HTML (.html, .htm)
    - Markdown (.md)
    
    ---
    tags:
      - PowerRAG Proxy
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        description: Parse to markdown parameters.
        required: true
        schema:
          type: object
          properties:
            doc_id:
              type: string
              required: true
              description: RAGFlow document ID.
            config:
              type: object
              description: Parser configuration.
              properties:
                layout_recognize:
                  type: string
                  description: Layout recognition engine (mineru or dots_ocr).
                enable_ocr:
                  type: boolean
                  description: Enable OCR.
                enable_formula:
                  type: boolean
                  description: Enable formula recognition.
                enable_table:
                  type: boolean
                  description: Enable table recognition.
                from_page:
                  type: integer
                  description: Start page number (for PDF).
                to_page:
                  type: integer
                  description: End page number (for PDF).
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer token for authentication.
    responses:
      200:
        description: Parse to markdown result.
        schema:
          type: object
          properties:
            code:
              type: integer
            data:
              type: object
              properties:
                doc_id:
                  type: string
                doc_name:
                  type: string
                markdown:
                  type: string
                markdown_length:
                  type: integer
                images:
                  type: object
                total_images:
                  type: integer
            message:
              type: string
    """
    return await _forward_request("POST", "/parse_to_md", tenant_id)


@manager.route("/powerrag/parse_to_md/async", methods=["POST"])  # noqa: F821
@token_required
async def parse_to_md_async_proxy(tenant_id):
    """
    代理 parse_to_md/async API 请求到 PowerRAG server (异步提交任务)
    
    异步解析文档为 Markdown，返回任务 ID。
    适用于大文档或需要长时间处理的场景。
    
    ---
    tags:
      - PowerRAG Proxy
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            doc_id:
              type: string
              description: Document ID
            config:
              type: object
              description: Parser configuration
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer token for authentication.
    responses:
      200:
        description: Task submitted successfully, returns task_id.
    """
    return await _forward_request("POST", "/parse_to_md/async", tenant_id)


@manager.route("/powerrag/parse_to_md/status/<task_id>", methods=["GET"])  # noqa: F821
@token_required
async def parse_to_md_status_proxy(tenant_id, task_id):
    """
    代理 parse_to_md/status API 请求到 PowerRAG server (查询任务状态)
    
    查询异步解析任务的状态和结果。
    
    ---
    tags:
      - PowerRAG Proxy
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: Task ID returned from async submission
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer token for authentication.
    responses:
      200:
        description: Task status and result.
    """
    return await _forward_request("GET", f"/parse_to_md/status/{task_id}", tenant_id)


@manager.route("/powerrag/parse_to_md/upload", methods=["POST"])  # noqa: F821
@token_required
async def parse_to_md_upload_proxy(tenant_id):
    """
    代理 parse_to_md/upload API 请求到 PowerRAG server
    
    直接上传文件并解析为 Markdown，不进行切分。
    
    支持的文件格式:
    - PDF (.pdf)
    - Office 文档 (.doc, .docx, .ppt, .pptx)
    - 图片 (.jpg, .png)
    - HTML (.html, .htm)
    - Markdown (.md)
    
    ---
    tags:
      - PowerRAG Proxy
    security:
      - ApiKeyAuth: []
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: File to parse (PDF, Office (doc/docx/ppt/pptx), Images (jpg/png), HTML, Markdown).
      - in: formData
        name: config
        type: string
        description: JSON string of parser configuration.
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer token for authentication.
    responses:
      200:
        description: Parse to markdown result.
    """
    return await _forward_request("POST", "/parse_to_md/upload", tenant_id)

