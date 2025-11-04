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

"""PowerRAG Document Conversion Service

This service handles document format conversions:
1. Office/HTML → PDF (using Gotenberg)
2. PDF → Markdown (using PowerRAG MinerU parser)
"""

import io
import logging
import requests
from typing import Dict, Any

from api.db.services.document_service import DocumentService
from api.db.services.file2document_service import File2DocumentService
from rag.utils.storage_factory import STORAGE_IMPL
from powerrag.parser import MinerUPdfParser, DotsOcrParser

logger = logging.getLogger(__name__)


class PowerRAGConvertService:
    """Service for document format conversion
    
    Supports:
    - Office/HTML → PDF (via Gotenberg)
    - PDF → Markdown (via PowerRAG MinerU parser)
    """
    
    def __init__(self, gotenberg_url: str = "http://localhost:3000", doc_id: str = "default"):
        """
        Initialize conversion service
        
        Args:
            gotenberg_url: URL of Gotenberg service for Office/HTML → PDF conversion
        """
        self.gotenberg_url = gotenberg_url
        self.doc_id = doc_id
        self.converter_map = {
            # PDF to Markdown conversion (using PowerRAG MinerU parser)
            ("pdf", "markdown"): self._pdf_to_markdown,
            # Office/HTML to PDF conversions (using Gotenberg)
            ("office", "pdf"): self._office_to_pdf,
            ("html", "pdf"): self._html_to_pdf,
        }
    
    def convert_document(self, doc_id: str, source_format: str, target_format: str, 
                        config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert document format
        
        Args:
            doc_id: Document ID
            source_format: Source format (pdf, office, html)
            target_format: Target format (markdown, pdf)
            config: Conversion configuration
            
        Returns:
            Dict containing converted content and metadata
            
        Supported conversions:
        - pdf → markdown (using PowerRAG MinerU parser)
        - office → pdf (using Gotenberg)
        - html → pdf (using Gotenberg)
        """
        try:
            # Get document
            exist, doc = DocumentService.get_by_id(doc_id)
            if not exist:
                raise ValueError(f"Document {doc_id} not found")
            
            # Get binary data
            bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
            binary = STORAGE_IMPL.get(bucket, name)
            
            if not binary:
                raise ValueError(f"Document binary not found for {doc_id}")
            
            # Add filename to config for converters
            if 'filename' not in config:
                config['filename'] = doc.name
            
            # Convert
            converter_key = (source_format.lower(), target_format.lower())
            converter_func = self.converter_map.get(converter_key)
            
            if not converter_func:
                supported = ", ".join([f"{s}→{t}" for s, t in self.converter_map.keys()])
                raise ValueError(
                    f"Conversion from {source_format} to {target_format} not supported. "
                    f"Supported conversions: {supported}"
                )
            
            content = converter_func(binary, config)
            
            return {
                "doc_id": doc_id,
                "doc_name": doc.name,
                "source_format": source_format,
                "target_format": target_format,
                "content": content,
                "content_length": len(content) if isinstance(content, (str, bytes)) else 0,
                "metadata": {
                    "converter": "powerrag_mineru" if target_format == "markdown" else "gotenberg",
                    "config": config
                }
            }
            
        except Exception as e:
            logger.error(f"Error converting document {doc_id}: {e}", exc_info=True)
            raise
    
    def convert_file_binary(self, binary: bytes, source_format: str, target_format: str,
                           config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert file binary directly (without doc_id)
        
        Args:
            binary: File binary data
            source_format: Source format (pdf, office, html)
            target_format: Target format (markdown, pdf)
            config: Conversion configuration (must include 'filename')
            
        Returns:
            Dict containing converted content and metadata
            
        Supported conversions:
        - pdf → markdown (using PowerRAG MinerU parser)
        - office → pdf (using Gotenberg)
        - html → pdf (using Gotenberg)
        """
        try:
            # Validate filename in config
            if 'filename' not in config:
                raise ValueError("config must include 'filename' parameter")
            
            filename = config['filename']
            
            # Convert
            converter_key = (source_format.lower(), target_format.lower())
            converter_func = self.converter_map.get(converter_key)
            
            if not converter_func:
                supported = ", ".join([f"{s}→{t}" for s, t in self.converter_map.keys()])
                raise ValueError(
                    f"Conversion from {source_format} to {target_format} not supported. "
                    f"Supported conversions: {supported}"
                )
            
            content = converter_func(binary, config)
            
            return {
                "filename": filename,
                "source_format": source_format,
                "target_format": target_format,
                "content": content,
                "content_length": len(content) if isinstance(content, (str, bytes)) else 0,
                "metadata": {
                    "converter": "powerrag_mineru" if target_format == "markdown" else "gotenberg",
                    "config": config
                }
            }
            
        except Exception as e:
            logger.error(f"Error converting file binary: {e}", exc_info=True)
            raise
    
    def _pdf_to_markdown(self, binary: bytes, config: Dict[str, Any]) -> str:
        """
        Convert PDF to Markdown using PowerRAG MinerU parser
        
        Args:
            binary: PDF binary data
            config: Conversion configuration
                - filename: PDF filename (required)
                - formula_enable: Enable formula recognition (default: True)
                - from_page: Start page (default: 0)
                - to_page: End page (default: 100000)
                - with_images: Include images in markdown output (default: True)
                
        Returns:
            Markdown content (with or without images based on with_images parameter)
        """
        try:
            filename = config.get('filename', 'document.pdf')
            from_page = config.get('from_page', 0)
            to_page = config.get('to_page', 100000)
            layout_recognize = config.get('layout_recognize', 'mineru')
            # with_images = config.get('with_images', True)

            if layout_recognize == 'mineru':
                # Initialize PowerRAG MinerU parser
                parser = MinerUPdfParser(filename=filename)
            
                logger.info(f"Converting PDF to Markdown using MinerU: {filename}")
            elif layout_recognize == 'dots_ocr':
                parser = DotsOcrParser(filename=filename)
                logger.info(f"Converting PDF to Markdown using DotsOCR: {filename})")
            else:
                raise ValueError(f"Unsupported layout recognize: {layout_recognize}")
            # Parse PDF and get markdown content
            result, _ = parser(
                binary=binary,
                from_page=from_page,
                to_page=to_page,
                doc_id=self.doc_id,
                callback=None
            )
            
            if result and len(result) > 0:
                markdown_content = result[0]
                logger.info(f"Successfully converted {filename} to Markdown ({len(markdown_content)} chars)")
                return markdown_content
            else:
                raise ValueError("MinerU parser returned empty result")
            
        except Exception as e:
            logger.error(f"Error converting PDF to Markdown: {e}", exc_info=True)
            raise
    
    def _office_to_pdf(self, binary: bytes, config: Dict[str, Any]) -> bytes:
        """
        Convert Office document (Word, Excel, PowerPoint) to PDF using Gotenberg
        
        Args:
            binary: Office document binary data
            config: Conversion configuration (must include 'filename')
            
        Returns:
            PDF binary data
        """
        filename = config.get('filename', 'document.docx')
        
        try:
            url = f"{self.gotenberg_url}/forms/libreoffice/convert"
            files = {'files': (filename, io.BytesIO(binary))}
            
            logger.info(f"Converting Office document to PDF via Gotenberg: {filename}")
            response = requests.post(url, files=files, timeout=60)
            
            if response.status_code != 200:
                raise Exception(f"Gotenberg returned status {response.status_code}: {response.text}")
            
            pdf_binary = response.content
            logger.info(f"Successfully converted {filename} to PDF ({len(pdf_binary)} bytes)")
            return pdf_binary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Gotenberg request failed: {e}")
            raise Exception(f"Failed to connect to Gotenberg service at {self.gotenberg_url}: {e}")
        except Exception as e:
            logger.error(f"Office to PDF conversion error: {e}")
            raise
    
    def _html_to_pdf(self, binary: bytes, config: Dict[str, Any]) -> bytes:
        """
        Convert HTML document to PDF using Gotenberg
        
        Args:
            binary: HTML document binary data
            config: Conversion configuration (must include 'filename')
            
        Returns:
            PDF binary data
        """
        filename = config.get('filename', 'document.html')
        
        try:
            url = f"{self.gotenberg_url}/forms/chromium/convert/html"
            files = {'files': (filename, io.BytesIO(binary))}
            
            logger.info(f"Converting HTML document to PDF via Gotenberg: {filename}")
            response = requests.post(url, files=files, timeout=60)
            
            if response.status_code != 200:
                raise Exception(f"Gotenberg returned status {response.status_code}: {response.text}")
            
            pdf_binary = response.content
            logger.info(f"Successfully converted {filename} to PDF ({len(pdf_binary)} bytes)")
            return pdf_binary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Gotenberg request failed: {e}")
            raise Exception(f"Failed to connect to Gotenberg service at {self.gotenberg_url}: {e}")
        except Exception as e:
            logger.error(f"HTML to PDF conversion error: {e}")
            raise
    
    def convert_to_pdf(self, filename: str, binary: bytes, format_type: str) -> bytes:
        """
        Convert Office or HTML document to PDF
        
        This is a convenience method for parse_service to use.
        
        Args:
            filename: Original filename
            binary: Document binary data
            format_type: 'office' or 'html'
            
        Returns:
            PDF binary data
        """
        if format_type not in ['office', 'html']:
            raise ValueError(f"Unsupported format type: {format_type}. Must be 'office' or 'html'")
        
        config = {'filename': filename}
        converter_key = (format_type, "pdf")
        converter_func = self.converter_map.get(converter_key)
        
        if not converter_func:
            raise ValueError(f"Conversion from {format_type} to PDF not supported")
        
        return converter_func(binary, config)




