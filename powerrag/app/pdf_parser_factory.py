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
PDF Parser Factory for PowerRAG

This module provides a factory function to create PDF parsers based on configuration.
Supports multiple PDF parsing backends: MinerU, DotsOcr, DeepDOC, PlainParser, etc.
"""

import logging
from typing import Optional
from powerrag.parser.mineru_parser import MinerUPdfParser
from powerrag.parser.dots_ocr_parser import DotsOcrParser

logger = logging.getLogger(__name__)


def create_pdf_parser(
    filename: str,
    parser_config: dict,
    tenant_id: str = "default",
    lang: str = "Chinese"
) -> Optional[object]:
    """
    Create a PDF parser instance based on configuration.
    
    Args:
        filename: PDF filename
        parser_config: Parser configuration dictionary containing:
            - pdf_parser: Parser type ("mineru", "dots_ocr")
            - layout_recognize: Legacy parameter, used as fallback if pdf_parser not specified
            - enable_ocr: Whether to enable OCR
            - enable_formula: Whether to enable formula recognition (for MinerU)
            - enable_table: Whether to enable table recognition (for MinerU)
        tenant_id: Tenant ID (reserved for future use)
        lang: Language setting (reserved for future use)
        
    Returns:
        PDF parser instance or None
        
    Supported parsers:
        - "mineru" or "mineru_parser": MinerUPdfParser (PowerRAG custom)
        - "dots_ocr" or "dots_ocr_parser": DotsOcrParser (vLLM-based)
    """
    
    # Fallback to layout_recognize for backward compatibility
    # layout_recognize can be: "mineru" or "dots_ocr"
    layout_recognize = parser_config.get("layout_recognize", "mineru")
    if layout_recognize == "dots_ocr":
        pdf_parser_type = "dots_ocr"
    else:
        # Default to mineru for any other value
        pdf_parser_type = "mineru"
    
    # Normalize parser type (case-insensitive)
    pdf_parser_type = pdf_parser_type.lower().strip()
    
    # Get parser options
    enable_ocr = parser_config.get("enable_ocr", False)
    formula_enable = parser_config.get("enable_formula", False)
    enable_table = parser_config.get("enable_table", True)
    
    try:
        if pdf_parser_type == "mineru":
            logger.info(f"Creating MinerUPdfParser for {filename}")
            return MinerUPdfParser(
                filename=filename,
                formula_enable=formula_enable,
                table_enable=enable_table,
                enable_ocr=enable_ocr
            )
        
        elif pdf_parser_type == "dots_ocr":
            logger.info(f"Creating DotsOcrParser for {filename}")
            return DotsOcrParser(
                filename=filename,
                enable_ocr=enable_ocr
            )
        
        else:
            logger.warning(f"Unknown PDF parser type: {pdf_parser_type}, falling back to MinerUPdfParser")
            return MinerUPdfParser(
                filename=filename,
                formula_enable=formula_enable,
                table_enable=enable_table,
                enable_ocr=enable_ocr
            )
    
    except Exception as e:
        logger.error(f"Failed to create PDF parser {pdf_parser_type}: {e}", exc_info=True)
        # Fallback to MinerUPdfParser on error
        try:
            logger.info(f"Falling back to MinerUPdfParser")
            return MinerUPdfParser(
                filename=filename,
                formula_enable=formula_enable,
                table_enable=enable_table,
                enable_ocr=enable_ocr
            )
        except Exception as fallback_error:
            logger.error(f"Failed to create fallback parser: {fallback_error}", exc_info=True)
            return None

