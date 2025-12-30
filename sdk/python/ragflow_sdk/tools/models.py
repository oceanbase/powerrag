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

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


class FileType(Enum):
    """File type enumeration."""
    JSON_ARRAY = "json_array"
    JSONL = "jsonl"
    CSV = "csv"
    EXCEL = "excel"
    SINGLE = "single"


class DocumentFormat(Enum):
    """Document format enumeration."""
    MULTI_DOC = "multi_doc"  # One file contains multiple documents
    SINGLE_DOC = "single_doc"  # One file corresponds to one document


@dataclass
class DocumentMetadata:
    """
    Document metadata entity in RAGFlow format.
    
    Attributes:
        doc_id: Optional document ID
        doc_url: Optional document URL
        tags: Optional list of tags
    """
    doc_id: Optional[str] = None
    doc_url: Optional[str] = None
    tags: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary format."""
        result = {}
        if self.doc_id is not None:
            result["doc_id"] = self.doc_id
        if self.doc_url is not None:
            result["doc_url"] = self.doc_url
        if self.tags is not None:
            result["tags"] = self.tags
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentMetadata":
        """Create metadata from dictionary."""
        return cls(
            doc_id=data.get("doc_id"),
            doc_url=data.get("doc_url"),
            tags=data.get("tags")
        )
    
    def is_empty(self) -> bool:
        """Check if metadata is empty (all fields are None)."""
        return self.doc_id is None and self.doc_url is None and (
            self.tags is None or len(self.tags) == 0
        )


@dataclass
class Document:
    """
    Standard document entity in RAGFlow format.
    
    Attributes:
        title: Document title
        content: Document content
        metadata: Optional metadata entity containing doc_id, doc_url, tags
    """
    title: str
    content: str
    metadata: Optional[DocumentMetadata] = None
    
    def to_dict(self) -> Dict:
        """Convert document to dictionary format."""
        result = {
            "title": self.title,
            "content": self.content
        }
        if self.metadata and not self.metadata.is_empty():
            result["metadata"] = self.metadata.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Create document from dictionary."""
        metadata_dict = data.get("metadata", {})
        metadata = None
        if metadata_dict:
            if isinstance(metadata_dict, DocumentMetadata):
                metadata = metadata_dict
            else:
                metadata = DocumentMetadata.from_dict(metadata_dict)
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            metadata=metadata
        )


@dataclass
class FieldMappingConfig:
    """
    Field mapping configuration.
    
    Attributes:
        title_field: Source field name for title (None = auto-detect)
        content_field: Source field name for content (None = auto-detect)
        doc_id_field: Source field name for doc_id (None = auto-detect)
        doc_url_field: Source field name for doc_url (None = auto-detect)
        tags_field: Source field name for tags (None = auto-detect)
        tags_separator: Separator for tags string (default: ',')
    """
    title_field: Optional[str] = None
    content_field: Optional[str] = None
    doc_id_field: Optional[str] = None
    doc_url_field: Optional[str] = None
    tags_field: Optional[str] = None
    tags_separator: str = ','


@dataclass
class FileCursor:
    """
    File cursor entity for tracking document processing progress.
    
    This entity represents a single file's processing cursor, indicating
    how many documents have been processed from this file.
    
    Attributes:
        file_path: Path to the file
        doc_index: Next document index to process (documents with index >= this are processed)
    """
    file_path: str
    doc_index: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert file cursor to dictionary format."""
        return {
            "file_path": self.file_path,
            "doc_index": self.doc_index
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileCursor":
        """Create file cursor from dictionary."""
        return cls(
            file_path=data.get("file_path", ""),
            doc_index=data.get("doc_index", 0)
        )


@dataclass
class Snapshot:
    """
    Processing snapshot entity for resume support.
    
    Attributes:
        file_cursors: List of file cursor entities, each tracking a file's processing progress
        total_processed: Total number of documents processed
        timestamp: Snapshot creation timestamp
        dataset_id: Optional dataset ID
    """
    file_cursors: List[FileCursor] = field(default_factory=list)
    total_processed: int = 0
    timestamp: float = 0.0
    dataset_id: Optional[str] = None
    
    def get_cursor(self, file_path: str) -> Optional[FileCursor]:
        """Get file cursor for a specific file path."""
        for cursor in self.file_cursors:
            if cursor.file_path == file_path:
                return cursor
        return None
    
    def set_cursor(self, file_path: str, doc_index: int) -> None:
        """Set or update file cursor for a file path."""
        cursor = self.get_cursor(file_path)
        if cursor:
            cursor.doc_index = doc_index
        else:
            self.file_cursors.append(FileCursor(file_path=file_path, doc_index=doc_index))
    
    def remove_cursor(self, file_path: str) -> None:
        """Remove file cursor for a file path."""
        self.file_cursors = [c for c in self.file_cursors if c.file_path != file_path]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary format."""
        result = {
            "file_cursors": [cursor.to_dict() for cursor in self.file_cursors],
            "total_processed": self.total_processed,
            "timestamp": self.timestamp
        }
        if self.dataset_id:
            result["dataset_id"] = self.dataset_id
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Create snapshot from dictionary."""
        file_cursors_data = data.get("file_cursors", [])
        # Support backward compatibility: if file_cursor (singular) exists, convert it
        if "file_cursor" in data and "file_cursors" not in data:
            # Old format: file_cursor is a dict {file_path: doc_index}
            file_cursor_dict = data.get("file_cursor", {})
            if isinstance(file_cursor_dict, dict):
                file_cursors_data = [
                    {"file_path": path, "doc_index": idx}
                    for path, idx in file_cursor_dict.items()
                ]
        
        file_cursors = []
        if file_cursors_data:
            for cursor_data in file_cursors_data:
                if isinstance(cursor_data, FileCursor):
                    file_cursors.append(cursor_data)
                else:
                    file_cursors.append(FileCursor.from_dict(cursor_data))
        
        return cls(
            file_cursors=file_cursors,
            total_processed=data.get("total_processed", 0),
            timestamp=data.get("timestamp", 0.0),
            dataset_id=data.get("dataset_id")
        )


@dataclass
class BatchInfo:
    """
    Batch processing information.
    
    Attributes:
        batch_documents: List of documents in the batch
        file_path: Path of the file currently being processed
        is_file_complete: True if this is the last batch from the current file
    """
    batch_documents: List[Dict[str, Any]]
    file_path: str
    is_file_complete: bool

