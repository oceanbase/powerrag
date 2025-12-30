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
import glob
import logging
from typing import Iterator, List, Dict, Optional, Tuple, Any
from pathlib import Path

from .file_reader import FileReader
from .field_mapper import FieldMapper


class DocumentExtractor:
    """
    Document extractor that extracts documents from files/directories.
    
    This class provides an iterator interface for extracting documents
    from various file formats with lazy loading support.
    """
    
    def __init__(self, field_mapper: Optional[FieldMapper] = None, 
                 multi_doc_extensions: Optional[List[str]] = ['json', 'jsonl']):
        """
        Initialize DocumentExtractor.
        
        Args:
            field_mapper: Optional FieldMapper instance for field mapping
            multi_doc_extensions: List of file extensions (without dot) that should be
                                 treated as multi-document formats. 
                                 Default: ['json', 'jsonl', 'csv', 'xlsx', 'xls']
                                 Files with these extensions will be parsed as containing
                                 multiple documents. If not in this list, files will be
                                 treated as single-document format.
        """
        self.field_mapper = field_mapper or FieldMapper()
        self.multi_doc_extensions = multi_doc_extensions
        self.file_reader = FileReader(field_mapper=self.field_mapper, 
                                     multi_doc_extensions=multi_doc_extensions)
        self.logger = logging.getLogger(__name__)
    
    def _get_file_list(self, data_dir: str, file_patterns: Optional[List[str]] = None) -> List[str]:
        """
        Get list of files to process.
        
        Args:
            data_dir: Directory containing files
            file_patterns: Optional list of file patterns (e.g., ['*.json', '*.csv'])
                          If None, uses all supported patterns
            
        Returns:
            Sorted list of file paths (sorted by filename for consistent processing order)
        """
        if file_patterns is None:
            # Include all PowerRAG supported formats
            # Multi-doc formats
            file_patterns = ['*.json', '*.jsonl', '*.csv', '*.xlsx', '*.xls']
            # Single-doc formats (PowerRAG supported)
            file_patterns.extend([
                '*.pdf', '*.docx', '*.doc', '*.pptx', '*.ppt',
                '*.html', '*.htm', '*.md', '*.markdown', '*.txt',
                '*.eml', '*.epub', '*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.tiff', '*.webp'
            ])
        
        file_list = []
        for pattern in file_patterns:
            pattern_path = os.path.join(data_dir, pattern)
            file_list.extend(glob.glob(pattern_path))
        
        # Remove duplicates and sort by filename (important for snapshot consistency)
        file_list = sorted(list(set(file_list)))
        return file_list
    
    def extract_documents(
        self,
        data_dir: str,
        file_patterns: Optional[List[str]] = None,
        processed_files: Optional[List[str]] = None
    ) -> Iterator[Tuple[Dict[str, Any], str]]:
        """
        Extract documents from files in a directory.
        
        This method returns an iterator that yields documents lazily.
        Each document is yielded as a tuple of (document_dict, file_path).
        
        Args:
            data_dir: Directory containing files to extract
            file_patterns: Optional list of file patterns to match
            processed_files: Optional list of already processed file paths (will be skipped)
            
        Yields:
            Tuples of (document_dict, file_path)
            - document_dict: Document dictionary in RAGFlow standard format
            - file_path: Path of the file containing this document
        """
        # Get file list
        file_list = self._get_file_list(data_dir, file_patterns)
        self.logger.info(f"Found {len(file_list)} files to process")
        
        processed_set = set(processed_files or [])
        
        for file_path in file_list:
            # Skip already processed files
            if file_path in processed_set:
                self.logger.debug(f"Skipping already processed file: {file_path}")
                continue
            
            self.logger.info(f"Processing file: {os.path.basename(file_path)}")
            
            try:
                # Read file and yield documents lazily
                for doc in self.file_reader.read_file(file_path):
                    yield doc, file_path
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {e}")
                # Continue with next file
                continue
    
    def extract_batches(
        self,
        data_dir: str,
        batch_size: int,
        file_patterns: Optional[List[str]] = None,
        file_cursor: Optional[Dict[str, int]] = None,
        exclude_files: Optional[List[str]] = None
    ) -> Iterator[Tuple[List[Dict[str, Any]], str, bool]]:
        """
        Extract documents in batches from files in a directory.
        
        This method returns an iterator that yields batches of documents.
        Each batch is loaded lazily only when requested.
        
        Args:
            data_dir: Directory containing files to extract
            batch_size: Number of documents per batch
            file_patterns: Optional list of file patterns to match
            file_cursor: Optional dictionary mapping file paths to document indices
                        {file_path: doc_index} - resume from this index for each file
            exclude_files: Optional list of file paths to exclude from processing
            
        Yields:
            Tuples of (batch_documents, current_file_path, is_file_complete)
            - batch_documents: List of document dictionaries ready for upload
            - current_file_path: Path of the file currently being processed
            - is_file_complete: True if this is the last batch from the current file
        """
        # Get file list (sorted by filename)
        file_list = self._get_file_list(data_dir, file_patterns)
        
        # Exclude specified files (e.g., snapshot files)
        if exclude_files:
            exclude_set = set(exclude_files)
            file_list = [f for f in file_list if f not in exclude_set]
        
        self.logger.info(f"Found {len(file_list)} files to process")
        
        file_cursor = file_cursor or {}
        current_batch = []
        current_file_path = None
        
        for file_path in file_list:
            # Get start index for this file (0 if not in cursor, or cursor value)
            start_index = file_cursor.get(file_path, 0)
            
            # Check if file is fully processed
            # For multi-doc files, we need to check if there are more docs
            # For single-doc files, if start_index > 0, it's processed
            if start_index > 0 and not self.file_reader.is_multi_document_format(file_path):
                # Single-doc file already processed
                self.logger.debug(f"Skipping already processed file: {file_path}")
                continue
            
            current_file_path = file_path
            
            if start_index > 0:
                self.logger.info(f"Resuming file: {os.path.basename(file_path)} from document index {start_index}")
            else:
                self.logger.info(f"Processing file: {os.path.basename(file_path)}")
            
            try:
                # Read file lazily (iterator-based, doesn't load entire file into memory)
                # Pass start_index to skip already processed documents
                doc_iterator = self.file_reader.read_file(file_path, start_index=start_index)
                doc_count = 0
                
                for doc in doc_iterator:
                    current_batch.append(doc)
                    doc_count += 1
                    
                    # Yield batch when it reaches batch_size
                    if len(current_batch) >= batch_size:
                        yield current_batch, current_file_path, False
                        current_batch = []
                
                # Yield remaining documents in final batch for this file
                if current_batch:
                    yield current_batch, current_file_path, True
                    current_batch = []
                
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {e}")
                # Continue with next file
                continue
        
        # Yield remaining documents in final batch (should not happen, but just in case)
        if current_batch:
            yield current_batch, current_file_path, True

