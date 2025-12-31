#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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

import time
import logging
from typing import Optional, Tuple

from ..ragflow import RAGFlow
from ..modules.dataset import DataSet


class FailedDocumentReparser:
    """
    Tool for reparsing failed documents in a RAGFlow dataset.
    
    This class handles the logic for finding failed documents in a dataset
    and reparsing them in batches with automatic retry and exponential backoff.
    
    Features:
    - Stream processing: fetch documents page by page
    - Batch reparsing with configurable batch size
    - Automatic retry with exponential backoff
    - Progress tracking and logging
    """
    
    def __init__(self, rag: RAGFlow, dataset: Optional[DataSet] = None):
        """
        Initialize FailedDocumentReparser.
        
        Args:
            rag: RAGFlow client instance
            dataset: Optional dataset instance
        """
        self.rag = rag
        self.dataset = dataset
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def retry_with_backoff(func, max_retries: int = 10, max_backoff: int = 8):
        """
        Retry wrapper with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts (default: 10)
            max_backoff: Maximum retry interval in seconds (default: 8)
            
        Returns:
            Wrapped function with retry logic
        """
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(__name__)
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        backoff_time = min(2 ** attempt, max_backoff)
                        logger.warning(f"  ⚠️  Error: {str(e)}")
                        logger.info(f"  Retrying in {backoff_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(backoff_time)
                    else:
                        logger.error(f"  ❌ Failed after {max_retries} attempts: {str(e)}")
                        raise
        return wrapper
    
    def set_dataset(self, dataset: DataSet):
        """Set the dataset to use for reparsing."""
        self.dataset = dataset
    
    def get_dataset(self, dataset_id: str) -> DataSet:
        """
        Get dataset by ID.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dataset instance
        """
        datasets = self.rag.list_datasets(id=dataset_id)
        if not datasets:
            raise Exception(f"Dataset with ID '{dataset_id}' not found")
        self.dataset = datasets[0]
        self.logger.info(f"Using dataset: {self.dataset.name} (ID: {self.dataset.id})")
        return self.dataset
    
    def reparse_failed_documents(
        self,
        dataset_id: Optional[str] = None,
        reparse_batch_size: int = 50,
        page_size: int = 10000
    ) -> Tuple[int, int]:
        """
        Reparse all failed documents in a dataset.
        
        This method fetches documents page by page, filters failed ones,
        and reparses them in batches.
        
        Args:
            dataset_id: Dataset ID to reparse documents from (if dataset not set)
            reparse_batch_size: Batch size for reparsing documents (default: 50)
            page_size: Page size for fetching documents (default: 10000)
            
        Returns:
            Tuple of (total_failed, total_reparsed)
        """
        # Validate reparse_batch_size
        if reparse_batch_size <= 0:
            raise ValueError(f"reparse_batch_size must be greater than 0, got {reparse_batch_size}")
        
        if page_size <= 0:
            raise ValueError(f"page_size must be greater than 0, got {page_size}")
        
        # Get dataset if not set
        if not self.dataset:
            if not dataset_id:
                raise ValueError("Either dataset must be set or dataset_id must be provided")
            self.get_dataset(dataset_id)
        
        # Stream processing: fetch documents page by page, filter failed ones, and reparse when reparse_batch_size is reached
        self.logger.info("Fetching documents from dataset and processing failed ones in batches...")
        page = 1
        total_documents = 0
        total_failed = 0
        total_reparsed = 0
        pending_failed_doc_ids = []  # Accumulate failed document IDs until reparse_batch_size is reached
        
        def reparse_batch(doc_ids):
            """Reparse a batch of documents."""
            nonlocal total_reparsed
            # This check should not be needed if the calling code is correct,
            # but kept as a safety measure
            if not doc_ids:
                self.logger.warning("  ⚠️  Skipping empty batch (this should not happen)")
                return
            
            self.logger.info(f"  Reparsing batch of {len(doc_ids)} documents...")
            self.dataset.async_parse_documents(doc_ids)
            total_reparsed += len(doc_ids)
            self.logger.info(f"  Batch completed: {len(doc_ids)} documents parsed successfully")
            self.logger.info(f"  Total reparsed so far: {total_reparsed}")
        
        # Wrap reparse_batch with retry logic
        reparse_batch_with_retry = self.retry_with_backoff(reparse_batch, max_retries=10, max_backoff=8)
        
        # Helper function to fetch documents with retry
        def fetch_documents_page(page_num, page_sz):
            """Fetch a page of documents with retry logic."""
            return self.dataset.list_documents(page=page_num, page_size=page_sz, orderby="id", desc=False)
        
        fetch_documents_with_retry = self.retry_with_backoff(fetch_documents_page, max_retries=10, max_backoff=8)
        batch_number = 0
        
        while True:
            # Fetch a page of documents
            self.logger.info(f"Fetching page {page} (page_size={page_size})...")
            documents = fetch_documents_with_retry(page, page_size)
            
            if not documents:
                break
            
            total_documents += len(documents)
            self.logger.info(f"  Page {page}: fetched {len(documents)} documents (total: {total_documents})")
            
            # Filter failed documents from this page
            page_failed_docs = []
            for doc in documents:
                # Check if document parsing failed
                # run status can be "FAIL", "DONE", "CANCEL", etc.
                if isinstance(doc.run, str) and doc.run.upper() == "FAIL":
                    page_failed_docs.append(doc)
                    pending_failed_doc_ids.append(doc.id)
                    total_failed += 1
            
            if page_failed_docs:
                self.logger.info(f"  Found {len(page_failed_docs)} failed documents in this page (total failed: {total_failed})")
            
            # If we've accumulated enough failed documents, reparse them
            while len(pending_failed_doc_ids) >= reparse_batch_size:
                batch_number += 1
                batch = pending_failed_doc_ids[:reparse_batch_size]
                pending_failed_doc_ids = pending_failed_doc_ids[reparse_batch_size:]  # Remove only the processed batch
                self.logger.info(f"\nProcessing batch {batch_number} ({len(batch)} documents)...")
                reparse_batch_with_retry(batch)
            
            # Check if this is the last page
            if len(documents) < page_size:
                break
            page += 1
        
        self.logger.info(f"\nFinished fetching all documents. Total: {total_documents}, Failed: {total_failed}")
        
        # Process remaining failed documents (if any)
        if pending_failed_doc_ids:
            batch_number += 1
            self.logger.info(f"\nProcessing final batch {batch_number} ({len(pending_failed_doc_ids)} documents)...")
            reparse_batch_with_retry(pending_failed_doc_ids)
        
        if total_failed == 0:
            self.logger.info("✅ No failed documents found in the dataset")
            return 0, 0
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info(f"✅ Reparsing completed! Successfully reparsed: {total_reparsed}/{total_failed} documents")
        
        return total_failed, total_reparsed

