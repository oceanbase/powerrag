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
PowerRAG Extractors

这些组件复用 powerrag.server.services.extract_service 的代码，
用于 PowerRAG Flow 流水线中的信息抽取。
"""

import logging
from typing import Dict, Any, List
from ..core.powerrag_base import PowerRAGComponentParam, PowerRAGComponent
from powerrag.server.services.extract_service import PowerRAGExtractService

logger = logging.getLogger(__name__)


class EntityExtractorParam(PowerRAGComponentParam):
    """Parameters for Entity Extractor"""
    
    def __init__(self):
        super().__init__()
        self.entity_types = ["PERSON", "ORG", "GPE", "MONEY", "DATE", "TIME", "EMAIL", "PHONE"]
        self.use_regex = True
        self.use_llm = False
        self.min_length = 2
        self.max_length = 50


class EntityExtractor(PowerRAGComponent):
    """
    Entity extractor for pipeline use
    
    Reuses PowerRAGExtractService for entity extraction.
    Supports regex-based and LLM-based extraction.
    """
    component_name = "EntityExtractor"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize extract service
        self._extract_service = PowerRAGExtractService()
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Extract entities from text
        
        Args:
            text: Text string to extract from
            entity_types: List of entity types to extract
            use_regex: Use regex-based extraction (default: True)
            use_llm: Use LLM-based extraction (default: False)
            min_length: Minimum entity length (default: 2)
            max_length: Maximum entity length (default: 50)
            
        Returns:
            Dict with 'entities', 'entity_count', 'metadata'
        """
        try:
            text = kwargs.get("text")
            if not text:
                raise ValueError("No text provided for entity extraction")
            
            # Build config
            config = {
                "entity_types": kwargs.get("entity_types", self._param.entity_types),
                "use_regex": kwargs.get("use_regex", self._param.use_regex),
                "use_llm": kwargs.get("use_llm", self._param.use_llm),
                "min_length": kwargs.get("min_length", self._param.min_length),
                "max_length": kwargs.get("max_length", self._param.max_length)
            }
            
            logger.info(f"Extracting entities from text ({len(text)} chars)")
            
            # Use PowerRAGExtractService
            result = self._extract_service.extract_from_text(
                text=text,
                extractor_type="entity",
                config=config
            )
            
            logger.info(f"Extracted {result.get('entity_count', 0)} entities")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract entities: {e}", exc_info=True)
            raise


# class KeywordExtractorParam(PowerRAGComponentParam):
#     """Parameters for Keyword Extractor"""
    
#     def __init__(self):
#         super().__init__()
#         self.max_keywords = 20
#         self.min_word_length = 3
#         self.remove_stopwords = True
#         self.use_tfidf = True
#         self.language = "english"


# class KeywordExtractor(PowerRAGComponent):
#     """
#     Keyword extractor for pipeline use
    
#     Reuses PowerRAGExtractService for keyword extraction.
#     Supports frequency-based and TF-IDF methods.
#     """
#     component_name = "KeywordExtractor"
    
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         # Initialize extract service
#         self._extract_service = PowerRAGExtractService()
    
#     async def _invoke(self, **kwargs) -> Dict[str, Any]:
#         """
#         Extract keywords from text
        
#         Args:
#             text: Text string to extract from
#             max_keywords: Maximum number of keywords (default: 20)
#             min_word_length: Minimum word length (default: 3)
#             remove_stopwords: Remove stopwords (default: True)
#             use_tfidf: Use TF-IDF scoring (default: True)
#             language: Language for stopwords (default: "english")
            
#         Returns:
#             Dict with 'keywords', 'keyword_count', 'metadata'
#         """
#         try:
#             text = kwargs.get("text")
#             if not text:
#                 raise ValueError("No text provided for keyword extraction")
            
#             # Build config
#             config = {
#                 "max_keywords": kwargs.get("max_keywords", self._param.max_keywords),
#                 "min_word_length": kwargs.get("min_word_length", self._param.min_word_length),
#                 "remove_stopwords": kwargs.get("remove_stopwords", self._param.remove_stopwords),
#                 "use_tfidf": kwargs.get("use_tfidf", self._param.use_tfidf),
#                 "language": kwargs.get("language", self._param.language)
#             }
            
#             logger.info(f"Extracting keywords from text ({len(text)} chars)")
            
#             # Use PowerRAGExtractService
#             result = self._extract_service.extract_from_text(
#                 text=text,
#                 extractor_type="keyword",
#                 config=config
#             )
            
#             logger.info(f"Extracted {result.get('keyword_count', 0)} keywords")
            
#             return result
            
#         except Exception as e:
#             logger.error(f"Failed to extract keywords: {e}", exc_info=True)
#             raise


# class SummaryExtractorParam(PowerRAGComponentParam):
#     """Parameters for Summary Extractor"""
    
#     def __init__(self):
#         super().__init__()
#         self.summary_type = "abstractive"  # abstractive or extractive
#         self.max_length = 200
#         self.min_length = 50
#         self.use_llm = False  # Set to False by default to avoid LLM dependency
#         self.language = "english"


# class SummaryExtractor(PowerRAGComponent):
    """
    Summary extractor for pipeline use
    
    Reuses PowerRAGExtractService for summary generation.
    Supports both extractive and abstractive summarization.
    """
    component_name = "SummaryExtractor"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize extract service
        self._extract_service = PowerRAGExtractService()
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Generate summary from text
        
        Args:
            text: Text string to summarize
            summary_type: "abstractive" or "extractive" (default: "abstractive")
            max_length: Maximum summary length (default: 200)
            min_length: Minimum summary length (default: 50)
            use_llm: Use LLM for summarization (default: False)
            language: Language (default: "english")
            
        Returns:
            Dict with 'summary', 'summary_type', 'length', 'metadata'
        """
        try:
            text = kwargs.get("text")
            if not text:
                raise ValueError("No text provided for summarization")
            
            # Build config
            config = {
                "summary_type": kwargs.get("summary_type", self._param.summary_type),
                "max_length": kwargs.get("max_length", self._param.max_length),
                "min_length": kwargs.get("min_length", self._param.min_length),
                "use_llm": kwargs.get("use_llm", self._param.use_llm),
                "language": kwargs.get("language", self._param.language)
            }
            
            logger.info(f"Generating summary from text ({len(text)} chars)")
            
            # Use PowerRAGExtractService
            result = self._extract_service.extract_from_text(
                text=text,
                extractor_type="summary",
                config=config
            )
            
            summary = result.get('data', {}).get('summary', '')
            logger.info(f"Generated summary ({len(summary)} chars)")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}", exc_info=True)
            raise


# class BatchExtractorParam(PowerRAGComponentParam):
#     """
#     Parameters for Batch Extractor
    
#     Extracts all types of information in a single pass.
#     """
    
#     def __init__(self):
#         super().__init__()
#         self.extract_entities = True
#         self.extract_keywords = True
#         self.extract_summary = True
#         self.entity_types = ["PERSON", "ORG", "GPE", "MONEY", "DATE", "TIME", "EMAIL", "PHONE"]
#         self.max_keywords = 20
#         self.summary_max_length = 200


# class BatchExtractor(PowerRAGComponent):
#     """
#     Batch Extractor for pipeline use
    
#     Extracts multiple types of information (entities, keywords, summary)
#     in a single operation using PowerRAGExtractService.
#     """
#     component_name = "BatchExtractor"
    
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         # Initialize extract service
#         self._extract_service = PowerRAGExtractService()
    
#     async def _invoke(self, **kwargs) -> Dict[str, Any]:
#         """
#         Extract all information types from text
        
#         Args:
#             text: Text string to extract from
#             extract_entities: Extract entities (default: True)
#             extract_keywords: Extract keywords (default: True)
#             extract_summary: Generate summary (default: True)
            
#         Returns:
#             Dict with 'entities', 'keywords', 'summary', 'metadata'
#         """
#         try:
#             text = kwargs.get("text")
#             if not text:
#                 raise ValueError("No text provided for extraction")
            
#             result = {
#                 "text_length": len(text),
#                 "metadata": {
#                     "extractor": "powerrag_batch",
#                     "text_preview": text[:200] if len(text) > 200 else text
#                 }
#             }
            
#             logger.info(f"Batch extracting from text ({len(text)} chars)")
            
#             # Extract entities
#             if kwargs.get("extract_entities", self._param.extract_entities):
#                 entity_config = {
#                     "entity_types": kwargs.get("entity_types", self._param.entity_types),
#                     "use_regex": True,
#                     "use_llm": False
#                 }
#                 entities_result = self._extract_service.extract_from_text(
#                     text=text,
#                     extractor_type="entity",
#                     config=entity_config
#                 )
#                 result["entities"] = entities_result.get("data", {})
            
#             # Extract keywords
#             if kwargs.get("extract_keywords", self._param.extract_keywords):
#                 keyword_config = {
#                     "max_keywords": kwargs.get("max_keywords", self._param.max_keywords),
#                     "min_word_length": 3,
#                     "remove_stopwords": True
#                 }
#                 keywords_result = self._extract_service.extract_from_text(
#                     text=text,
#                     extractor_type="keyword",
#                     config=keyword_config
#                 )
#                 result["keywords"] = keywords_result.get("data", {})
            
#             # Generate summary
#             if kwargs.get("extract_summary", self._param.extract_summary):
#                 summary_config = {
#                     "summary_type": "extractive",
#                     "max_length": kwargs.get("summary_max_length", self._param.summary_max_length),
#                     "use_llm": False
#                 }
#                 summary_result = self._extract_service.extract_from_text(
#                     text=text,
#                     extractor_type="summary",
#                     config=summary_config
#                 )
#                 result["summary"] = summary_result.get("data", {})
            
#             logger.info("Batch extraction completed successfully")
            
#             return result
            
#         except Exception as e:
#             logger.error(f"Failed batch extraction: {e}", exc_info=True)
#             raise
