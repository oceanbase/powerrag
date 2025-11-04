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
PowerRAG Converters

这些组件复用 powerrag.server.services.convert_service 的代码，
用于 PowerRAG Flow 流水线中的文档格式转换。
"""

import logging
import os
from typing import Dict, Any
from ..core.powerrag_base import PowerRAGComponentParam, PowerRAGComponent
from powerrag.server.services.convert_service import PowerRAGConvertService
from api.utils.configs import get_base_config

logger = logging.getLogger(__name__)


class DocumentToPDFParam(PowerRAGComponentParam):
    """Parameters for Document to PDF Converter"""
    
    def __init__(self):
        super().__init__()
        self.component_type = "converter"
        self.supported_extensions = ["docx", "doc", "xlsx", "xls", "pptx", "ppt", "html", "htm"]
        self.format_type = "office"  # office or html
        self.gotenberg_url = None  # Will use config from service_conf.yaml if not provided


class DocumentToPDF(PowerRAGComponent):
    """
    Document to PDF converter for pipeline use
    
    Reuses PowerRAGConvertService for actual conversion.
    Supports:
    - Office documents (Word, Excel, PowerPoint) → PDF
    - HTML documents → PDF
    """
    component_name = "DocumentToPDF"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Get Gotenberg URL from config or use default
        gotenberg_config = get_base_config("gotenberg", {})
        gotenberg_url = self._param.gotenberg_url or gotenberg_config.get("url", "http://localhost:3000")
        # Initialize convert service
        self._convert_service = PowerRAGConvertService(gotenberg_url=gotenberg_url)
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Convert document to PDF implementation
        
        Args:
            file: Dict with 'name' and 'blob' keys
            format_type: 'office' or 'html'
            
        Returns:
            Dict with 'pdf_binary', 'filename', 'size', 'format_type'
        """
        try:
            # Get input file data
            file_data = kwargs.get("file")
            if not file_data:
                raise ValueError("No file data provided for conversion")
            
            filename = file_data.get("name", "")
            binary = file_data.get("blob")
            
            if not binary:
                raise ValueError("No binary data provided for conversion")
            
            # Determine format type from filename if not specified
            format_type = kwargs.get("format_type") or self._param.format_type
            if format_type not in ['office', 'html']:
                # Try to infer from extension
                ext = filename.lower().split('.')[-1]
                if ext in ['html', 'htm']:
                    format_type = 'html'
                else:
                    format_type = 'office'
            
            logger.info(f"Converting {format_type} document to PDF: {filename}")
            
            # Use PowerRAGConvertService for conversion
            pdf_binary = self._convert_service.convert_to_pdf(
                filename=filename,
                binary=binary,
                format_type=format_type
            )
            
            result = {
                "pdf_binary": pdf_binary,
                "filename": filename.rsplit('.', 1)[0] + '.pdf',
                "size": len(pdf_binary),
                "format_type": format_type,
                "metadata": {
                    "converter": "powerrag_gotenberg",
                    "original_filename": filename,
                    "original_format": format_type
                }
            }
            
            logger.info(f"Successfully converted {filename} to PDF ({len(pdf_binary)} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to convert {filename} to PDF: {e}", exc_info=True)
            raise


class PDFToMarkdownParam(PowerRAGComponentParam):
    """Parameters for PDF to Markdown Converter"""
    
    def __init__(self):
        super().__init__()
        self.component_type = "converter"
        self.formula_enable = True
        self.enable_ocr = False
        self.from_page = 0
        self.to_page = 100000


class PDFToMarkdown(PowerRAGComponent):
    """
    PDF to Markdown converter for pipeline use
    
    Reuses PowerRAGConvertService._pdf_to_markdown() which uses MinerU parser.
    """
    component_name = "PDFToMarkdown"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize convert service (gotenberg_url not needed for PDF→MD)
        self._convert_service = PowerRAGConvertService()
    
    async def _invoke(self, **kwargs) -> Dict[str, Any]:
        """
        Convert PDF to Markdown
        
        Args:
            file: Dict with 'name' and 'blob' keys
            formula_enable: Enable formula recognition (default: True)
            enable_ocr: Enable OCR (default: False)
            from_page: Start page (default: 0)
            to_page: End page (default: 100000)
            
        Returns:
            Dict with 'markdown_content', 'filename', 'length'
        """
        try:
            # Get input file data
            file_data = kwargs.get("file")
            if not file_data:
                raise ValueError("No file data provided for conversion")
            
            filename = file_data.get("name", "")
            binary = file_data.get("blob")
            
            if not binary:
                raise ValueError("No binary data provided for conversion")
            
            logger.info(f"Converting PDF to Markdown using MinerU: {filename}")
            
            # Build config
            config = {
                'filename': filename,
                'model': kwargs.get('layout_enable', self._param.model),
                'from_page': kwargs.get('from_page', self._param.from_page),
                'to_page': kwargs.get('to_page', self._param.to_page)
            }
            
            # Use PowerRAGConvertService._pdf_to_markdown()
            markdown_content = self._convert_service._pdf_to_markdown(binary, config)
            
            result = {
                "markdown_content": markdown_content,
                "filename": filename.rsplit('.', 1)[0] + '.md',
                "length": len(markdown_content),
                "metadata": {
                    "converter": "powerrag_mineru",
                    "original_filename": filename,
                    "config": config
                }
            }
            
            logger.info(f"Successfully converted {filename} to Markdown ({len(markdown_content)} chars)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to convert {filename} to Markdown: {e}", exc_info=True)
            raise
