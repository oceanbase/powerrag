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
PowerRAG Task Queue Routes

These routes allow submitting parsing tasks to the task_executor queue
instead of processing them synchronously in the HTTP service.
"""

import logging
from flask import Blueprint, request, jsonify

from powerrag.server.services.task_queue_service import PowerRAGTaskQueueService

logger = logging.getLogger(__name__)

task_bp = Blueprint("powerrag_tasks", __name__)


@task_bp.route("/parse/async", methods=["POST"])
def parse_document_async():
    """
    Create an async parsing task using task_executor
    
    This endpoint creates a task in the RAGFlow task queue system.
    The task will be processed asynchronously by task_executor workers.
    
    Request Body:
        {
            "doc_id": "document_id",
            "config": {
                "title_level": 3,
                "chunk_token_num": 256,
                "layout_recognize": "mineru"
            },
            "priority": 0  // 0=normal, 1=high
        }
    
    Response:
        {
            "code": 0,
            "data": {
                "task_id": "task_uuid",
                "doc_id": "document_id",
                "status": "queued"
            },
            "message": "Task created successfully"
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
        if not doc_id:
            return jsonify({
                "code": 400,
                "message": "doc_id is required"
            }), 400
        
        config = data.get("config", {})
        priority = data.get("priority", 0)
        
        # Create task
        result = PowerRAGTaskQueueService.create_parse_task(
            doc_id=doc_id,
            config=config,
            priority=priority
        )
        
        if result["success"]:
            return jsonify({
                "code": 0,
                "data": {
                    "task_id": result["task_id"],
                    "doc_id": result["doc_id"],
                    "status": result["status"]
                },
                "message": result["message"]
            }), 200
        else:
            return jsonify({
                "code": 500,
                "message": result.get("error", "Failed to create task")
            }), 500
            
    except Exception as e:
        logger.error(f"Parse async error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@task_bp.route("/task/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """
    Get task status and progress
    
    Response:
        {
            "code": 0,
            "data": {
                "task_id": "task_uuid",
                "doc_id": "document_id",
                "status": "processing",  // pending, processing, completed, failed
                "progress": 0.5,          // 0.0 - 1.0
                "progress_msg": "Parsing page 5/10..."
            }
        }
    """
    try:
        result = PowerRAGTaskQueueService.get_task_status(task_id)
        
        if result["success"]:
            return jsonify({
                "code": 0,
                "data": result
            }), 200
        else:
            return jsonify({
                "code": 404,
                "message": result.get("error", "Task not found")
            }), 404
            
    except Exception as e:
        logger.error(f"Get task status error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@task_bp.route("/task/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    """
    Cancel a running task
    
    Response:
        {
            "code": 0,
            "message": "Task canceled successfully"
        }
    """
    try:
        result = PowerRAGTaskQueueService.cancel_task(task_id)
        
        if result["success"]:
            return jsonify({
                "code": 0,
                "message": result["message"]
            }), 200
        else:
            return jsonify({
                "code": 500,
                "message": result.get("error", "Failed to cancel task")
            }), 500
            
    except Exception as e:
        logger.error(f"Cancel task error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500


@task_bp.route("/document/<doc_id>/chunks", methods=["GET"])
def get_document_chunks(doc_id):
    """
    Get parsed chunks for a completed document
    
    Response:
        {
            "code": 0,
            "data": {
                "doc_id": "document_id",
                "doc_name": "file.pdf",
                "total_chunks": 42,
                "chunks": [
                    {
                        "content": "chunk text...",
                        "title": "Section Title",
                        "page": 1
                    },
                    ...
                ]
            }
        }
    """
    try:
        result = PowerRAGTaskQueueService.get_document_chunks(doc_id)
        
        if result["success"]:
            return jsonify({
                "code": 0,
                "data": result
            }), 200
        else:
            return jsonify({
                "code": 500,
                "message": result.get("error", "Failed to get chunks")
            }), 500
            
    except Exception as e:
        logger.error(f"Get chunks error: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "message": str(e)
        }), 500

