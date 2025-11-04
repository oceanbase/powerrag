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

"""PowerRAG Unified API Routes"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file, Response
from powerrag.server.services.parse_service import PowerRAGParseService
from powerrag.server.services.convert_service import PowerRAGConvertService
from powerrag.server.services.split_service import PowerRAGSplitService
from powerrag.server.services.extract_service import PowerRAGExtractService
from powerrag.utils.api_utils import get_data_error_result
from api.utils.api_utils import apikey_required
import io
import langextract as lx

# Import RAGFlow services for task queue integration
from api.db.services.document_service import DocumentService
from api.db.services.file2document_service import File2DocumentService
from api.db.services.task_service import TaskService, queue_tasks, cancel_all_task_of
from api.db import TaskStatus, ParserType
from api import settings
from rag.nlp import search
from api.utils.configs import get_base_config

logger = logging.getLogger(__name__)

powerrag_bp = Blueprint("powerrag", __name__)

# Get Gotenberg URL from config file (priority) or environment variable (fallback)
gotenberg_config = get_base_config("gotenberg", {})
GOTENBERG_URL = gotenberg_config.get("url", os.environ.get("GOTENBERG_URL", "http://localhost:3000"))


# ============================================================================
# 文档解析接口
# ============================================================================

@powerrag_bp.route("/run", methods=["POST"])
def run_parse():
    """
    Run PowerRAG parsing tasks using task_executor (async) - 推荐使用
    
    Similar to /v1/document/run, this creates tasks in the queue system.
    This is the RECOMMENDED way for production use.
    
    Request Body:
    {
        "doc_ids": ["doc_id1", "doc_id2"],
        "run": "1",  // 1=start, 2=cancel
        "delete": false,  // whether to delete existing chunks
        "config": {
            "title_level": 3,
            "chunk_token_num": 256,
            "layout_recognize": "mineru"
        }
    }
    
    Response:
    {
        "code": 0,
        "message": "Tasks queued successfully",
        "data": {
            "results": [...],
            "total": 2,
            "success": 2,
            "failed": 0
        }
    }
    """
    logger.info(f"=== PowerRAG /run endpoint called from {request.remote_addr} ===")
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        doc_ids = data.get("doc_ids", [])
        run_status = str(data.get("run", TaskStatus.RUNNING.value))
        delete = data.get("delete", False)
        config = data.get("config", {})
        logger.info(f"doc_ids: {doc_ids}, run_status: {run_status}, delete: {delete}, config: {config}")
        if not doc_ids:
            return jsonify({
                "code": 400,
                "message": "doc_ids is required"
            }), 400
        
        if isinstance(doc_ids, str):
            doc_ids = [doc_ids]
        
        results = []
        
        for doc_id in doc_ids:
            try:
                # Get document
                exist, doc = DocumentService.get_by_id(doc_id)
                if not exist:
                    logger.warning(f"Document {doc_id} not found in database")
                    results.append({
                        "doc_id": doc_id,
                        "success": False,
                        "error": "Document not found"
                    })
                    continue
                
                tenant_id = DocumentService.get_tenant_id(doc_id)
                if not tenant_id:
                    results.append({
                        "doc_id": doc_id,
                        "success": False,
                        "error": "Tenant not found"
                    })
                    continue
                
                # Get parser_id from document (doc is a Peewee Model object, not a dict)
                parser_id = doc.parser_id if doc.parser_id else ParserType.TITLE.value
                
                # Handle cancel
                if run_status == TaskStatus.CANCEL.value:
                    if str(doc.run) == TaskStatus.RUNNING.value:
                        cancel_all_task_of(doc_id)
                        results.append({
                            "doc_id": doc_id,
                            "success": True,
                            "message": "Task canceled"
                        })
                    else:
                        results.append({
                            "doc_id": doc_id,
                            "success": False,
                            "error": "Cannot cancel a task that is not running"
                        })
                    continue
                
                # Update document status and config
                update_info = {"run": run_status, "progress": 0}
                
                if run_status == TaskStatus.RUNNING.value and delete:
                    update_info.update({
                        "progress_msg": "",
                        "chunk_num": 0,
                        "token_num": 0
                    })
                
                # Clear existing data if needed
                if delete:
                    from api.db.db_models import Task as TaskModel
                    TaskService.filter_delete([TaskModel.doc_id == doc_id])
                    if settings.docStoreConn.indexExist(search.index_name(tenant_id), doc.kb_id):
                        settings.docStoreConn.delete(
                            {"doc_id": doc_id}, 
                            search.index_name(tenant_id), 
                            doc.kb_id
                        )
                
                DocumentService.update_by_id(doc_id, update_info)
                
                # Queue task if starting
                if run_status == TaskStatus.RUNNING.value:
                    doc_dict = doc.to_dict()
                    doc_dict["tenant_id"] = tenant_id
                    
                    # Apply config updates
                    # if config:
                    #     doc_dict["parser_id"] = parser_id
                        # doc_dict["parser_config"] = config["parser_config"]
                    
                    bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
                    queue_tasks(doc_dict, bucket, name, 0)
                    
                    results.append({
                        "doc_id": doc_id,
                        "success": True,
                        "message": "Task queued successfully"
                    })
                
            except Exception as e:
                logger.error(f"Error processing doc {doc_id}: {e}", exc_info=True)
                results.append({
                    "doc_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        # Check overall success
        all_success = all(r.get("success", False) for r in results)
        
        return jsonify({
            "code": 0 if all_success else 500,
            "message": "success" if all_success else "Some tasks failed !!!!",
            "data": {
                "results": results,
                "total": len(doc_ids),
                "success": sum(1 for r in results if r.get("success", False)),
                "failed": sum(1 for r in results if not r.get("success", False))
            }
        }), 200 if all_success else 207
        
    except Exception as e:
        logger.error(f"Run parse error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/parse", methods=["POST"])
@apikey_required
def parse_document(tenant_id):
    """
    Quick parse for preview (synchronous) - 仅用于快速预览
    
    ⚠️ 注意：此接口为同步处理，仅用于快速预览和调试。
    生产环境请使用 /run 接口（异步、可靠、支持大文件）。
    
    Request JSON:
    {
        "doc_id": "document_id",
        "config": {
            "title_level": 3,
            "chunk_token_num": 256
        }
    }
    
    Response:
    {
        "code": 0,
        "data": {
            "doc_id": "...",
            "chunks": [...],
            "preview": "..."
        },
        "message": "success (preview only, use /run for production)"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        doc_id = data.get("doc_id")
        config = data.get("config", {})
        
        if not doc_id:
            return jsonify({
                "code": 400,
                "message": "doc_id is required"
            }), 400
        
        # Create service with Gotenberg URL
        gotenberg_url = config.get("gotenberg_url", GOTENBERG_URL) if config else GOTENBERG_URL
        service = PowerRAGParseService(gotenberg_url=gotenberg_url)
        e, doc = DocumentService.get_by_id(doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")
        # doc is a Peewee Model object, use attribute access
        parser_id = doc.parser_id if doc.parser_id else ParserType.TITLE.value
        result = service.parse_document(doc_id, parser_id, config)
        
        # Generate preview (first 500 chars)
        chunks = result.get("chunks", [])
        preview = ""
        if chunks:
            preview = chunks[0].get("content_with_weight", "")[:500]
        
        return jsonify({
            "code": 0,
            "data": {
                **result,
                "preview": preview,
                "note": "This is a quick preview. For production use, please use /run endpoint."
            },
            "message": "success (preview only, use /run for production)"
        }), 200
        
    except Exception as e:
        logger.error(f"Parse document error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/parse/batch", methods=["POST"])
@apikey_required
def parse_documents_batch(tenant_id):
    """
    Batch parse multiple documents (using ThreadPoolExecutor like FileService.parse_docs)
    
    Request JSON:
    {
        "doc_ids": ["doc_id1", "doc_id2"],
        "parser_type": "pdf",
        "config": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        doc_ids = data.get("doc_ids", [])
        parser_type = data.get("parser_type")
        config = data.get("config", {})
        
        if not doc_ids:
            return jsonify({
                "code": 400,
                "message": "doc_ids is required"
            }), 400
        
        # Create service with Gotenberg URL
        gotenberg_url = config.get("gotenberg_url", GOTENBERG_URL) if config else GOTENBERG_URL
        service = PowerRAGParseService(gotenberg_url=gotenberg_url)
        # Use the batch method with ThreadPoolExecutor (same as FileService.parse_docs)
        results = service.parse_docs_batch(doc_ids, parser_type, config)
        
        return jsonify({
            "code": 0,
            "data": results,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Batch parse error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/parse/upload", methods=["POST"])
@apikey_required
def parse_upload_file():
    """
    Parse uploaded file directly and return markdown + images
    
    Authentication: Requires RAGFlow API key in Authorization header (Bearer token)
    
    Request (multipart/form-data):
    - file: File to parse (required) - supports PDF, Office (docx/xlsx/pptx), HTML, Markdown
    - parser_id: Parser ID - title/naive/paper (optional, default: title)
    - config: JSON string of parser config (optional)
    
    Config parameters:
    - formula_enable (bool): Enable formula recognition (default: true)
    - enable_ocr (bool): Enable OCR (default: false)
    - from_page (int): Start page number (default: 0)
    - to_page (int): End page number (default: 100000)
    
    Response JSON:
    {
        "code": 0,
        "data": {
            "filename": "document.pdf",
            "markdown": "# Title\n\nContent...",
            "images": {
                "image_001.png": "base64_encoded_data...",
                "image_002.png": "base64_encoded_data..."
            },
            "total_images": 2,
            "markdown_length": 5000
        },
        "message": "success"
    }
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                "code": 400,
                "message": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 400,
                "message": "No file selected"
            }), 400
        
        # Get parameters
        parser_id = request.form.get('parser_id', 'title')
        
        # Parse config from JSON string if provided
        import json
        config_str = request.form.get('config', '{}')
        try:
            config = json.loads(config_str)
        except json.JSONDecodeError:
            return jsonify({
                "code": 400,
                "message": "Invalid JSON in config parameter"
            }), 400
        
        filename = file.filename
        
        # Read file binary
        binary = file.read()
        if not binary:
            return jsonify({
                "code": 400,
                "message": "File is empty"
            }), 400
        
        # Create service and parse
        gotenberg_url = config.get("gotenberg_url", GOTENBERG_URL) if config else GOTENBERG_URL
        service = PowerRAGParseService(gotenberg_url=gotenberg_url)
        
        result = service.parse_file_binary(binary, filename, parser_id, config)
        
        return jsonify({
            "code": 0,
            "data": result,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Parse upload file error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


# ============================================================================
# 文档转换接口
# ============================================================================

@powerrag_bp.route("/convert", methods=["POST"])
@apikey_required
def convert_document(tenant_id):
    """
    Convert document format using PowerRAG converters
    
    Authentication: Requires RAGFlow API key in Authorization header (Bearer token)
    
    Request JSON:
    {
        "doc_id": "document_id",
        "source_format": "pdf",
        "target_format": "markdown",
        "config": {
            "with_images": true,
            "formula_enable": true,
            "enable_ocr": false,
            "from_page": 0,
            "to_page": 100000
        }
    }
    
    Config parameters for PDF to Markdown conversion:
    - with_images (bool): Include images in output (default: true)
    - formula_enable (bool): Enable formula recognition (default: true)
    - enable_ocr (bool): Enable OCR (default: false)
    - from_page (int): Start page number (default: 0)
    - to_page (int): End page number (default: 100000)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        doc_id = data.get("doc_id")
        source_format = data.get("source_format", "pdf")
        target_format = data.get("target_format", "markdown")
        config = data.get("config", {})
        
        if not doc_id:
            return jsonify({
                "code": 400,
                "message": "doc_id is required"
            }), 400
        
        # Create service with Gotenberg URL for Office/HTML → PDF conversion
        service = PowerRAGConvertService(gotenberg_url=GOTENBERG_URL)
        result = service.convert_document(doc_id, source_format, target_format, config)
        
        return jsonify({
            "code": 0,
            "data": result,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Convert document error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/convert/upload", methods=["POST"])
@apikey_required
def convert_upload_file(tenant_id):
    """
    Convert uploaded file directly (with file download support)
    
    Authentication: Requires RAGFlow API key in Authorization header (Bearer token)
    
    Request (multipart/form-data):
    - file: File to convert (required)
    - source_format: Source format - pdf/office/html (optional, auto-detect from filename)
    - target_format: Target format - markdown/pdf (required)
    - config: JSON string of conversion config (optional)
    
    Config parameters (same as /convert):
    - with_images (bool): Include images in output (default: true)
    - formula_enable (bool): Enable formula recognition (default: true)
    - enable_ocr (bool): Enable OCR (default: false)
    - from_page (int): Start page number (default: 0)
    - to_page (int): End page number (default: 100000)
    
    Response:
    - For markdown: Returns file as downloadable .md file
    - For PDF: Returns file as downloadable .pdf file
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                "code": 400,
                "message": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 400,
                "message": "No file selected"
            }), 400
        
        # Get parameters
        source_format = request.form.get('source_format', '').lower()
        target_format = request.form.get('target_format', 'markdown').lower()
        
        # Parse config from JSON string if provided
        import json
        config_str = request.form.get('config', '{}')
        try:
            config = json.loads(config_str)
        except json.JSONDecodeError:
            return jsonify({
                "code": 400,
                "message": "Invalid JSON in config parameter"
            }), 400
        
        # Auto-detect source format from filename if not provided
        filename = file.filename
        if not source_format:
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext == 'pdf':
                source_format = 'pdf'
            elif ext in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                source_format = 'office'
            elif ext in ['html', 'htm']:
                source_format = 'html'
            else:
                return jsonify({
                    "code": 400,
                    "message": f"Cannot auto-detect format from filename '{filename}'. Please specify source_format parameter."
                }), 400
        
        # Read file binary
        binary = file.read()
        if not binary:
            return jsonify({
                "code": 400,
                "message": "File is empty"
            }), 400
        
        # Add filename to config
        config['filename'] = filename
        
        # Create service and convert
        service = PowerRAGConvertService(gotenberg_url=GOTENBERG_URL)
        result = service.convert_file_binary(binary, source_format, target_format, config)
        
        # Prepare output filename
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        if target_format == 'markdown':
            output_filename = f"{base_name}.md"
            mimetype = 'text/markdown'
        elif target_format == 'pdf':
            output_filename = f"{base_name}.pdf"
            mimetype = 'application/pdf'
        else:
            output_filename = f"{base_name}.{target_format}"
            mimetype = 'application/octet-stream'
        
        # Return file as download
        content = result['content']
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        return Response(
            content,
            mimetype=mimetype,
            headers={
                'Content-Disposition': f'attachment; filename="{output_filename}"',
                'Content-Length': str(len(content))
            }
        )
        
    except Exception as e:
        logger.error(f"Convert upload file error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


# ============================================================================
# 文档切片接口
# ============================================================================

@powerrag_bp.route("/split", methods=["POST"])
@apikey_required
def split_text(tenant_id):
    """
    Split text into chunks using powerrag/app chunking methods
    
    Note: This endpoint only handles TEXT splitting, not document parsing.
    Uses chunking methods from powerrag/app based on parser_id.
    
    Request JSON:
    {
        "text": "# Title 1\n\nYour markdown content...",
        "parser_id": "title",
        "config": {
            "title_level": 3,
            "chunk_token_num": 256
        }
    }
    
    Response:
    {
        "code": 0,
        "data": {
            "parser_id": "title",
            "chunks": [...],
            "total_chunks": 10,
            "text_length": 5000
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        text = data.get("text")
        parser_id = data.get("parser_id", "title")
        config = data.get("config", {})
        
        if not text:
            return jsonify({
                "code": 400,
                "message": "text is required"
            }), 400
        
        if not isinstance(text, str):
            return jsonify({
                "code": 400,
                "message": "text must be a string"
            }), 400
        
        service = PowerRAGSplitService()
        result = service.split_text(text, parser_id, config)
        
        return jsonify({
            "code": 0,
            "data": result,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Split text error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


# ============================================================================
# 信息抽取接口
# ============================================================================

@powerrag_bp.route("/extract", methods=["POST"])
@apikey_required
def extract_from_document(tenant_id):
    """
    Extract information from document using PowerRAG extractors
    
    Request JSON:
    {
        "doc_id": "document_id",
        "extractor_type": "entity|keyword|summary",
        "config": {
            "entity_types": ["PERSON", "ORG"],
            "max_keywords": 20
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        doc_id = data.get("doc_id")
        extractor_type = data.get("extractor_type", "entity")
        config = data.get("config", {})
        
        if not doc_id:
            return jsonify({
                "code": 400,
                "message": "doc_id is required"
            }), 400
        
        service = PowerRAGExtractService()
        result = service.extract_from_document(doc_id, extractor_type, config)
        
        return jsonify({
            "code": 0,
            "data": result,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Extract from document error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/extract/text", methods=["POST"])
@apikey_required
def extract_from_text(tenant_id):
    """
    Extract information from raw text (no doc_id required)
    
    Request JSON:
    {
        "text": "text content",
        "extractor_type": "entity|keyword|summary",
        "config": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        text = data.get("text")
        extractor_type = data.get("extractor_type", "entity")
        config = data.get("config", {})
        
        if not text:
            return jsonify({
                "code": 400,
                "message": "text is required"
            }), 400
        
        service = PowerRAGExtractService()
        result = service.extract_from_text(text, extractor_type, config)
        
        return jsonify({
            "code": 0,
            "data": result,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Extract from text error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/extract/batch", methods=["POST"])
def extract_batch(tenant_id):
    """
    Extract information from multiple documents
    
    Request JSON:
    {
        "doc_ids": ["doc_id1", "doc_id2"],
        "extractor_type": "entity",
        "config": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        doc_ids = data.get("doc_ids", [])
        extractor_type = data.get("extractor_type", "entity")
        config = data.get("config", {})
        
        if not doc_ids:
            return jsonify({
                "code": 400,
                "message": "doc_ids is required"
            }), 400
        
        service = PowerRAGExtractService()
        results = []
        
        for doc_id in doc_ids:
            try:
                result = service.extract_from_document(doc_id, extractor_type, config)
                results.append({
                    "doc_id": doc_id,
                    "success": True,
                    "data": result
                })
            except Exception as e:
                results.append({
                    "doc_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        return jsonify({
            "code": 0,
            "data": results,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Batch extract error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


# ============================================================================
# Langextract 提取接口
# ============================================================================

@powerrag_bp.route("/struct_extract/submit", methods=["POST"])
@apikey_required
def submit_extraction_task(tenant_id):
    """
    Submit a langextract extraction task
    
    Authentication: Requires RAGFlow API key in Authorization header (Bearer token)
    
    Request JSON:
    {
        "text_or_documents": "Text content or URL" OR [
            {
                "text": "Document text content",
                "document_id": "doc1",  // optional, auto-generated if not set
                "additional_context": "Additional context for this document"  // optional
            },
            {
                "text": "Another document text",
                "document_id": "doc2"
            }
        ],
        "prompt_description": "Extract names, locations, and dates from the text.",
        "examples": [
            {
                "text": "John attended a conference in New York on January 1, 2024.",
                "extractions": [
                    {
                        "extraction_class": "name",
                        "extraction_text": "John"
                    },
                    {
                        "extraction_class": "location",
                        "extraction_text": "New York"
                    },
                    {
                        "extraction_class": "date",
                        "extraction_text": "January 1, 2024"
                    }
                ]
            }
        ],
        "fetch_urls": false,
        "max_char_buffer": 1000,
        "temperature": 0.3,
        "extraction_passes": 1,
        "additional_context": "Additional context string",
        "prompt_validation_level": "WARNING",
        "prompt_validation_strict": false,
        "resolver_params": {
            "enable_fuzzy_alignment": true,
            "fuzzy_alignment_threshold": 0.75
        },
        "model_parameters": {
            "max_tokens": 4096
        },
        "tenant_id": "optional_tenant_id",
        "timeout": 1800
    }
    
    Response:
    {
        "code": 0,
        "data": {
            "task_id": "uuid-string"
        },
        "message": "Task submitted successfully"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 400,
                "message": "No JSON data provided"
            }), 400
        
        # Required parameters
        text_or_documents = data.get("text_or_documents")
        prompt_description = data.get("prompt_description")
        examples = data.get("examples", [])
        
        if not text_or_documents:
            return jsonify({
                "code": 400,
                "message": "text_or_documents is required"
            }), 400
        
        if not prompt_description:
            return jsonify({
                "code": 400,
                "message": "prompt_description is required"
            }), 400
        
        if not examples or len(examples) == 0:
            return jsonify({
                "code": 400,
                "message": "examples is required and must not be empty"
            }), 400
        
        # Convert document list to lx.data.Document objects if needed
        if isinstance(text_or_documents, list):
            # Convert list of dicts to list of Document objects
            document_objects = []
            for doc_dict in text_or_documents:
                if not isinstance(doc_dict, dict):
                    return jsonify({
                        "code": 400,
                        "message": "Each item in text_or_documents list must be a dictionary with 'text' field"
                    }), 400
                
                if "text" not in doc_dict:
                    return jsonify({
                        "code": 400,
                        "message": "Each document in text_or_documents list must have a 'text' field"
                    }), 400
                
                # Create Document object
                doc_obj = lx.data.Document(
                    text=doc_dict["text"],
                    document_id=doc_dict.get("document_id"),  # Optional, auto-generated if None
                    additional_context=doc_dict.get("additional_context")  # Optional
                )
                document_objects.append(doc_obj)
            
            text_or_documents = document_objects
        
        # Optional parameters
        fetch_urls = data.get("fetch_urls", False)
        max_char_buffer = data.get("max_char_buffer", 1000)
        temperature = data.get("temperature")
        extraction_passes = data.get("extraction_passes", 1)
        additional_context = data.get("additional_context")
        prompt_validation_level = data.get("prompt_validation_level", "WARNING")
        prompt_validation_strict = data.get("prompt_validation_strict", False)
        resolver_params = data.get("resolver_params")
        model_parameters = data.get("model_parameters")
        timeout = data.get("timeout")
        
        # Get debug mode from logging level
        debug = logger.level <= logging.DEBUG
        
        # Get service instance
        from powerrag.server.services.langextract_service import get_langextract_service, ServerBusyError
        service = get_langextract_service()
        
        # Submit task
        try:
            task_id = service.submit_task(
                text_or_documents=text_or_documents,
                prompt_description=prompt_description,
                examples=examples,
                fetch_urls=fetch_urls,
                max_char_buffer=max_char_buffer,
                temperature=temperature,
                extraction_passes=extraction_passes,
                additional_context=additional_context,
                prompt_validation_level=prompt_validation_level,
                prompt_validation_strict=prompt_validation_strict,
                resolver_params=resolver_params,
                model_parameters=model_parameters,
                tenant_id=tenant_id,
                debug=debug,
                timeout=timeout
            )
            
            return jsonify({
                "code": 0,
                "data": {
                    "task_id": task_id
                },
                "message": "Task submitted successfully"
            }), 200
        
        except ServerBusyError as e:
            # Server busy error
            return jsonify({
                "code": 503,
                "message": str(e)
            }), 503
        
    except Exception as e:
        logger.error(f"Submit extraction task error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@powerrag_bp.route("/struct_extract/status/<task_id>", methods=["GET"])
@apikey_required
def get_extraction_status(task_id):
    """
    Get extraction task status
    
    Authentication: Requires RAGFlow API key in Authorization header (Bearer token)
    
    Response:
    {
        "code": 0,
        "data": {
            "task_id": "uuid-string",
            "status": "pending|processing|success|failed|not_found",
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "result": {
                "extractions": [...]
            },
            "error": "Error message if failed"
        },
        "message": "success"
    }
    """
    try:
        from powerrag.server.services.langextract_service import get_langextract_service
        service = get_langextract_service()
        
        status = service.get_task_status(task_id)
        
        if status.get("status") == "not_found":
            return jsonify({
                "code": 404,
                "message": "Task not found",
                "data": status
            }), 404
        
        return jsonify({
            "code": 0,
            "data": status,
            "message": "success"
        }), 200
        
    except Exception as e:
        logger.error(f"Get extraction status error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500

