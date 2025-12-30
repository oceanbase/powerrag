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

from typing import Dict, Any, Optional, List, Union
import logging

from .models import FieldMappingConfig, Document, DocumentMetadata


class FieldMapper:
    """
    Field mapper for converting source document fields to RAGFlow standard format.
    
    Standard fields:
    - title: Document title
    - content: Document content
    - metadata.doc_id: Document ID
    - metadata.doc_url: Document URL
    - metadata.tags: List of tags
    """
    
    # Default field mappings
    DEFAULT_MAPPINGS = {
        'title': ['title', 'name', 'subject', 'heading', 'header'],
        'content': ['content', 'text', 'body', 'description', 'desc', 'data'],
        'doc_id': ['id', 'doc_id', '_id', 'document_id', 'docid'],
        'doc_url': ['url', 'link', 'uri', 'doc_url', 'source_url'],
        'tags': ['tags', 'tag', 'categories', 'category', 'labels', 'label']
    }
    
    def __init__(
        self,
        title_field: Optional[str] = None,
        content_field: Optional[str] = None,
        doc_id_field: Optional[str] = None,
        doc_url_field: Optional[str] = None,
        tags_field: Optional[str] = None,
        tags_separator: str = ',',
        config: Optional[FieldMappingConfig] = None
    ):
        """
        Initialize FieldMapper with custom field mappings.
        
        Args:
            title_field: Source field name for title (None = auto-detect)
            content_field: Source field name for content (None = auto-detect)
            doc_id_field: Source field name for doc_id (None = auto-detect)
            doc_url_field: Source field name for doc_url (None = auto-detect)
            tags_field: Source field name for tags (None = auto-detect)
            tags_separator: Separator for tags string (default: ',')
            config: Optional FieldMappingConfig instance (if provided, overrides individual fields)
        """
        if config:
            self.title_field = config.title_field
            self.content_field = config.content_field
            self.doc_id_field = config.doc_id_field
            self.doc_url_field = config.doc_url_field
            self.tags_field = config.tags_field
            self.tags_separator = config.tags_separator
        else:
            self.title_field = title_field
            self.content_field = content_field
            self.doc_id_field = doc_id_field
            self.doc_url_field = doc_url_field
            self.tags_field = tags_field
            self.tags_separator = tags_separator
        self.logger = logging.getLogger(__name__)
    
    def _find_field(self, doc: Dict[str, Any], candidates: List[str]) -> Optional[str]:
        """
        Find field name in document using candidate names.
        
        Args:
            doc: Document dictionary
            candidates: List of candidate field names
            
        Returns:
            Found field name or None
        """
        # Check exact match first (case-insensitive)
        doc_keys_lower = {k.lower(): k for k in doc.keys()}
        for candidate in candidates:
            if candidate.lower() in doc_keys_lower:
                return doc_keys_lower[candidate.lower()]
        return None
    
    def _extract_field(self, doc: Dict[str, Any], field_name: Optional[str], 
                      candidates: List[str], default: Any = None) -> Any:
        """
        Extract field value from document.
        
        Args:
            doc: Document dictionary
            field_name: Explicit field name (if provided)
            candidates: List of candidate field names for auto-detection
            default: Default value if field not found
            
        Returns:
            Field value or default
        """
        if field_name:
            # Use explicit field name
            return doc.get(field_name, default)
        
        # Auto-detect field name
        found_field = self._find_field(doc, candidates)
        if found_field:
            return doc.get(found_field, default)
        
        return default
    
    def _parse_tags(self, tags_value: Any) -> List[str]:
        """
        Parse tags from various formats.
        
        Supports:
        - Array format: ["tag1", "tag2", "tag3"]
        - Comma-separated string: "tag1, tag2, tag3" or "tag1,tag2,tag3" (spaces are trimmed)
        
        Args:
            tags_value: Tags value (can be string, list, or None)
            
        Returns:
            List of tag strings (empty strings and None values are filtered out)
        """
        if tags_value is None:
            return []
        
        if isinstance(tags_value, list):
            # Array format: ["tag1", "tag2", "tag3"]
            return [str(tag).strip() for tag in tags_value if tag and str(tag).strip()]
        
        if isinstance(tags_value, str):
            # Comma-separated string: "tag1, tag2, tag3" or "tag1,tag2,tag3"
            if not tags_value.strip():
                return []
            # Split by separator and strip whitespace from each tag
            return [tag.strip() for tag in tags_value.split(self.tags_separator) if tag.strip()]
        
        # Convert to string and parse as single tag
        tag_str = str(tags_value).strip()
        return [tag_str] if tag_str else []
    
    def map(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map source document to RAGFlow standard format.
        
        Args:
            doc: Source document dictionary
            
        Returns:
            Mapped document in RAGFlow format:
            {
                'title': str,
                'content': str,
                'metadata': {
                    'doc_id': str (optional),
                    'doc_url': str (optional),
                    'tags': List[str] (optional)
                }
            }
        """
        # Extract fields
        title = self._extract_field(
            doc, self.title_field, 
            self.DEFAULT_MAPPINGS['title'], 
            default=''
        )
        
        content = self._extract_field(
            doc, self.content_field,
            self.DEFAULT_MAPPINGS['content'],
            default=''
        )
        
        doc_id = self._extract_field(
            doc, self.doc_id_field,
            self.DEFAULT_MAPPINGS['doc_id'],
            default=None
        )
        
        doc_url = self._extract_field(
            doc, self.doc_url_field,
            self.DEFAULT_MAPPINGS['doc_url'],
            default=None
        )
        
        tags_value = self._extract_field(
            doc, self.tags_field,
            self.DEFAULT_MAPPINGS['tags'],
            default=None
        )
        
        tags = self._parse_tags(tags_value)
        
        # Build metadata entity
        metadata = None
        if doc_id is not None or doc_url is not None or tags:
            metadata = DocumentMetadata(
                doc_id=str(doc_id) if doc_id is not None else None,
                doc_url=str(doc_url) if doc_url is not None else None,
                tags=tags if tags else None
            )
        
        # Build result document
        doc = Document(
            title=str(title) if title else '',
            content=str(content) if content else '',
            metadata=metadata
        )
        
        return doc.to_dict()

