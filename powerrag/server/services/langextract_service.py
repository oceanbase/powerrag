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

"""PowerRAG Langextract Service - Provides langextract extraction API"""

import os
import logging
import traceback
import uuid
import threading
import requests
from typing import Dict, Any, Optional, List, Union
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime

import langextract as lx
from langextract import factory
from langextract import data_lib
from langextract import prompt_validation
import dataclasses

from api import settings
from api.db.services.tenant_llm_service import TenantLLMService
from api.db import LLMType
from rag.llm import SupportedLiteLLMProvider, FACTORY_DEFAULT_BASE_URL

logger = logging.getLogger(__name__)


class ServerBusyError(Exception):
    """Exception raised when server is busy (insufficient workers available)"""
    
    def __init__(self, required_workers: int, available_workers: int):
        self.required_workers = required_workers
        self.available_workers = available_workers
        message = f"Server busy: required {required_workers} workers, but only {available_workers} available"
        super().__init__(message)


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"


@dataclass
class ExtractionTask:
    """Extraction task data structure"""
    task_id: str
    status: TaskStatus
    text_or_documents: Union[str, List[Any]]  # Can be text string or list of Document objects
    prompt_description: str
    examples: List[Dict[str, Any]]
    config: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    max_workers: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        result = asdict(self)
        result['status'] = self.status.value
        result['created_at'] = self.created_at.isoformat() if self.created_at else None
        result['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return result


class LangextractService:
    """Service for langextract extraction with task management"""
    
    # Maximum extract workers across all tasks
    MAX_EXTRACT_WORKS = int(os.environ.get("MAX_EXTRACT_WORKS", "20"))
    # Default task timeout in seconds (30 minutes)
    DEFAULT_TASK_TIMEOUT = int(os.environ.get("LANGEXTRACT_TASK_TIMEOUT", "1800"))
    
    def __init__(self):
        """Initialize the service"""
        self.tasks: Dict[str, ExtractionTask] = {}
        self.tasks_lock = threading.Lock()
        self.used_workers = 0  # Currently used workers
        self.workers_lock = threading.Lock()
        # Thread pool for processing extraction tasks
        self.executor = ThreadPoolExecutor(max_workers=self.MAX_EXTRACT_WORKS, thread_name_prefix="langextract")
        # Store futures for timeout monitoring
        self.task_futures: Dict[str, Future] = {}
        logger.info(f"LangextractService initialized with MAX_EXTRACT_WORKS={self.MAX_EXTRACT_WORKS}, DEFAULT_TASK_TIMEOUT={self.DEFAULT_TASK_TIMEOUT}s")
    
    def _get_ragflow_llm_config(self, tenant_id: Optional[str] = None, llm_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get RAGFlow LLM configuration
        
        Args:
            tenant_id: Optional tenant ID, if None uses default settings
            llm_id: Optional LLM ID, if provided uses this specific model
            
        Returns:
            Dict with model configuration: {model, factory, api_key, base_url}
        """
        if not tenant_id:
            raise Exception("Tenant ID is required to get RAGFlow LLM config")
        
        # If llm_id is provided, use it to get specific model config
        if llm_id:
            llm_type = TenantLLMService.llm_id2llm_type(llm_id)
            if llm_type:
                llm_config = TenantLLMService.get_model_config(tenant_id, llm_type, llm_id)
                if llm_config:
                    # Get model name and factory
                    model_name = llm_config.get("llm_name", "")
                    factory_name = llm_config.get("llm_factory", "")
                    
                    # If model_name contains @factory format, extract it
                    if "@" in model_name:
                        model_name, factory_name = TenantLLMService.split_model_name_and_factory(model_name)
                    model_name = TenantLLMService.get_pure_model_name(factory_name, model_name)

                    return {
                        "model": model_name,
                        "factory": factory_name,
                        "api_key": llm_config.get("api_key", ""),
                        "base_url": llm_config.get("api_base", "")
                    }
        
        # Get tenant-specific default LLM config
        llm_config = TenantLLMService.get_model_config(tenant_id, LLMType.CHAT)
        if llm_config:
            # Get model name and factory
            model_name = llm_config.get("llm_name", "")
            factory_name = llm_config.get("llm_factory", "")
            
            # If model_name contains @factory format, extract it
            if "@" in model_name:
                model_name, factory_name = TenantLLMService.split_model_name_and_factory(model_name)
            model_name = TenantLLMService.get_pure_model_name(factory_name, model_name)

            return {
                "model": model_name,
                "factory": factory_name,
                "api_key": llm_config.get("api_key", ""),
                "base_url": llm_config.get("api_base", "")
            }
        
        # Fallback to default settings
        model_name = settings.CHAT_MDL
        factory_name = settings.CHAT_CFG.get("factory", "")
        
        # If model_name contains @factory format, extract it
        if "@" in model_name:
            model_name, factory_name = TenantLLMService.split_model_name_and_factory(model_name)
        model_name = TenantLLMService.get_pure_model_name(factory_name, model_name)
        
        return {
            "model": model_name,
            "factory": factory_name or settings.CHAT_CFG.get("factory", ""),
            "api_key": settings.CHAT_CFG.get("api_key", ""),
            "base_url": settings.CHAT_CFG.get("base_url", "")
        }
    
    def _convert_to_langextract_config(self, ragflow_config: Dict[str, Any], 
                                       model_parameters: Dict[str, Any] = None) -> factory.ModelConfig:
        """
        Convert RAGFlow LLM configuration to langextract ModelConfig
        
        Args:
            ragflow_config: RAGFlow model config dict
            model_parameters: Additional model parameters from request
            
        Returns:
            langextract factory.ModelConfig
        """
        model_id = ragflow_config.get("model", "")
        factory_name = ragflow_config.get("factory", "")
        api_key = ragflow_config.get("api_key", "")
        base_url = ragflow_config.get("base_url", "")
        
        # Extract model name if it contains @factory format
        if "@" in model_id:
            model_id, factory_name = model_id.split("@", 1)
        
        # Prepare provider kwargs
        provider_kwargs = {}
        if api_key:
            provider_kwargs["api_key"] = api_key

        if not factory_name:
            raise Exception("Cannot determine provider from factory name, please check the model configuration")
        
        # Determine provider based on factory name
        provider = None
        
        # Handle OpenAI separately
        if factory_name.lower() == "openai":
            provider = "OpenAILanguageModel"
            # Only set base_url if provided, otherwise use default
            if base_url:
                provider_kwargs["base_url"] = base_url
        # OpenAI-API-Compatible is a special case, it's actually OpenAI, so we use OpenAI provider
        elif factory_name.lower() == "openai-api-compatible":
            provider = "OpenAILanguageModel"
            if base_url:
                provider_kwargs["base_url"] = base_url
        # Try to get provider from SupportedLiteLLMProvider enum
        else:
            matched_provider = None
            try:
                # Try to create enum from factory name
                matched_provider = SupportedLiteLLMProvider(factory_name)
            except ValueError:
                # If factory_name doesn't match enum value, try case-insensitive match
                factory_lower = factory_name.lower()
                for provider_enum in SupportedLiteLLMProvider:
                    if provider_enum.value.lower() == factory_lower:
                        matched_provider = provider_enum
                        break
                
            if not matched_provider:
                raise Exception(f"Unsupported provider: {factory_name}")
                
            # Handle Gemini
            if matched_provider == SupportedLiteLLMProvider.Gemini:
                provider = "GeminiLanguageModel"
                if base_url:
                    provider_kwargs["base_url"] = base_url
            # Handle Ollama
            elif matched_provider == SupportedLiteLLMProvider.Ollama:
                provider = "OllamaLanguageModel"
                if base_url:
                    provider_kwargs["model_url"] = base_url
                provider_kwargs["api_key"] = api_key or ""
                provider_kwargs["auth_scheme"] = "Bearer"
                provider_kwargs["auth_header"] = "Authorization"
            # Handle OpenAI-compatible (default for other providers)
            else:
                provider = "OpenAILanguageModel"
                # Get base_url from FACTORY_DEFAULT_BASE_URL if not provided
                if not base_url and matched_provider:
                    base_url = FACTORY_DEFAULT_BASE_URL.get(matched_provider, "")
                if base_url:
                    provider_kwargs["base_url"] = base_url 
        # Add model_parameters if provided
        if model_parameters:
            provider_kwargs.update(model_parameters)
        
        # Ensure providers are loaded
        lx.providers.load_builtins_once()
        lx.providers.load_plugins_once()
        
        # Create ModelConfig
        config = factory.ModelConfig(
            model_id=model_id,
            provider=provider,
            provider_kwargs=provider_kwargs
        )
        
        return config
    
    def _download_url_content(self, url: str) -> str:
        """
        Download content from URL and extract text
        
        Args:
            url: URL to download
            
        Returns:
            Extracted text content
        """
        try:
            # Use requests to download
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Handle HTML
            if 'html' in content_type or url.endswith(('.html', '.htm')):
                # Try to extract text from HTML
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                return text
            
            # Handle plain text
            elif 'text' in content_type:
                return response.text
            
            # Try to parse as text anyway
            else:
                try:
                    return response.text
                except:
                    # If text parsing fails, try to use RAGFlow's parser
                    from powerrag.server.services.parse_service import PowerRAGParseService
                    service = PowerRAGParseService()
                    # This would need binary content, so we'll just return the text
                    return response.text
        
        except Exception as e:
            logger.error(f"Error downloading URL {url}: {e}", exc_info=True)
            raise Exception(f"Failed to download URL: {str(e)}")
    
    def _estimate_chunk_size(self, text: str, max_char_buffer: int) -> int:
        """
        Estimate chunk size based on text length and max_char_buffer
        
        Args:
            text: Input text
            max_char_buffer: Maximum character buffer per chunk
            
        Returns:
            Estimated number of chunks
        """
        if max_char_buffer <= 0:
            return 1
        # Rough estimation: assume 4 characters per token
        estimated_tokens = len(text) / 4
        estimated_chunks = int(estimated_tokens / max_char_buffer) + 1
        return max(1, estimated_chunks)
    
    def _calculate_max_workers(self, text_or_documents: Union[str, List[Any]], max_char_buffer: int) -> int:
        """
        Calculate max_workers based on text or documents and max_char_buffer
        
        Args:
            text_or_documents: Input text string or list of Document objects
            max_char_buffer: Maximum character buffer
            
        Returns:
            Number of workers to use
        """
        if isinstance(text_or_documents, list):
            # For document lists, use the number of documents as a base
            num_docs = len(text_or_documents)
            max_workers = min(num_docs, 20)  # Cap at 20 workers
            return max(1, max_workers)
        else:
            # For text strings, use existing logic
            estimate_chunk_size = self._estimate_chunk_size(text_or_documents, max_char_buffer)
            max_workers = min(int(estimate_chunk_size / 3), 5)
            return max(1, max_workers)

    def _convert_extraction_result(self, result: Any, is_list_input: bool) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Convert langextract extraction result to dict format.
        This is a shared method used by both sync and async extraction.
        
        Args:
            result: Extraction result from lx.extract() (can be single result or list)
            is_list_input: Whether the input was a list (determines output format)
            
        Returns:
            Dict with extractions (single input) or List of dicts (multiple inputs)
            Format: {"extractions": [...], "document_id": ..., "text": ...} 
                    or [{"extractions": [...], "document_id": ..., "text": ...}, ...]
        """
        if is_list_input:
            output_result = []
            for item in result:
                extractions_dict = [
                    dataclasses.asdict(extraction, dict_factory=data_lib.enum_asdict_factory)
                    for extraction in item.extractions
                ]
                output_result.append({
                    "document_id": getattr(item, "document_id", None),
                    "extractions": extractions_dict,
                    "text": getattr(item, "text", None),
                })
            return output_result
        else:
            extractions_dict = [
                dataclasses.asdict(extraction, dict_factory=data_lib.enum_asdict_factory)
                for extraction in result.extractions
            ]
            output_result = {
                "document_id": getattr(result, "document_id", None),
                "extractions": extractions_dict,
            }
            return output_result
    
    def _do_extract(self, text_or_documents: Union[str, List[Any]], 
                                    prompt_description: str,
                                    examples: List[Dict[str, Any]],
                                    max_char_buffer: int = 1000,
                                    temperature: Optional[float] = None,
                                    extraction_passes: int = 1,
                                    additional_context: Optional[str] = None,
                                    prompt_validation_level: str = "WARNING",
                                    prompt_validation_strict: bool = False,
                                    resolver_params: Optional[Dict[str, Any]] = None,
                                    model_parameters: Optional[Dict[str, Any]] = None,
                                    tenant_id: Optional[str] = None,
                                    llm_id: Optional[str] = None,
                                    max_workers: Optional[int] = None,
                                    batch_length: int = 10000000,
                                    use_schema_constraints: bool = True,
                                    fetch_urls: bool = False,
                                    debug: bool = False) -> Dict[str, Any] | List[Dict[str, Any]]:
        """
        Perform extraction and convert results to standardized dictionary format.

        Args:
            text_or_documents: Input text string or list of Document objects to extract from.
            prompt_description: Prompt describing the extraction task.
            examples: List of example data dictionaries for few-shot extraction.
            max_char_buffer: Maximum character buffer for a single extraction operation.
            temperature: Sampling temperature parameter for LLM.
            extraction_passes: Number of sequential extraction passes (for improved recall).
            additional_context: Optional additional context string for the extractor.
            prompt_validation_level: Prompt validation level; one of "OFF", "WARNING", or "ERROR".
            prompt_validation_strict: If True, enforce strict prompt validation.
            resolver_params: Optional parameters to pass to the extraction resolver.
            model_parameters: Additional model parameters for LLM, if any.
            tenant_id: Optional tenant ID for LLM/model configuration.
            llm_id: Optional LLM ID to use a specific model.
            max_workers: Optional maximum number of parallel workers (default: auto-calculated).
            batch_length: Batch length for document or chunk batching.
            use_schema_constraints: Whether to use schema-based constraints during extraction.
            fetch_urls: Whether to fetch content from URLs in the documents (default: False).
            debug: Enable debug mode.

        Returns:
            A dictionary or list of dictionaries representing the extraction results,
            compatible with the output format of langextract.
        """
        # Get RAGFlow LLM config
        ragflow_config = self._get_ragflow_llm_config(tenant_id, llm_id)
        
        # Convert to langextract config
        lx_config = self._convert_to_langextract_config(
            ragflow_config,
            model_parameters
        )
        
        # Convert examples to ExampleData objects
        example_objects = []
        if examples:
            for ex in examples:
                extractions = []
                for ext in ex.get("extractions", []):
                    ext_obj = lx.data.Extraction(
                        extraction_class=ext.get("extraction_class", ""),
                        extraction_text=ext.get("extraction_text", ""),
                        char_interval=ext.get("char_interval"),
                        alignment_status=ext.get("alignment_status"),
                        extraction_index=ext.get("extraction_index"),
                        group_index=ext.get("group_index", 0),
                        description=ext.get("description"),
                        attributes=ext.get("attributes", {})
                    )
                    extractions.append(ext_obj)
                
                ex_obj = lx.data.ExampleData(
                    text=ex.get("text", ""),
                    extractions=extractions
                )
                example_objects.append(ex_obj)
        
        # Set prompt validation level
        pv_level_map = {
            "OFF": prompt_validation.PromptValidationLevel.OFF,
            "WARNING": prompt_validation.PromptValidationLevel.WARNING,
            "ERROR": prompt_validation.PromptValidationLevel.ERROR
        }
        pv_level = pv_level_map.get(prompt_validation_level, prompt_validation.PromptValidationLevel.WARNING)
        
        # Calculate max_workers if not provided
        if max_workers is None:
            max_workers = self._calculate_max_workers(text_or_documents, max_char_buffer)
        
        # Prepare extract parameters
        extract_params = {
            "text_or_documents": text_or_documents,
            "prompt_description": prompt_description,
            "examples": example_objects,
            "config": lx_config,
            "use_schema_constraints": use_schema_constraints,
            "batch_length": batch_length,
            "max_workers": max_workers,
            "max_char_buffer": max_char_buffer,
            "extraction_passes": extraction_passes,
            "prompt_validation_level": pv_level,
            "prompt_validation_strict": prompt_validation_strict,
            "debug": debug,
            "fetch_urls": fetch_urls
        }
        
        # Add optional parameters
        if temperature is not None:
            extract_params["temperature"] = temperature
        if additional_context:
            extract_params["additional_context"] = additional_context
        if resolver_params:
            extract_params["resolver_params"] = resolver_params
        
        logger.debug(f"Running langextract with {extract_params.get('max_workers', 'unknown')} workers")
        # Run extraction
        result = lx.extract(**extract_params)

        is_list_input = isinstance(text_or_documents, list)
        # Convert result to dict format using shared method
        return self._convert_extraction_result(result, is_list_input)

   

    def extract_sync(self, text_or_documents: Union[str, List[Any]], prompt_description: str,
                     examples: List[Dict[str, Any]] = None, max_char_buffer: int = 1000,
                     temperature: Optional[float] = None, extraction_passes: int = 1,
                     additional_context: Optional[str] = None,
                     prompt_validation_level: str = "WARNING",
                     prompt_validation_strict: bool = False,
                     resolver_params: Optional[Dict[str, Any]] = None,
                     model_parameters: Optional[Dict[str, Any]] = None,
                     tenant_id: Optional[str] = None,
                     llm_id: Optional[str] = None,
                     debug: bool = False) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Synchronous extraction interface for direct use by Extractor nodes.
        
        Args:
            text_or_documents: Text string or list of text strings to extract from
            prompt_description: Extraction prompt description
            examples: List of example data dicts
            max_char_buffer: Maximum character buffer
            temperature: Sampling temperature
            extraction_passes: Number of extraction passes
            additional_context: Additional context string
            prompt_validation_level: Prompt validation level
            prompt_validation_strict: Whether to use strict validation
            resolver_params: Resolver parameters
            model_parameters: Additional model parameters
            tenant_id: Optional tenant ID for LLM config
            llm_id: Optional LLM ID to use specific model
            debug: Debug mode
            
        Returns:
            Dict with extractions (single text) or List of dicts (multiple texts)
            Format: {"extractions": [...]} or [{"extractions": [...]}, ...]
        """
    
        # Prepare extraction parameters using shared method
        max_workers = self._calculate_max_workers(text_or_documents, max_char_buffer)
        # Limit max_workers to avoid resource exhaustion in synchronous calls
        max_workers = min(max_workers, 5)
        
        return self._do_extract(
            text_or_documents=text_or_documents,
            prompt_description=prompt_description,
            examples=examples or [],
            max_char_buffer=max_char_buffer,
            temperature=temperature,
            extraction_passes=extraction_passes,
            additional_context=additional_context,
            prompt_validation_level=prompt_validation_level,
            prompt_validation_strict=prompt_validation_strict,
            resolver_params=resolver_params,
            model_parameters=model_parameters,
            tenant_id=tenant_id,
            llm_id=llm_id,
            max_workers=max_workers,
            batch_length=10000000,  # Large value to process all at once
            use_schema_constraints=True,
            fetch_urls=False,
            debug=debug
        )
    
    def submit_task(self, text_or_documents: Union[str, List[Any]], prompt_description: str, 
                   examples: List[Dict[str, Any]], fetch_urls: bool = False,
                   max_char_buffer: int = 1000, temperature: Optional[float] = None,
                   extraction_passes: int = 1, additional_context: Optional[str] = None,
                   prompt_validation_level: str = "WARNING",
                   prompt_validation_strict: bool = False,
                   resolver_params: Optional[Dict[str, Any]] = None,
                   model_parameters: Optional[Dict[str, Any]] = None,
                   tenant_id: Optional[str] = None,
                   debug: bool = False,
                   timeout: Optional[int] = None) -> str:
        """
        Submit an extraction task
        
        Args:
            text_or_documents: Text string, URL, or list of Document objects to extract from
            prompt_description: Extraction prompt description
            examples: List of example data dicts
            fetch_urls: Whether to fetch URLs (if text_or_documents is URL)
            max_char_buffer: Maximum character buffer
            temperature: Sampling temperature
            extraction_passes: Number of extraction passes
            additional_context: Additional context string
            prompt_validation_level: Prompt validation level
            prompt_validation_strict: Whether to use strict validation
            resolver_params: Resolver parameters
            model_parameters: Additional model parameters
            tenant_id: Optional tenant ID for LLM config
            debug: Debug mode
            timeout: Task timeout in seconds (default: DEFAULT_TASK_TIMEOUT or 1800)
            
        Returns:
            Task ID
            
        Raises:
            ValueError: If server is busy or invalid input
            
        Note:
            max_workers and batch_length are controlled internally by the service
            based on resource availability and input size.
        """
        # Handle text_or_documents: can be string or list of Document objects
        actual_text_or_documents = text_or_documents
        
        # Download URL content if needed (only for string URLs)
        if isinstance(text_or_documents, str):
            if fetch_urls and (text_or_documents.startswith("http://") or text_or_documents.startswith("https://")):
                logger.info(f"Downloading content from URL: {text_or_documents}")
                actual_text_or_documents = self._download_url_content(text_or_documents)
        
        # Calculate required workers (internal control, not exposed to API)
        required_workers = self._calculate_max_workers(actual_text_or_documents, max_char_buffer)
        
        # Check available workers
        with self.workers_lock:
            available_workers = self.MAX_EXTRACT_WORKS - self.used_workers
            if required_workers > available_workers:
                raise ServerBusyError(required_workers, available_workers)
            
            # Reserve workers
            self.used_workers += required_workers
        
        # Create task
        task_id = str(uuid.uuid4())
        task = ExtractionTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            text_or_documents=actual_text_or_documents,
            prompt_description=prompt_description,
            examples=examples,
            config={
                "max_char_buffer": max_char_buffer,
                "temperature": temperature,
                "extraction_passes": extraction_passes,
                "additional_context": additional_context,
                "prompt_validation_level": prompt_validation_level,
                "prompt_validation_strict": prompt_validation_strict,
                "resolver_params": resolver_params or {},
                "model_parameters": model_parameters or {},
                "tenant_id": tenant_id,
                "debug": debug,
                "timeout": timeout if timeout is not None else self.DEFAULT_TASK_TIMEOUT
            },
            max_workers=required_workers
        )
        
        with self.tasks_lock:
            self.tasks[task_id] = task
        
        # Submit to thread pool
        future = self.executor.submit(self._process_task, task_id)
        
        # Store future for timeout monitoring
        with self.tasks_lock:
            self.task_futures[task_id] = future
        
        # Set up timeout monitoring
        timeout_seconds = task.config.get("timeout", self.DEFAULT_TASK_TIMEOUT)
        if timeout_seconds > 0:
            self._setup_timeout_monitor(task_id, timeout_seconds)
        
        logger.info(f"Task {task_id} submitted with {required_workers} workers, timeout={timeout_seconds}s")
        
        return task_id
    
    def _setup_timeout_monitor(self, task_id: str, timeout_seconds: int):
        """
        Set up a timeout monitor for a task
        
        Args:
            task_id: Task ID to monitor
            timeout_seconds: Timeout in seconds
        """
        def timeout_handler():
            with self.tasks_lock:
                task = self.tasks.get(task_id)
                future = self.task_futures.get(task_id)
                
                if task and task.status == TaskStatus.PROCESSING:
                    # Check if task is still running
                    if future and not future.done():
                        logger.warning(f"Task {task_id} timed out after {timeout_seconds} seconds")
                        task.status = TaskStatus.FAILED
                        task.error = f"Task timed out after {timeout_seconds} seconds"
                        task.updated_at = datetime.now()
                        # Cancel the future if possible (note: this won't stop a running thread)
                        future.cancel()
        
        # Create a timer thread
        timer = threading.Timer(timeout_seconds, timeout_handler)
        timer.daemon = True
        timer.start()
    
    def _process_task(self, task_id: str):
        """
        Process an extraction task (runs in thread pool)
        
        Args:
            task_id: Task ID to process
        """
        try:
            with self.tasks_lock:
                task = self.tasks.get(task_id)
                if not task:
                    logger.error(f"Task {task_id} not found")
                    return
                task.status = TaskStatus.PROCESSING
                task.updated_at = datetime.now()
            
            logger.info(f"Processing task {task_id}")
            
            output_result = self._do_extract(
                text_or_documents=task.text_or_documents,
                prompt_description=task.prompt_description,
                examples=task.examples,
                max_char_buffer=task.config.get("max_char_buffer", 1000),
                temperature=task.config.get("temperature"),
                extraction_passes=task.config.get("extraction_passes", 1),
                additional_context=task.config.get("additional_context"),
                prompt_validation_level=task.config.get("prompt_validation_level", "WARNING"),
                prompt_validation_strict=task.config.get("prompt_validation_strict", False),
                resolver_params=task.config.get("resolver_params"),
                model_parameters=task.config.get("model_parameters"),
                tenant_id=task.config.get("tenant_id"),
                llm_id=None,  # Not used in async tasks
                max_workers=task.max_workers,
                batch_length=10000000,  # Large value to process all documents/chunks in one batch
                use_schema_constraints=False,  # Different from sync extraction
                fetch_urls=False,  # Always False since we already downloaded
                debug=task.config.get("debug", False)
            )

            # Update task with result
            with self.tasks_lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.SUCCESS
                    task.result = output_result
                    task.updated_at = datetime.now()
            
            logger.info(f"Task {task_id} completed successfully")
        
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            with self.tasks_lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.updated_at = datetime.now()
        
        finally:
            # Release workers and clean up
            with self.tasks_lock:
                task = self.tasks.get(task_id)
                if task:
                    with self.workers_lock:
                        self.used_workers -= task.max_workers
                        self.used_workers = max(0, self.used_workers)
                
                # Remove future from tracking
                self.task_futures.pop(task_id, None)
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status
        
        Args:
            task_id: Task ID
            
        Returns:
            Dict with task status and result
        """
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            if not task:
                return {
                    "status": TaskStatus.NOT_FOUND.value,
                    "message": "Task not found"
                }
            
            result = {
                "task_id": task_id,
                "status": task.status.value,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
            
            if task.status == TaskStatus.SUCCESS and task.result:
                result["result"] = task.result
            elif task.status == TaskStatus.FAILED and task.error:
                result["error"] = task.error
            
            return result


# Global service instance
_langextract_service = None


def get_langextract_service() -> LangextractService:
    """Get global langextract service instance"""
    global _langextract_service
    if _langextract_service is None:
        _langextract_service = LangextractService()
    return _langextract_service

