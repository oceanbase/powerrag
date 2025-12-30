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
import csv
import logging
from typing import Iterator, List, Dict, Optional, Any
from pathlib import Path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from .field_mapper import FieldMapper
from .models import FileType


class FileReader:
    """
    File reader for various file formats supporting batch iteration.
    
    Supports:
    - Multi-document formats: JSON (array), JSONL, CSV, XLSX, XLS
    - Single-document formats: PDF, Office, HTML, Markdown, images, etc.
    """
    
    # PowerRAG supported single-document formats
    # Based on powerrag/server/services/parse_service.py and powerrag/app/title.py
    SINGLE_DOC_FORMATS = {
        '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.html', '.htm', 
        '.md', '.markdown', '.txt', '.eml', '.epub',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'
    }
    
    def __init__(self, field_mapper: Optional[FieldMapper] = None,
                 multi_doc_extensions: Optional[List[str]] = None):
        """
        Initialize FileReader.
        
        Args:
            field_mapper: Optional FieldMapper instance for field mapping
            multi_doc_extensions: List of file extensions (without dot) that should be
                                 treated as multi-document formats. 
                                 Files with these extensions will be parsed as containing
                                 multiple documents. If not in this list, files will be
                                 treated as single-document format.
        """
        self.field_mapper = field_mapper or FieldMapper()
        # Convert to set with dots for easier comparison
        self.multi_doc_extensions = {f'.{ext.lower().lstrip(".")}' for ext in multi_doc_extensions}
        self.logger = logging.getLogger(__name__)
    
    def is_multi_document_format(self, file_path: str) -> bool:
        """
        Check if file is a multi-document format.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file contains multiple documents, False if single document
        """
        ext = Path(file_path).suffix.lower()
        
        # Check if extension is in configured multi-doc extensions
        if ext in self.multi_doc_extensions:
            # For JSON, check if it's an array (multi-doc) or single object (single-doc)
            if ext == '.json':
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        first_char = f.read(1).strip()
                        if first_char == '[':
                            return True  # Array JSON - multi-doc
                        else:
                            return False  # Single object JSON - single-doc
                except Exception:
                    # Default to single-doc if can't determine
                    return False
            elif ext == '.jsonl':
                # JSONL is always multi-doc (one JSON object per line)
                return True
            elif ext in ['.csv', '.xlsx', '.xls']:
                # CSV and Excel files are treated as multi-doc if in the list
                return True
            else:
                # Other configured extensions are signle-doc
                return False
        
        # All other formats are single-doc
        return False
    
    def _detect_file_type(self, file_path: str) -> FileType:
        """
        Detect file type based on extension and content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileType enumeration value
        """
        ext = Path(file_path).suffix.lower()
        
        # Check if it's a multi-doc format first
        if not self.is_multi_document_format(file_path):
            return FileType.SINGLE
        
        # Determine specific multi-doc type
        if ext == '.json':
            return FileType.JSON_ARRAY
        elif ext == '.jsonl':
            return FileType.JSONL
        elif ext == '.csv':
            return FileType.CSV
        elif ext in ['.xlsx', '.xls']:
            return FileType.EXCEL
        else:
            # Should not reach here, but treat as single if unknown
            return FileType.SINGLE
    
    def _read_json_array(self, file_path: str, start_index: int = 0) -> Iterator[Dict[str, Any]]:
        """Read JSON file (array of documents)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for idx, doc in enumerate(data):
                    if idx >= start_index:
                        yield doc
            else:
                # Should not happen if is_multi_document_format is correct
                # But if it does, return empty iterator (single object should be handled as single-doc)
                return
    
    def _read_jsonl(self, file_path: str, start_index: int = 0) -> Iterator[Dict[str, Any]]:
        """Read JSONL file (one JSON object per line)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line_num - 1 < start_index:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse JSONL line {line_num} in {file_path}: {e}")
                    continue
    
    def _read_csv(self, file_path: str, start_index: int = 0) -> Iterator[Dict[str, Any]]:
        """Read CSV file (each row is a document)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                if row_idx < start_index:
                    continue
                # Convert empty strings to None for consistency
                doc = {k: (v if v else None) for k, v in row.items()}
                yield doc
    
    def _read_excel(self, file_path: str, start_index: int = 0) -> Iterator[Dict[str, Any]]:
        """Read Excel file (each row is a document)."""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for Excel file support. Install it with: pip install pandas openpyxl")
        
        try:
            # Determine engine based on file extension
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.xls':
                # For .xls files, use xlrd engine
                engine = 'xlrd'
            else:
                # For .xlsx and other formats, use openpyxl
                engine = 'openpyxl'
            
            # Try reading all sheets
            excel_file = pd.ExcelFile(file_path, engine=engine)
            row_count = 0
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                # Convert DataFrame to list of dicts
                for _, row in df.iterrows():
                    if row_count < start_index:
                        row_count += 1
                        continue
                    # Convert NaN to None and convert to dict
                    doc = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                    yield doc
                    row_count += 1
        except Exception as e:
            self.logger.error(f"Failed to read Excel file {file_path}: {e}")
            raise
    
    def _read_single_file(self, file_path: str) -> Iterator[Dict[str, Any]]:
        """
        Read single file as a single document.
        
        For single-file-single-document format:
        - title: filename (with extension)
        - content: file content (as string for text files, empty string for binary files)
        - Other fields: empty (no metadata, no doc_id, no doc_url, no tags)
        """
        # Get filename as title (with extension)
        title = Path(file_path).name  # Use filename with extension as title
        
        # Try reading as text first
        content = ''
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # If text reading fails, it's likely a binary file (PDF, images, etc.)
            # For binary files, content will be empty string
            # The actual binary content will be handled by the uploader when uploading the file
            content = ''
        except Exception as e:
            self.logger.warning(f"Failed to read file {file_path} as text: {e}")
            content = ''
        
        # Return document with only title and content, no other fields
        # Field mapper will extract title and content, and won't add metadata since
        # doc_id, doc_url, and tags are all None/empty
        yield {
            'title': title,
            'content': content
        }
    
    def read_file(self, file_path: str, start_index: int = 0) -> Iterator[Dict[str, Any]]:
        """
        Read a file and yield documents.
        
        Args:
            file_path: Path to the file
            start_index: Starting document index (for multi-doc formats, skip documents before this index)
            
        Yields:
            Document dictionaries
        """
        file_type = self._detect_file_type(file_path)
        
        try:
            if file_type == FileType.JSON_ARRAY:
                iterator = self._read_json_array(file_path, start_index)
            elif file_type == FileType.JSONL:
                iterator = self._read_jsonl(file_path, start_index)
            elif file_type == FileType.CSV:
                iterator = self._read_csv(file_path, start_index)
            elif file_type == FileType.EXCEL:
                iterator = self._read_excel(file_path, start_index)
            else:  # FileType.SINGLE
                # For single-doc files, start_index should be 0 (or we skip if already processed)
                if start_index > 0:
                    # File already processed, skip
                    return
                iterator = self._read_single_file(file_path)
            
            for doc in iterator:
                # Apply field mapping if mapper is provided
                mapped_doc = self.field_mapper.map(doc)
                yield mapped_doc
                
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def read_files_batch(
        self,
        file_paths: List[str],
        batch_size: int,
        processed_files: Optional[List[str]] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Read multiple files in batches.
        
        Args:
            file_paths: List of file paths to read
            batch_size: Number of documents per batch
            processed_files: Optional list of already processed file paths (will be skipped)
            
        Yields:
            Batches of documents (each batch is a list of document dicts)
        """
        processed_set = set(processed_files or [])
        batch = []
        
        for file_path in file_paths:
            # Skip already processed files
            if file_path in processed_set:
                self.logger.debug(f"Skipping already processed file: {file_path}")
                continue
            
            try:
                for doc in self.read_file(file_path):
                    batch.append(doc)
                    
                    # Yield batch when it reaches batch_size
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {e}")
                # Continue with next file even if current file fails
                continue
        
        # Yield remaining documents
        if batch:
            yield batch

