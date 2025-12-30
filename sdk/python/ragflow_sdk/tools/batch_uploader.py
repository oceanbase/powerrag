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

import json
import os
import time
import logging
from typing import Optional, Dict, List, Tuple, Iterator

from ..ragflow import RAGFlow
from ..modules.dataset import DataSet
from .document_extractor import DocumentExtractor
from .models import Snapshot, FileCursor


class BatchUploader:
    """
    Batch uploader for uploading large volumes of documents to RAGFlow.
    
    This class handles the upload logic, receiving document batches from
    a DocumentExtractor iterator and uploading them to RAGFlow.
    
    Features:
    - Iterator-based batch processing
    - Snapshot-based resume support
    - Automatic retry with exponential backoff
    """
    
    def __init__(self, rag: RAGFlow, dataset: Optional[DataSet] = None):
        """
        Initialize BatchUploader.
        
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
    
    @staticmethod
    def save_snapshot(snapshot_file: str, file_cursors: List[FileCursor], 
                     total_processed: int, dataset_id: Optional[str] = None):
        """
        Save processing snapshot to file.
        
        Args:
            snapshot_file: Path to snapshot file
            file_cursors: List of FileCursor entities, each tracking a file's processing progress
            total_processed: Total number of documents processed
            dataset_id: Optional dataset ID
        """
        snapshot = Snapshot(
            file_cursors=file_cursors,
            total_processed=total_processed,
            timestamp=time.time(),
            dataset_id=dataset_id
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(snapshot_file) if os.path.dirname(snapshot_file) else '.', exist_ok=True)
        
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot.to_dict(), f, indent=2)
    
    @staticmethod
    def load_snapshot(snapshot_file: str) -> Optional[Snapshot]:
        """
        Load processing snapshot from file.
        
        Args:
            snapshot_file: Path to snapshot file
            
        Returns:
            Snapshot entity or None if file doesn't exist or is invalid
        """
        if not os.path.exists(snapshot_file):
            return None
        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Snapshot.from_dict(data)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Warning: Failed to load snapshot: {e}")
            return None
    
    def set_dataset(self, dataset: DataSet):
        """Set the dataset to use for uploading."""
        self.dataset = dataset
    
    def get_or_create_dataset(self, dataset_id: Optional[str] = None, 
                             dataset_name: Optional[str] = None) -> DataSet:
        """
        Get existing dataset or create a new one.
        
        Args:
            dataset_id: Optional existing dataset ID
            dataset_name: Optional name for new dataset (default: auto-generated)
            
        Returns:
            Dataset instance
        """
        if dataset_id:
            datasets = self.rag.list_datasets(id=dataset_id)
            if not datasets:
                raise Exception(f"Dataset with ID '{dataset_id}' not found")
            self.dataset = datasets[0]
            self.logger.info(f"Using existing dataset: {self.dataset.name} (ID: {self.dataset.id})")
        else:
            if not dataset_name:
                dataset_name = f"batch_upload_{time.strftime('%Y%m%d_%H%M%S')}"
            self.dataset = self.rag.create_dataset(name=dataset_name)
            self.logger.info(f"Created new dataset: {self.dataset.name} (ID: {self.dataset.id})")
        
        return self.dataset
    
    def _upload_batches(
        self,
        batch_iterator: Iterator[Tuple[List[Dict], str, bool]],
        snapshot_file: str = "upload_snapshot.json",
        file_extension: str = "txt"
    ) -> Iterator[Tuple[List[Dict], str, bool]]:
        """
        Internal method: Upload document batches from a document extractor iterator.
        
        This is a private method used internally by upload(). It receives batches
        from a DocumentExtractor iterator and uploads them to RAGFlow.
        
        Args:
            batch_iterator: Iterator from DocumentExtractor.extract_batches()
            snapshot_file: Path to snapshot file for resume support
            file_extension: File extension for uploaded documents
            
        Yields:
            Tuples of (batch_documents, current_file_path, is_file_complete)
            - batch_documents: List of document dictionaries (already uploaded)
            - current_file_path: Path of the file currently being processed
            - is_file_complete: True if this is the last batch from the current file
        """
        # Upload function with retry
        def upload_batch(batch: List[Dict]):
            """Upload a batch of documents."""
            if not batch:
                return
            
            self.logger.info(f"  Uploading batch of {len(batch)} documents...")
            docs = self.dataset.upload_documents_with_meta(batch, file_extension=file_extension)
            self.logger.info(f"  Successfully uploaded {len(docs)} documents")
            return len(docs)
        
        upload_batch_with_retry = self.retry_with_backoff(upload_batch, max_retries=10, max_backoff=8)
        
        # Process batches from iterator
        for batch, file_path, is_file_complete in batch_iterator:
            # Upload batch with retry
            upload_batch_with_retry(batch)
            
            # Yield batch info (for tracking purposes)
            yield batch, file_path, is_file_complete
    
    def upload(
        self,
        document_extractor: DocumentExtractor,
        data_dir: str,
        dataset_id: Optional[str] = None,
        dataset_name: Optional[str] = None,
        batch_size: int = 5,
        snapshot_file: str = "upload_snapshot.json",
        resume: bool = False,
        file_extension: str = "txt",
        file_patterns: Optional[List[str]] = None
    ) -> Tuple[int, int]:
        """
        Upload documents from directory to RAGFlow.
        
        This is a convenience method that uses DocumentExtractor to extract
        documents and then uploads them automatically.
        
        Args:
            document_extractor: DocumentExtractor instance
            data_dir: Directory containing files to upload
            dataset_id: Optional dataset ID to use
            dataset_name: Optional name for new dataset
            batch_size: Number of documents per batch
            snapshot_file: Path to snapshot file for resume support
            resume: Whether to resume from snapshot
            file_extension: File extension for uploaded documents if title does not have an extension
            file_patterns: Optional list of file patterns to match
            
        Returns:
            Tuple of (total_processed_docs, total_files_processed)
        """
        if not self.dataset:
            self.get_or_create_dataset(dataset_id, dataset_name)
        
        # Load snapshot
        snapshot = None
        file_cursors: List[FileCursor] = []
        total_processed = 0
        
        if resume:
            snapshot = self.load_snapshot(snapshot_file)
            if snapshot:
                file_cursors = snapshot.file_cursors
                total_processed = snapshot.total_processed
                
                # Restore dataset_id from snapshot if not provided
                if not dataset_id and snapshot.dataset_id:
                    dataset_id = snapshot.dataset_id
                    if not self.dataset or self.dataset.id != dataset_id:
                        datasets = self.rag.list_datasets(id=dataset_id)
                        if datasets:
                            self.dataset = datasets[0]
                    self.logger.info(f"📍 Restored dataset_id from snapshot: {dataset_id}")
                
                self.logger.info(f"📍 Resuming: {len(file_cursors)} files in progress, {total_processed} documents processed")
            else:
                self.logger.warning("⚠️  No valid snapshot found, starting from beginning")
        
        # Track current file being processed and document index
        current_file_path = None
        current_file_doc_index = {}  # Track current doc index for each file
        
        # Convert FileCursor list to dict for backward compatibility with extract_batches
        file_cursor_dict = None
        if resume and file_cursors:
            file_cursor_dict = {cursor.file_path: cursor.doc_index for cursor in file_cursors}
        
        # Exclude snapshot file from processing
        exclude_files = [snapshot_file] if os.path.exists(snapshot_file) else []
        
        # Get batch iterator from document extractor
        batch_iterator = document_extractor.extract_batches(
            data_dir=data_dir,
            batch_size=batch_size,
            file_patterns=file_patterns,
            file_cursor=file_cursor_dict,
            exclude_files=exclude_files
        )
        
        # Create a snapshot instance to manage file cursors
        current_snapshot = Snapshot(
            file_cursors=file_cursors.copy() if file_cursors else [],
            total_processed=total_processed,
            dataset_id=self.dataset.id if self.dataset else None
        )
        
        # Track documents processed in this session (for resume mode)
        docs_processed_this_session = 0
        
        # Process batches using internal _upload_batches method
        try:
            for batch, file_path, is_file_complete in self._upload_batches(
                batch_iterator=batch_iterator,
                snapshot_file=snapshot_file,
                file_extension=file_extension
            ):
                current_file_path = file_path
                current_snapshot.total_processed += len(batch)
                docs_processed_this_session += len(batch)
                
                # Update file cursor: track how many documents we've processed from this file
                if file_path not in current_file_doc_index:
                    # Start from cursor position or 0
                    cursor = current_snapshot.get_cursor(file_path)
                    current_file_doc_index[file_path] = cursor.doc_index if cursor else 0
                
                # Increment document index for this file
                current_file_doc_index[file_path] += len(batch)
                
                # Update snapshot after successful upload
                # For multi-doc files, update cursor to next index
                # For single-doc files, if complete, set cursor to 1 (or any > 0)
                if is_file_complete:
                    # File is complete, mark as fully processed
                    # For single-doc files, cursor > 0 means processed
                    # For multi-doc files, cursor = total docs means processed
                    current_snapshot.set_cursor(file_path, current_file_doc_index[file_path])
                    self.logger.info(f"  File completed: {os.path.basename(file_path)} (processed {current_file_doc_index[file_path]} documents)")
                else:
                    # File not complete yet, update cursor to current position
                    current_snapshot.set_cursor(file_path, current_file_doc_index[file_path])
                
                # Save snapshot after each successful batch upload
                self.save_snapshot(snapshot_file, current_snapshot.file_cursors, current_snapshot.total_processed, current_snapshot.dataset_id)
        
        except Exception as e:
            self.logger.error(f"Upload failed: {e}")
            # Save snapshot before re-raising
            self.save_snapshot(snapshot_file, current_snapshot.file_cursors, current_snapshot.total_processed, current_snapshot.dataset_id)
            raise
        
        # Count fully processed files (files with cursor > 0 for single-doc, or cursor >= total docs for multi-doc)
        # Count only files that were processed or completed in this session
        fully_processed_files = 0
        initial_file_cursors = {cursor.file_path: cursor.doc_index for cursor in file_cursors} if resume else {}
        
        for cursor in current_snapshot.file_cursors:
            if cursor.doc_index > 0:
                # Check if this file was processed in this session
                # If resume mode, only count files that were processed/completed in this session
                if resume:
                    initial_index = initial_file_cursors.get(cursor.file_path, 0)
                    if cursor.doc_index > initial_index:
                        fully_processed_files += 1
                else:
                    fully_processed_files += 1
        
        # Return documents processed in this session (not total)
        # For resume mode, return only newly processed documents
        # For normal mode, return total processed documents
        if resume:
            total_processed = docs_processed_this_session
        else:
            total_processed = current_snapshot.total_processed
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info(f"✅ Upload completed!")
        self.logger.info(f"   Documents processed: {total_processed}")
        if resume:
            self.logger.info(f"   Total documents (including previous): {current_snapshot.total_processed}")
        self.logger.info(f"   Files processed: {fully_processed_files}")
        
        # Clean up snapshot on successful completion
        if os.path.exists(snapshot_file):
            os.remove(snapshot_file)
            self.logger.info(f"🧹 Snapshot file removed: {snapshot_file}")
        
        return total_processed, fully_processed_files

