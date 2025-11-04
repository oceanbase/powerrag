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
PowerRAG Splitters

这些组件复用 powerrag.server.services.split_service 的代码，
用于 PowerRAG Flow 流水线中的文本切片。
"""

import logging
from typing import List, Dict, Any
from ..core.powerrag_base import PowerRAGComponentParam, PowerRAGComponent
from powerrag.server.services.split_service import PowerRAGSplitService

logger = logging.getLogger(__name__)


class PowerRAGTextSplitterParam(PowerRAGComponentParam):
    """
    Parameters for PowerRAG Text Splitter
    
    Supports all parsers from powerrag/app and rag/app:
    - title (PowerRAG custom)
    - naive, paper, book, presentation, manual
    - laws, qa, table, resume, picture, one
    - audio, email, tag
    """
    
    def __init__(self):
        super().__init__()
        self.parser_id = "title"  # Default to PowerRAG title parser
        self.title_level = 3
        self.chunk_token_num = 256
        self.delimiter = "\n!?;。；！？"
        self.lang = "Chinese"


class PowerRAGTextSplitter(PowerRAGComponent):
    """
    PowerRAG Text Splitter for pipeline use
    
    Reuses PowerRAGSplitService which supports 20+ parsers.
    This is the recommended splitter for PowerRAG pipelines.
    """
    component_name = "PowerRAGTextSplitter"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize split service
        self._split_service = PowerRAGSplitService()
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Split text using PowerRAG split service
        
        Args:
            text: Text string to split (str type, usually markdown format)
            parser_id: Parser/chunker ID (default: "title")
            config: Chunking configuration
            
        Returns:
            Dict with 'chunks', 'parser_id', 'total_chunks', 'metadata'
        """
        try:
            text = kwargs.get("text")
            if not text:
                raise ValueError("No text provided for splitting")
            
            if not isinstance(text, str):
                raise TypeError(f"text must be str type, got {type(text)}")
            
            parser_id = kwargs.get("parser_id", self._param.parser_id)
            
            # Build config from params and kwargs
            config = {
                "title_level": kwargs.get("title_level", self._param.title_level),
                "chunk_token_num": kwargs.get("chunk_token_num", self._param.chunk_token_num),
                "delimiter": kwargs.get("delimiter", self._param.delimiter),
                "lang": kwargs.get("lang", self._param.lang)
            }
            
            logger.info(f"Splitting text using parser '{parser_id}' ({len(text)} chars)")
            
            # Use PowerRAGSplitService for splitting
            result = self._split_service.split_text(text, parser_id, config)
            
            logger.info(f"Split text into {result['total_chunks']} chunks using parser '{parser_id}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to split text: {e}", exc_info=True)
            raise


class TitleBasedSplitterParam(PowerRAGComponentParam):
    """
    Parameters for Title-Based Splitter (PowerRAG title parser)
    """
    
    def __init__(self):
        super().__init__()
        self.title_level = 3  # Split at h1-h3 level
        self.chunk_token_num = 256
        self.delimiter = "\n!?;。；！？"
        self.layout_recognize = "markdown"


class TitleBasedSplitter(PowerRAGComponent):
    """
    Title-Based Splitter using PowerRAG title parser
    
    This is a convenience component that uses PowerRAGTextSplitter
    with parser_id="title".
    """
    component_name = "TitleBasedSplitter"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize split service
        self._split_service = PowerRAGSplitService()
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Split text using title-based strategy
        
        Args:
            text: Text string (usually markdown with title markers)
            title_level: Title level to split at (1-6, default: 3)
            chunk_token_num: Target chunk size in tokens (default: 256)
            delimiter: Sentence delimiters (default: "\n!?;。；！？")
            
        Returns:
            Dict with 'chunks', 'total_chunks', 'metadata'
        """
        try:
            text = kwargs.get("text")
            if not text:
                raise ValueError("No text provided for splitting")
            
            # Build config
            config = {
                "title_level": kwargs.get("title_level", self._param.title_level),
                "chunk_token_num": kwargs.get("chunk_token_num", self._param.chunk_token_num),
                "delimiter": kwargs.get("delimiter", self._param.delimiter),
                "layout_recognize": kwargs.get("layout_recognize", self._param.layout_recognize)
            }
            
            logger.info(f"Splitting text using title-based strategy (level={config['title_level']})")
            
            # Use PowerRAGSplitService with parser_id="title"
            result = self._split_service.split_text(text, "title", config)
            
            logger.info(f"Split text into {result['total_chunks']} title-based chunks")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to split text with title-based strategy: {e}", exc_info=True)
            raise
