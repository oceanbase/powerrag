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

"""PowerRAG Document Parsing Service

PowerRAG only supports: PDF, Office (Word/Excel/PPT), HTML, Markdown
- Office and HTML documents are first converted to PDF via Gotenberg
- PDF and Markdown are parsed directly using MinerU parser
"""

import io
import re
import logging
import tempfile
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Import RAGFlow services and models
from api.db.services.document_service import DocumentService
from api.db.services.file2document_service import File2DocumentService
from api.db import ParserType, FileType
from api.utils.file_utils import filename_type
from rag.utils.storage_factory import STORAGE_IMPL

# Import split service for text chunking
from powerrag.server.services.split_service import PowerRAGSplitService
# Import convert service for document conversion
from powerrag.server.services.convert_service import PowerRAGConvertService

logger = logging.getLogger(__name__)


class PowerRAGParseService:
    """
    PowerRAG Document Parsing Service
    
    Supported formats:
    - PDF: Direct parsing with MinerU
    - Office (DOCX, XLSX, PPTX): Convert to PDF via Gotenberg, then parse
    - HTML: Convert to PDF via Gotenberg, then parse
    - Markdown: Direct parsing with MinerU
    """
    
    # Supported file extensions
    SUPPORTED_FORMATS = {
        'pdf': 'pdf',
        'docx': 'office',
        'doc': 'office',
        'xlsx': 'office',
        'xls': 'office',
        'pptx': 'office',
        'ppt': 'office',
        'html': 'html',
        'htm': 'html',
        'jpeg': 'image',
        'jpg': 'image',
        'png': 'image'
    }
    
    def __init__(self, gotenberg_url: str = "http://localhost:3000"):
        """
        Initialize PowerRAG Parse Service
        
        Args:
            gotenberg_url: Gotenberg service URL for document conversion
        """
        self.gotenberg_url = gotenberg_url
        self.split_service = PowerRAGSplitService()  # Text splitting service
        self.convert_service = PowerRAGConvertService(gotenberg_url)  # Document conversion service
    
    def split_text(self, text: str, parser_id: str = "title", config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Split text into chunks using split_service
        
        This is a convenience method that delegates to PowerRAGSplitService.
        
        Args:
            text: Plain text string to split
            parser_id: Parser/chunker ID
            config: Chunking configuration
            
        Returns:
            Dict containing chunks and metadata
        """
        return self.split_service.split_text(text, parser_id, config)
    
    def parse_document(self, doc_id: str) -> Dict[str, Any]:
        """
        Parse document from RAGFlow database
        
        PowerRAG only supports: PDF, Office, HTML
        - Office/HTML are converted to PDF via Gotenberg first
        - PDF and Markdown are parsed directly with MinerU
        
        Args:
            doc_id: Document ID in RAGFlow database
            parser_type: Optional parser type override (if None, auto-detect from doc)
            config: Parser configuration
            
        Returns:

        """
        try:
            # Get document from database
            exist, doc = DocumentService.get_by_id(doc_id)
            if not exist:
                raise ValueError(f"Document {doc_id} not found in database")

            parser_config = doc.get["parser_config"]
            # Get document binary data from storage
            bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
            binary = STORAGE_IMPL.get(bucket, name)
            
            if not binary:
                raise ValueError(f"Document binary data not found for {doc_id}")
            file_ext = Path(doc.name).suffix.lstrip('.').lower()
            format_type = self.SUPPORTED_FORMATS[file_ext]
            result = self._parse_to_markdown(doc.name, binary, format_type, parser_config)

            
            return {
                "doc_id": doc_id,
                "doc_name": doc.name,
                "md_content": result[0],
                "images": result[1]
            }
            
        except Exception as e:
            logger.error(f"Error parsing document {doc_id}: {e}", exc_info=True)
            raise
    
    def parse_file_binary(self, binary: bytes, filename: str,
                         config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Parse file binary directly (without doc_id) and return markdown + images
        
        PowerRAG only supports: PDF, Office, HTML, Markdown
        - Office/HTML are converted to PDF via Gotenberg first
        - PDF and Markdown are parsed directly with MinerU
        
        Args:
            binary: File binary data
            filename: Original filename (used to detect format)
            parser_id: Parser ID (e.g., "title", "naive", "paper")
            config: Parser configuration
            
        Returns:
            Dict containing markdown content and images
            {
                "filename": "...",
                "markdown": "...",
                "images": {"image1.png": "base64_data", ...},
                "total_images": 5
            }
        """
        try:
            # Check if format is supported
            file_ext = Path(filename).suffix.lstrip('.').lower()
            if file_ext not in self.SUPPORTED_FORMATS:
                raise ValueError(
                    f"Unsupported format: .{file_ext}. "
                    f"PowerRAG only supports: {', '.join(sorted(set(self.SUPPORTED_FORMATS.values())))}"
                )
            
            format_type = self.SUPPORTED_FORMATS[file_ext]
            
            # Parse document to get markdown and images
            md_content, images = self._parse_to_markdown(filename, binary, format_type, config)
            
            return {
                "filename": filename,
                "file_format": file_ext,
                "format_type": format_type,
                "markdown": md_content,
                "images": images,
                "total_images": len(images),
                "markdown_length": len(md_content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing file binary: {e}", exc_info=True)
            raise
    
    def _parse_to_markdown(self, filename: str, binary: bytes, format_type: str,
                          config: Dict[str, Any] = None) -> tuple:
        """
        Parse document to markdown with images
        
        Args:
            filename: Document filename
            binary: Document binary data
            format_type: Format type (pdf, office, html, markdown)
            config: Parser configuration
            
        Returns:
            Tuple of (markdown_content, images_dict)
        """
        if config is None:
            config = {}
        
        # For markdown files, return as-is
        if format_type == 'markdown':
            logger.info(f"Reading markdown file: {filename}")
            try:
                md_content = binary.decode('utf-8')
                return md_content, {}
            except Exception as e:
                logger.error(f"Error decoding markdown: {e}")
                raise ValueError(f"Failed to decode markdown file: {e}")
        
        # For Office/HTML, convert to PDF first
        needs_conversion = format_type in ['office', 'html']
        if needs_conversion:
            logger.info(f"Converting {format_type} document to PDF: {filename}")
            try:
                pdf_binary = self.convert_service.convert_to_pdf(filename, binary, format_type)
                filename = Path(filename).stem + '.pdf'
                binary = pdf_binary
                logger.info(f"Conversion successful, now parsing PDF")
            except Exception as e:
                logger.error(f"Failed to convert {filename} to PDF: {e}")
                raise ValueError(f"Document conversion failed: {e}")
        
        # Check layout_recognize parameter to select parser
        layout_recognize = config.get('layout_recognize', 'mineru')
        
        # Parse PDF with selected parser to get markdown and images
        logger.info(f"Parsing PDF to markdown with images using {layout_recognize}: {filename}")
        try:
            if layout_recognize == 'dots_ocr':
                # Use dots_ocr parser
                from powerrag.parser.dots_ocr_parser import DotsOcrParser
                
                # Create parser with config
                formula_enable = config.get('formula_enable', True)
                enable_ocr = config.get('enable_ocr', True)
                from_page = config.get('from_page', 0)
                to_page = config.get('to_page', 100000)
                
                parser = DotsOcrParser(
                    filename=filename,
                    enable_ocr=enable_ocr
                )
                
                # Parse PDF - DotsOcrParser returns (sections, images_dict)
                result, images_dict = parser(
                    binary=binary,
                    from_page=from_page,
                    to_page=to_page,
                    callback=None
                )
                
                # Extract markdown content
                if result and len(result) > 0:
                    md_content = result[0]
                else:
                    md_content = ""
                
                # Extract images (images_dict should be in format returned by parser)
                images = {}
                if images_dict and isinstance(images_dict, dict):
                    # Check if it's the nested result structure
                    if 'results' in images_dict:
                        for doc_key, doc_data in images_dict['results'].items():
                            if 'images' in doc_data:
                                images = doc_data['images']
                                if 'md_content' in doc_data:
                                    # Use md_content from result if available
                                    md_content = doc_data['md_content']
                                break
                    else:
                        # Direct images dict
                        images = images_dict
            elif layout_recognize == 'mineru':
                # Default to mineru parser
                from powerrag.parser.mineru_parser import MinerUPdfParser
                
                # Create parser with config
                formula_enable = config.get('formula_enable', True)
                table_enable = config.get('table_enable', True)
                enable_ocr = config.get('enable_table', False)
                from_page = config.get('from_page', 0)
                to_page = config.get('to_page', 100000)
                
                parser = MinerUPdfParser(
                    filename=filename,
                    formula_enable=formula_enable,
                    table_enable=table_enable,
                    enable_ocr=enable_ocr
                )
                
                # Parse PDF - MinerU returns (sections, images_dict)
                # sections[0] contains markdown content
                # images_dict contains {filename: base64_string}
                result, images_dict = parser(
                    binary=binary,
                    from_page=from_page,
                    to_page=to_page,
                    callback=None
                )
                
                # Extract markdown content
                if result and len(result) > 0:
                    md_content = result[0]
                else:
                    md_content = ""
                
                # Extract images (images_dict should be in format returned by parser)
                images = {}
                if images_dict and isinstance(images_dict, dict):
                    # Check if it's the nested result structure from CLI parsing
                    if 'results' in images_dict:
                        for doc_key, doc_data in images_dict['results'].items():
                            if 'images' in doc_data:
                                images = doc_data['images']
                                if 'md_content' in doc_data:
                                    # Use md_content from result if available
                                    md_content = doc_data['md_content']
                                break
                    else:
                        # Direct images dict
                        images = images_dict
            else:
                raise ValueError(f"Unsupported layout_recognize parser: {layout_recognize}")
            logger.info(f"Successfully parsed {filename}: {len(md_content)} chars markdown, {len(images)} images")
            return md_content, images
            
        except Exception as e:
            logger.error(f"Error parsing PDF to markdown: {e}", exc_info=True)
            raise
    
    def _parse_powerrag(self, filename: str, binary: bytes, 
                         config: Dict[str, Any] = None, doc: Any = None) -> List[Dict[str, Any]]:
        """
        Parse document using PowerRAG approach:
        1. Get parser based on parser_id
        2. For Office/HTML: Convert to PDF via Gotenberg first
        3. For PDF/Markdown: Parse directly with selected parser
        
        All formats are parsed into chunks according to parser_id configuration.
        
        Args:
            filename: Document filename
            binary: Document binary data
            config: Parser configuration
            doc: Document object
        
        Returns:
            List of parsed chunks
        """
        if config is None:
            config = {}
        
        file_ext = Path(filename).suffix.lstrip('.').lower()
        format_type = self.SUPPORTED_FORMATS.get(file_ext)
        
        # For markdown files, use split_service directly with text
        if format_type == 'markdown':
            logger.info(f"Using split_service for markdown file: {filename}")
            try:
                # Decode markdown binary to text
                text = binary.decode('utf-8')
                # Use split_service to chunk the text
                result = self.split_service.split_text(text, config)
                # Return chunks in expected format
                return result['chunks']
            except Exception as e:
                logger.error(f"Error using split_service for markdown: {e}")
                # Fallback to traditional parsing if split_service fails
                logger.info("Falling back to traditional parsing method")
        
        # Determine if conversion to PDF is needed
        needs_conversion = format_type in ['office', 'html']
        
        if needs_conversion:
            logger.info(f"Converting {format_type} document to PDF: {filename}")
            try:
                # Use convert_service for Office/HTML → PDF conversion
                pdf_binary = self.convert_service.convert_to_pdf(filename, binary, format_type)
                filename = Path(filename).stem + '.pdf'  # Change filename to PDF
                binary = pdf_binary
                logger.info(f"Conversion successful, now parsing PDF")
            except Exception as e:
                logger.error(f"Failed to convert {filename} to PDF: {e}")
                raise ValueError(f"Document conversion failed: {e}")
        
        # Parse document with selected parser (for PDF and other binary formats)
        return self._parse_with_parser(filename, binary, config, doc)
    
    
    def _parse_with_parser(self, parser_id: str, filename: str, binary: bytes,
                           config: Dict[str, Any] = None, doc: Any = None) -> List[Dict[str, Any]]:
        """
        Parse document with specified parser
        
        This method directly uses split_service's chunking logic for consistency.
        
        Args:
            parser_id: Parser ID (e.g., "title", "naive", "paper")
            filename: Document filename
            binary: Document binary data
            config: Parser configuration
            doc: Document object
        
        Returns:
            List of parsed chunks
        """
        if config is None:
            config = {}
        
        # Check layout_recognize parameter to select parser for PDF files
        layout_recognize = config.get('layout_recognize', 'mineru')
        
        # For PDF and other binary formats, use split_service's chunker or direct parsing
        try:
            # If layout_recognize is specified and not 'mineru', use direct parsing with selected parser
            if layout_recognize != 'mineru' and layout_recognize in ['dots_ocr']:
                # Use direct parsing with selected parser
                logger.info(f"Using direct parsing with {layout_recognize} parser for {filename}")
                
                if layout_recognize == 'dots_ocr':
                    # Use dots_ocr parser
                    from powerrag.parser.dots_ocr_parser import DotsOcrParser
                    
                    # Create parser with config
                    formula_enable = config.get('formula_enable', True)
                    enable_ocr = config.get('enable_ocr', True)
                    from_page = config.get('from_page', 0)
                    to_page = config.get('to_page', 100000)
                    
                    parser = DotsOcrParser(
                        filename=filename,
                        formula_enable=formula_enable,
                        enable_ocr=enable_ocr
                    )
                    
                    # Parse PDF - DotsOcrParser returns (sections, images_dict)
                    result, images_dict = parser(
                        binary=binary,
                        from_page=from_page,
                        to_page=to_page,
                        callback=None
                    )
                    
                    # Extract markdown content
                    if result and len(result) > 0:
                        md_content = result[0]
                    else:
                        md_content = ""
                    
                    # Use split_service to chunk the text
                    chunk_result = self.split_service.split_text(md_content, parser_id, config)
                    return chunk_result['chunks']
                else:
                    # Default to mineru parser (fallback)
                    from powerrag.parser.mineru_parser import MinerUPdfParser
                    
                    # Create parser with config
                    formula_enable = config.get('formula_enable', True)
                    enable_ocr = config.get('enable_ocr', False)
                    from_page = config.get('from_page', 0)
                    to_page = config.get('to_page', 100000)
                    
                    parser = MinerUPdfParser(
                        filename=filename,
                        formula_enable=formula_enable,
                        enable_ocr=enable_ocr
                    )
                    
                    # Parse PDF - MinerU returns (sections, images_dict)
                    # sections[0] contains markdown content
                    # images_dict contains {filename: base64_string}
                    result, images_dict = parser(
                        binary=binary,
                        from_page=from_page,
                        to_page=to_page,
                        callback=None
                    )
                    
                    # Extract markdown content
                    if result and len(result) > 0:
                        md_content = result[0]
                    else:
                        md_content = ""
                    
                    # Use split_service to chunk the text
                    chunk_result = self.split_service.split_text(md_content, parser_id, config)
                    return chunk_result['chunks']
            else:
                # Default behavior: use split_service's chunker directly
                logger.info(f"Using split_service's chunker directly for {filename}")
                
                from powerrag.app import title as powerrag_title
                
                def dummy(prog=None, msg=""):
                    """Dummy callback for progress"""
                    pass
                
                # Build parser_config
                if parser_id == ParserType.TITLE.value:
                    parser_config = {
                        "title_level": config.get("title_level", 3),
                        "chunk_token_num": config.get("chunk_token_num", 256),
                        "delimiter": config.get("delimiter", "\n!?;。；！？"),
                        "layout_recognize": config.get("layout_recognize", "mineru")
                    }
                else:
                    parser_config = config.copy() if config else {}
                    parser_config.setdefault("chunk_token_num", 256)
                    parser_config.setdefault("delimiter", "\n!?;。；！？")
                
                # Build kwargs
                kwargs = {
                    "lang": config.get("lang", "Chinese"),
                    "callback": dummy,
                    "parser_config": parser_config,
                    "from_page": config.get("from_page", 0),
                    "to_page": config.get("to_page", 100000),
                }
                
                # Add optional fields if doc is provided
                if doc:
                    if hasattr(doc, 'tenant_id'):
                        kwargs["tenant_id"] = doc.tenant_id
                    if hasattr(doc, 'kb_id'):
                        kwargs["kb_id"] = doc.kb_id
                    if hasattr(doc, 'id'):
                        kwargs["doc_id"] = doc.id
                
                # Get chunker from split_service
                chunker = self.split_service._get_chunker(parser_id)
                
                # Call chunker's chunk method
                chunks = chunker.chunk(filename, binary, **kwargs)
                
                logger.info(f"Parsed {filename} with parser '{parser_id}': {len(chunks)} chunks")
                return chunks
            
        except Exception as e:
            logger.error(f"Error parsing {filename} with parser '{parser_id}': {e}", exc_info=True)
            raise
    
    def parse_docs_batch(self, doc_ids: List[str], parser_type: str = None, 
                        config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Batch parse multiple documents using ThreadPoolExecutor
        (same approach as FileService.parse_docs)
        """
        exe = ThreadPoolExecutor(max_workers=12)
        threads = []
        
        for doc_id in doc_ids:
            threads.append(exe.submit(self.parse_document, doc_id, parser_type, config))
        
        results = []
        for doc_id, th in zip(doc_ids, threads):
            try:
                result = th.result()
                results.append({
                    "doc_id": doc_id,
                    "success": True,
                    "data": result
                })
            except Exception as e:
                results.append({
                    "doc_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        return results

