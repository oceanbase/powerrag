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
PowerRAG Parsers

这些组件复用 powerrag.server.services.convert_service 的代码，
用于 PowerRAG Flow 流水线中的文档解析。

Parsers 负责将文档解析为文本/Markdown：
- PDF → Markdown (via convert_service._pdf_to_markdown)
- Office → PDF → Markdown (via convert_service)
- HTML → PDF → Markdown (via convert_service)
"""

import logging
from typing import Dict, Any
from ..core.powerrag_base import PowerRAGComponentParam, PowerRAGComponent
from powerrag.server.services.convert_service import PowerRAGConvertService
from api.utils.configs import get_base_config

logger = logging.getLogger(__name__)


class PDFParserParam(PowerRAGComponentParam):
    """
    Parameters for PDF Parser
    
    Uses PowerRAG MinerU parser for high-quality PDF parsing.
    """
    
    def __init__(self):
        super().__init__()
        self.component_type = "parser"
        self.formula_enable = True
        self.enable_ocr = False
        self.from_page = 0
        self.to_page = 100000
        self.output_format = "markdown"  # Always markdown for consistency


class PDFParser(PowerRAGComponent):
    """
    PDF parser for pipeline use
    
    Reuses PowerRAGConvertService._pdf_to_markdown() which uses MinerU parser.
    This ensures consistent PDF parsing across the entire PowerRAG system.
    """
    component_name = "PDFParser"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize convert service (no gotenberg_url needed for PDF parsing)
        self._convert_service = PowerRAGConvertService()
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Parse PDF document to Markdown
        
        Args:
            file: Dict with 'name' and 'blob' keys
            formula_enable: Enable formula recognition (default: True)
            enable_ocr: Enable OCR (default: False)
            from_page: Start page (default: 0)
            to_page: End page (default: 100000)
            
        Returns:
            Dict with 'text', 'format', 'metadata'
        """
        try:
            # Get input file data
            file_data = kwargs.get("file")
            if not file_data:
                raise ValueError("No file data provided for parsing")
            
            filename = file_data.get("name", "")
            binary = file_data.get("blob")
            
            if not binary:
                raise ValueError("No binary data provided for parsing")
            
            logger.info(f"Parsing PDF to Markdown using MinerU: {filename}")
            
            # Build config for MinerU parser
            config = {
                'filename': filename,
                'formula_enable': kwargs.get('formula_enable', self._param.formula_enable),
                'enable_ocr': kwargs.get('enable_ocr', self._param.enable_ocr),
                'from_page': kwargs.get('from_page', self._param.from_page),
                'to_page': kwargs.get('to_page', self._param.to_page)
            }
            
            # Use PowerRAGConvertService._pdf_to_markdown() for parsing
            markdown_content = self._convert_service._pdf_to_markdown(binary, config)
            
            result = {
                "text": markdown_content,
                "format": "markdown",
                "length": len(markdown_content),
                "metadata": {
                    "parser": "powerrag_mineru",
                    "filename": filename,
                    "config": config,
                    "component": "PDFParser"
                }
            }
            
            logger.info(f"Successfully parsed PDF {filename} to Markdown ({len(markdown_content)} chars)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse PDF {filename}: {e}", exc_info=True)
            raise


# class OfficeParserParam(PowerRAGComponentParam):
#     """
#     Parameters for Office Document Parser
    
#     Converts Office documents to PDF first, then parses to Markdown.
#     """
    
#     def __init__(self):
#         super().__init__()
#         self.component_type = "parser"
#         self.gotenberg_url = None  # Will use config from service_conf.yaml if not provided
#         self.formula_enable = True
#         self.enable_ocr = False
#         self.output_format = "markdown"


# class OfficeParser(PowerRAGComponent):
#     """
#     Office document parser (Word, Excel, PowerPoint)
    
#     Two-step process:
#     1. Office → PDF (via PowerRAGConvertService.convert_to_pdf)
#     2. PDF → Markdown (via PowerRAGConvertService._pdf_to_markdown)
    
#     This ensures consistent parsing results across all document types.
#     """
#     component_name = "OfficeParser"
    
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         # Get Gotenberg URL from config or use default
#         gotenberg_config = get_base_config("gotenberg", {})
#         gotenberg_url = self._param.gotenberg_url or gotenberg_config.get("url", "http://localhost:3000")
#         # Initialize convert service with Gotenberg URL
#         self._convert_service = PowerRAGConvertService(gotenberg_url=gotenberg_url)
    
#     async def _invoke(self, **kwargs) -> Dict[str, Any]:
#         """
#         Parse Office document to Markdown
        
#         Process:
#         1. Convert Office document to PDF via Gotenberg
#         2. Parse PDF to Markdown via MinerU
        
#         Args:
#             file: Dict with 'name' and 'blob' keys
#             formula_enable: Enable formula recognition (default: True)
#             enable_ocr: Enable OCR (default: False)
            
#         Returns:
#             Dict with 'text', 'format', 'metadata'
#         """
#         try:
#             # Get input file data
#             file_data = kwargs.get("file")
#             if not file_data:
#                 raise ValueError("No file data provided for parsing")
            
#             filename = file_data.get("name", "")
#             binary = file_data.get("blob")
            
#             if not binary:
#                 raise ValueError("No binary data provided for parsing")
            
#             logger.info(f"Parsing Office document: {filename}")
            
#             # Step 1: Convert Office to PDF
#             logger.info(f"Step 1: Converting Office document to PDF via Gotenberg")
#             pdf_binary = self._convert_service.convert_to_pdf(
#                 filename=filename,
#                 binary=binary,
#                 format_type='office'
#             )
            
#             # Step 2: Parse PDF to Markdown
#             logger.info(f"Step 2: Parsing PDF to Markdown via MinerU")
#             pdf_config = {
#                 'filename': filename.rsplit('.', 1)[0] + '.pdf',
#                 'formula_enable': kwargs.get('formula_enable', self._param.formula_enable),
#                 'enable_ocr': kwargs.get('enable_ocr', self._param.enable_ocr),
#                 'from_page': 0,
#                 'to_page': 100000
#             }
#             markdown_content = self._convert_service._pdf_to_markdown(pdf_binary, pdf_config)
            
#             result = {
#                 "text": markdown_content,
#                 "format": "markdown",
#                 "length": len(markdown_content),
#                 "metadata": {
#                     "parser": "powerrag_office",
#                     "filename": filename,
#                     "process": [
#                         "office_to_pdf (Gotenberg)",
#                         "pdf_to_markdown (MinerU)"
#                     ],
#                     "component": "OfficeParser"
#                 }
#             }
            
#             logger.info(f"Successfully parsed Office document {filename} to Markdown ({len(markdown_content)} chars)")
#             return result
            
#         except Exception as e:
#             logger.error(f"Failed to parse Office document {filename}: {e}", exc_info=True)
#             raise


# class HTMLParserParam(PowerRAGComponentParam):
#     """
#     Parameters for HTML Document Parser
    
#     Converts HTML to PDF first, then parses to Markdown.
#     """
    
#     def __init__(self):
#         super().__init__()
#         self.component_type = "parser"
#         self.gotenberg_url = None  # Will use config from service_conf.yaml if not provided
#         self.formula_enable = False  # HTML usually doesn't have formulas
#         self.enable_ocr = False
#         self.output_format = "markdown"


# class HTMLParser(PowerRAGComponent):
#     """
#     HTML document parser
    
#     Two-step process:
#     1. HTML → PDF (via PowerRAGConvertService.convert_to_pdf)
#     2. PDF → Markdown (via PowerRAGConvertService._pdf_to_markdown)
#     """
#     component_name = "HTMLParser"
    
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         # Get Gotenberg URL from config or use default
#         gotenberg_config = get_base_config("gotenberg", {})
#         gotenberg_url = self._param.gotenberg_url or gotenberg_config.get("url", "http://localhost:3000")
#         # Initialize convert service with Gotenberg URL
#         self._convert_service = PowerRAGConvertService(gotenberg_url=gotenberg_url)
    
#     async def _invoke(self, **kwargs) -> Dict[str, Any]:
#         """
#         Parse HTML document to Markdown
        
#         Process:
#         1. Convert HTML to PDF via Gotenberg
#         2. Parse PDF to Markdown via MinerU
        
#         Args:
#             file: Dict with 'name' and 'blob' keys
#             formula_enable: Enable formula recognition (default: False)
#             enable_ocr: Enable OCR (default: False)
            
#         Returns:
#             Dict with 'text', 'format', 'metadata'
#         """
#         try:
#             # Get input file data
#             file_data = kwargs.get("file")
#             if not file_data:
#                 raise ValueError("No file data provided for parsing")
            
#             filename = file_data.get("name", "")
#             binary = file_data.get("blob")
            
#             if not binary:
#                 raise ValueError("No binary data provided for parsing")
            
#             logger.info(f"Parsing HTML document: {filename}")
            
#             # Step 1: Convert HTML to PDF
#             logger.info(f"Step 1: Converting HTML to PDF via Gotenberg")
#             pdf_binary = self._convert_service.convert_to_pdf(
#                 filename=filename,
#                 binary=binary,
#                 format_type='html'
#             )
            
#             # Step 2: Parse PDF to Markdown
#             logger.info(f"Step 2: Parsing PDF to Markdown via MinerU")
#             pdf_config = {
#                 'filename': filename.rsplit('.', 1)[0] + '.pdf',
#                 'formula_enable': kwargs.get('formula_enable', self._param.formula_enable),
#                 'enable_ocr': kwargs.get('enable_ocr', self._param.enable_ocr),
#                 'from_page': 0,
#                 'to_page': 100000
#             }
#             markdown_content = self._convert_service._pdf_to_markdown(pdf_binary, pdf_config)
            
#             result = {
#                 "text": markdown_content,
#                 "format": "markdown",
#                 "length": len(markdown_content),
#                 "metadata": {
#                     "parser": "powerrag_html",
#                     "filename": filename,
#                     "process": [
#                         "html_to_pdf (Gotenberg)",
#                         "pdf_to_markdown (MinerU)"
#                     ],
#                     "component": "HTMLParser"
#                 }
#             }
            
#             logger.info(f"Successfully parsed HTML document {filename} to Markdown ({len(markdown_content)} chars)")
#             return result
            
#         except Exception as e:
#             logger.error(f"Failed to parse HTML document {filename}: {e}", exc_info=True)
#             raise
