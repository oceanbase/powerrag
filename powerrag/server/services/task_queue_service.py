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
PowerRAG Task Queue Service

This service creates tasks in the RAGFlow task queue system,
allowing PowerRAG parsing to be handled asynchronously by task_executor.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.task_service import TaskService, queue_tasks
from api.db.services.file2document_service import File2DocumentService
from api.db import ParserType
from api.utils import get_uuid
from rag.settings import get_svr_queue_name
from rag.utils.redis_conn import REDIS_CONN

logger = logging.getLogger(__name__)


class PowerRAGTaskQueueService:
    """
    Service for creating and managing PowerRAG parsing tasks
    
    This service allows PowerRAG HTTP API to create tasks that will be
    processed asynchronously by task_executor with the title parser.
    """
    
    @staticmethod
    def create_parse_task(doc_id: str, config: Dict[str, Any] = None, 
                         priority: int = 0) -> Dict[str, Any]:
        """
        Create a PowerRAG parsing task for async processing
        
        Args:
            doc_id: Document ID to parse
            config: Parser configuration (optional)
            priority: Task priority (0=normal, 1=high)
            
        Returns:
            Dict with task_id and status
            
        Example:
            >>> result = PowerRAGTaskQueueService.create_parse_task(
            ...     doc_id="doc_123",
            ...     config={"title_level": 3, "chunk_token_num": 256}
            ... )
            >>> print(result["task_id"])
        """
        try:
            # Get document info
            exist, doc = DocumentService.get_by_id(doc_id)
            if not exist:
                raise ValueError(f"Document {doc_id} not found")
            
            # Get knowledge base info
            kb_id = DocumentService.get_knowledgebase_id(doc_id)
            exist, kb = KnowledgebaseService.get_by_id(kb_id)
            if not exist:
                raise ValueError(f"Knowledge base {kb_id} not found")
            
            # Get storage location
            bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
            
            # Update document to use title parser
            parser_config = config or {}
            parser_config.update({
                "title_level": parser_config.get("title_level", 3),
                "layout_recognize": "mineru",
                "chunk_token_num": parser_config.get("chunk_token_num", 256)
            })
            
            # Update document parser settings
            DocumentService.update_by_id(doc_id, {
                "parser_id": ParserType.TITLE.value,
                "parser_config": parser_config
            })
            
            # Create task using RAGFlow's queue_tasks
            doc_dict = {
                "id": doc_id,
                "kb_id": kb_id,
                "parser_id": ParserType.TITLE.value,
                "parser_config": parser_config,
                "name": doc.name,
                "type": doc.type,
                "location": f"{bucket}/{name}",
                "size": doc.size,
                "tenant_id": doc.tenant_id,
                "embd_id": kb.embd_id,
                "language": kb.language,
                "llm_id": kb.llm_id
            }
            
            # Queue the task
            queue_tasks(doc_dict, bucket, name, priority)
            
            # Get the created task
            tasks = TaskService.get_tasks(doc_id)
            if tasks:
                task = tasks[0]
                return {
                    "success": True,
                    "task_id": task["id"],
                    "doc_id": doc_id,
                    "status": "queued",
                    "message": "Task created successfully"
                }
            else:
                raise Exception("Failed to create task")
                
        except Exception as e:
            logger.error(f"Failed to create parse task for {doc_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create task"
            }
    
    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """
        Get task status and progress
        
        Args:
            task_id: Task ID
            
        Returns:
            Dict with task status and progress
        """
        try:
            task = TaskService.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "error": "Task not found"
                }
            
            return {
                "success": True,
                "task_id": task_id,
                "doc_id": task["doc_id"],
                "progress": task.get("progress", 0),
                "progress_msg": task.get("progress_msg", ""),
                "status": PowerRAGTaskQueueService._get_task_status_text(task),
                "create_time": task.get("create_time", ""),
                "update_time": task.get("update_time", "")
            }
        except Exception as e:
            logger.error(f"Failed to get task status {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_document_chunks(doc_id: str) -> Dict[str, Any]:
        """
        Get parsed chunks for a document
        
        Args:
            doc_id: Document ID
            
        Returns:
            Dict with chunks data
        """
        try:
            # Get document info
            exist, doc = DocumentService.get_by_id(doc_id)
            if not exist:
                return {
                    "success": False,
                    "error": "Document not found"
                }
            
            # Check if parsing is complete
            tasks = TaskService.get_tasks(doc_id)
            if not tasks or tasks[0].get("progress", 0) < 1.0:
                return {
                    "success": False,
                    "error": "Document not fully parsed yet"
                }
            
            # Get chunks from document store
            from rag import settings
            from rag.nlp import search
            
            kb_id = DocumentService.get_knowledgebase_id(doc_id)
            exist, kb = KnowledgebaseService.get_by_id(kb_id)
            if not exist:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            # Retrieve chunks
            chunks = settings.retriever.chunk_list(
                doc_id=doc_id,
                tenant_id=doc.tenant_id,
                kb_ids=[kb_id],
                fields=["content_with_weight", "page_num_int", "title_kwd"],
                sort_by_position=True
            )
            
            return {
                "success": True,
                "doc_id": doc_id,
                "doc_name": doc.name,
                "total_chunks": len(chunks),
                "chunks": [
                    {
                        "content": chunk.get("content_with_weight", ""),
                        "title": chunk.get("title_kwd", ""),
                        "page": chunk.get("page_num_int", [1])[0] if chunk.get("page_num_int") else 1
                    }
                    for chunk in chunks
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get chunks for {doc_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def cancel_task(task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            Dict with cancellation result
        """
        try:
            task = TaskService.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "error": "Task not found"
                }
            
            # Update task status to canceled
            TaskService.update_progress(task_id, {
                "progress": -1,
                "progress_msg": "Task canceled by user"
            })
            
            return {
                "success": True,
                "task_id": task_id,
                "message": "Task canceled successfully"
            }
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def _get_task_status_text(task: Dict) -> str:
        """
        Convert task progress to status text
        """
        progress = task.get("progress", 0)
        
        if progress < 0:
            return "failed"
        elif progress == 0:
            return "pending"
        elif progress < 1.0:
            return "processing"
        else:
            return "completed"

