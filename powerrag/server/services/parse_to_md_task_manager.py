"""
Parse to Markdown Task Manager

Manages async tasks for parse_to_md operations.
Provides task submission, status tracking, and result retrieval.
"""

import uuid
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"


class ParseToMdTaskManager:
    """
    Singleton task manager for parse_to_md async operations.
    
    Features:
    - Thread-safe task storage
    - Async task execution with thread pool
    - Task status tracking
    - Result caching (max 1000 completed tasks)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.tasks = {}  # task_id -> task_info
        self.tasks_lock = threading.Lock()
        
        # Thread pool for async execution (max 4 concurrent tasks)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="parse_to_md_worker")
        
        # Max cached completed tasks (to prevent memory leak)
        self.max_cached_tasks = 1000
        
        logger.info("ParseToMdTaskManager initialized")
    
    def submit_task(
        self,
        service,
        method_name: str,
        **kwargs
    ) -> str:
        """
        Submit a parse_to_md task for async execution
        
        Args:
            service: The ParseService instance
            method_name: Method name to call ("parse_to_md" or "parse_to_md_upload")
            **kwargs: Arguments to pass to the method
        
        Returns:
            task_id: Unique task identifier
        """
        task_id = str(uuid.uuid4())
        
        with self.tasks_lock:
            # Clean up old tasks if needed
            if len(self.tasks) > self.max_cached_tasks:
                self._cleanup_old_tasks()
            
            # Create task info
            self.tasks[task_id] = {
                "task_id": task_id,
                "status": TaskStatus.PENDING.value,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "method": method_name,
                "kwargs": kwargs,
                "result": None,
                "error": None
            }
        
        # Submit to thread pool
        future = self.executor.submit(self._execute_task, task_id, service, method_name, kwargs)
        
        logger.info(f"Task {task_id} submitted for {method_name}")
        
        return task_id
    
    def _execute_task(
        self,
        task_id: str,
        service,
        method_name: str,
        kwargs: Dict[str, Any]
    ):
        """
        Execute the parse task in background thread
        
        Args:
            task_id: Task ID
            service: ParseService instance
            method_name: Method to call
            kwargs: Method arguments
        """
        try:
            # Update status to processing
            self._update_task_status(task_id, TaskStatus.PROCESSING)
            
            # Call the actual method
            if method_name == "parse_to_md":
                result = service._parse_to_markdown_for_task(**kwargs)
            elif method_name == "parse_to_md_upload":
                result = service._parse_to_markdown_for_task(**kwargs)
            else:
                raise ValueError(f"Unknown method: {method_name}")
            
            # Update with success result
            with self.tasks_lock:
                if task_id in self.tasks:
                    self.tasks[task_id].update({
                        "status": TaskStatus.SUCCESS.value,
                        "updated_at": datetime.now().isoformat(),
                        "result": result
                    })
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            # Update with error
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            
            with self.tasks_lock:
                if task_id in self.tasks:
                    self.tasks[task_id].update({
                        "status": TaskStatus.FAILED.value,
                        "updated_at": datetime.now().isoformat(),
                        "error": str(e)
                    })
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and result
        
        Args:
            task_id: Task ID
        
        Returns:
            Task information dict
        """
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            
            if not task:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.NOT_FOUND.value
                }
            
            # Return a copy to avoid external modifications
            return {
                "task_id": task["task_id"],
                "status": task["status"],
                "created_at": task["created_at"],
                "updated_at": task["updated_at"],
                "result": task.get("result"),
                "error": task.get("error")
            }
    
    def _update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status"""
        with self.tasks_lock:
            if task_id in self.tasks:
                self.tasks[task_id].update({
                    "status": status.value,
                    "updated_at": datetime.now().isoformat()
                })
    
    def _cleanup_old_tasks(self):
        """
        Clean up old completed/failed tasks to prevent memory leak.
        Keeps only the most recent tasks.
        """
        # Get completed/failed tasks
        completed_tasks = [
            (tid, t["updated_at"]) 
            for tid, t in self.tasks.items() 
            if t["status"] in [TaskStatus.SUCCESS.value, TaskStatus.FAILED.value]
        ]
        
        # Sort by updated_at (oldest first)
        completed_tasks.sort(key=lambda x: x[1])
        
        # Remove oldest 20% of tasks
        num_to_remove = max(1, len(completed_tasks) // 5)
        for i in range(num_to_remove):
            task_id = completed_tasks[i][0]
            del self.tasks[task_id]
            logger.debug(f"Cleaned up old task {task_id}")
    
    def shutdown(self):
        """Shutdown the task manager and thread pool"""
        logger.info("Shutting down ParseToMdTaskManager")
        self.executor.shutdown(wait=True)


# Singleton instance
_task_manager = None


def get_task_manager() -> ParseToMdTaskManager:
    """Get the singleton task manager instance"""
    global _task_manager
    if _task_manager is None:
        _task_manager = ParseToMdTaskManager()
    return _task_manager

