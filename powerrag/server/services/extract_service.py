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

"""PowerRAG Document Extraction Service"""

import re
import logging
from typing import Dict, Any, List
from collections import Counter

from api.db.services.document_service import DocumentService
from api.db.services.file2document_service import File2DocumentService
from rag.utils.storage_factory import STORAGE_IMPL

# ⚠️ 延迟导入 PdfParser，避免启动时加载 OCR 模型
# from deepdoc.parser import PdfParser as RAGFlowPdfParser

logger = logging.getLogger(__name__)


class PowerRAGExtractService:
    """Service for information extraction from documents"""
    
    def __init__(self):
        self.extractor_map = {
            "entity": self._extract_entities,
            "keyword": self._extract_keywords,
            "summary": self._extract_summary,
        }
    
    def extract_from_document(self, doc_id: str, extractor_type: str, 
                             config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract information from document
        
        Args:
            doc_id: Document ID
            extractor_type: Type of extractor (entity, keyword, summary)
            config: Extractor configuration
            
        Returns:
            Dict containing extracted information and metadata
        """
        try:
            # Get document
            exist, doc = DocumentService.get_by_id(doc_id)
            if not exist:
                raise ValueError(f"Document {doc_id} not found")
            
            # Get binary data and extract text
            bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
            binary = STORAGE_IMPL.get(bucket, name)
            
            if not binary:
                raise ValueError(f"Document binary not found for {doc_id}")
            
            text = self._extract_text(binary)
            
            # Extract information
            extractor_func = self.extractor_map.get(extractor_type)
            if not extractor_func:
                raise ValueError(f"Unsupported extractor type: {extractor_type}")
            
            result = extractor_func(text, config)
            
            return {
                "doc_id": doc_id,
                "doc_name": doc.name,
                "extractor_type": extractor_type,
                "data": result,
                "metadata": {
                    "extractor": "powerrag",
                    "config": config
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting from document {doc_id}: {e}", exc_info=True)
            raise
    
    def extract_from_text(self, text: str, extractor_type: str, 
                         config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information from raw text"""
        try:
            extractor_func = self.extractor_map.get(extractor_type)
            if not extractor_func:
                raise ValueError(f"Unsupported extractor type: {extractor_type}")
            
            result = extractor_func(text, config)
            
            return {
                "extractor_type": extractor_type,
                "data": result,
                "metadata": {
                    "extractor": "powerrag",
                    "config": config
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting from text: {e}", exc_info=True)
            raise
    
    def _extract_text(self, binary: bytes) -> str:
        """Extract text from binary document"""
        try:
            # 延迟导入：只在需要时才导入
            from deepdoc.parser import PdfParser as RAGFlowPdfParser
            parser = RAGFlowPdfParser()
            sections, _ = parser(binary, from_page=0, to_page=100000)
            
            text_parts = []
            for text, _ in sections:
                if text.strip():
                    text_parts.append(text.strip())
            
            return "\n\n".join(text_parts)
            
        except Exception:
            try:
                return binary.decode('utf-8')
            except Exception as e:
                logger.error(f"Error extracting text: {e}")
                raise
    
    def _extract_entities(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract named entities from text"""
        entity_types = config.get("entity_types", ["PERSON", "ORG", "EMAIL", "PHONE", "DATE"])
        
        entities = {}
        
        # Simple regex-based entity extraction
        patterns = {
            "PERSON": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            "ORG": r'\b[A-Z][A-Za-z\s&]+(?:Inc|Corp|LLC|Ltd|Company|Corporation)\b',
            "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "PHONE": r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            "DATE": r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
            "MONEY": r'\$[\d,]+(?:\.\d{2})?|\b\d+(?:\.\d{2})?\s*(?:dollars?|USD|EUR|GBP)\b',
        }
        
        for entity_type in entity_types:
            if entity_type in patterns:
                matches = re.findall(patterns[entity_type], text, re.IGNORECASE)
                if matches:
                    # Remove duplicates and filter
                    unique_matches = list(set(matches))
                    min_length = config.get("min_length", 2)
                    max_length = config.get("max_length", 50)
                    
                    filtered = [
                        m for m in unique_matches
                        if min_length <= len(m) <= max_length
                    ]
                    
                    if filtered:
                        entities[entity_type] = filtered
        
        return {
            "entities": entities,
            "entity_count": sum(len(v) for v in entities.values()),
            "entity_types": list(entities.keys())
        }
    
    def _extract_keywords(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract keywords from text"""
        max_keywords = config.get("max_keywords", 20)
        min_word_length = config.get("min_word_length", 3)
        remove_stopwords = config.get("remove_stopwords", True)
        
        # Tokenize
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # Filter by length
        words = [w for w in words if len(w) >= min_word_length]
        
        # Remove stopwords
        if remove_stopwords:
            stopwords = self._get_stopwords()
            words = [w for w in words if w not in stopwords]
        
        # Count frequencies
        word_counts = Counter(words)
        
        # Get top keywords
        total_words = len(words)
        keywords = []
        for word, count in word_counts.most_common(max_keywords):
            keywords.append({
                "keyword": word,
                "frequency": count,
                "score": count / total_words if total_words > 0 else 0
            })
        
        return {
            "keywords": keywords,
            "keyword_count": len(keywords),
            "total_words": total_words
        }
    
    def _extract_summary(self, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract/generate summary from text"""
        max_sentences = config.get("max_sentences", 3)
        max_length = config.get("max_length", 200)
        
        # Simple extractive summarization: take first and last sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= max_sentences:
            summary = ". ".join(sentences) + "."
        else:
            # Take first sentence and last sentence
            selected = [sentences[0]]
            if len(sentences) > 1:
                selected.append(sentences[-1])
            summary = ". ".join(selected) + "."
        
        # Truncate if too long
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return {
            "summary": summary,
            "summary_length": len(summary),
            "original_length": len(text),
            "compression_ratio": len(summary) / len(text) if len(text) > 0 else 0
        }
    
    def _get_stopwords(self) -> set:
        """Get common English stopwords"""
        return {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
            'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
            'from', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further',
            'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
            'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very'
        }




