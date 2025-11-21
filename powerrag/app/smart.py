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

import os
import re
import copy
import logging

from powerrag.app.pdf_parser_factory import create_pdf_parser
from powerrag.app.gotenberg_converter import convert_office_to_pdf, convert_html_to_pdf
from rag.nlp import rag_tokenizer
import io
from rag.nlp import find_codec

# 引入 server/services/split_service.py 中的智能切片方法
from powerrag.server.services.split_service import smart_based_chunking

logger = logging.getLogger(__name__)


def chunk(filename=None, binary=None, from_page=0, to_page=100000, lang="Chinese", callback=None, kb_id=None, **kwargs):
    """
    Supported file formats are pdf, doc, docx, markdown, or plain text.
    This method apply the smart ways to chunk files or text.
    Successive text will be sliced into pieces using 'smart'.
    
    Args:
        filename: Optional filename (can be None for text-only chunking)
        binary: Binary content or text content (str or bytes)
        ...
    """

    parser_config = kwargs.get("parser_config", 
    {"chunk_token_num": 256, "min_chunk_tokens":64,
    "enable_ocr": False, "enable_image_understanding": False, "enable_table": True, "enable_formula": False, "layout_recognize": "mineru"})

    # Handle filename - use default if not provided
    doc = {"docnm_kwd": filename, "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))}
    chunk_token_num = parser_config.get("chunk_token_num", 256)
    is_english = lang.lower() == "english"  # is_english(cks)
    tenant_id = kwargs.get("tenant_id", "default")
    formula_enable = parser_config.get("enable_formula", False)
    enable_table = parser_config.get("enable_table", True)
    enable_ocr = parser_config.get("enable_ocr", False)
    enable_image_understanding = parser_config.get("enable_image_understanding", False)
    pdf_parser = None
    res = []
    if callback:
        callback(0.1, "Start to parse.")
    
    # Handle PDF files directly
    if re.search(r"\.pdf$", filename, re.IGNORECASE):
        pdf_parser = create_pdf_parser(filename, parser_config, tenant_id=tenant_id, lang=lang)
    
    # Handle Office files (Word, Excel, PowerPoint) - convert to PDF first
    elif re.search(r"\.(docx?|doc?|pptx?|ppt?)$", filename, re.IGNORECASE):
        trace_id = kwargs.get('trace_id')
        pdf_binary, pdf_filename = convert_office_to_pdf(
            filename, binary=binary, callback=callback, trace_id=trace_id
        )
        # Parse the converted PDF
        pdf_parser = create_pdf_parser(pdf_filename, parser_config, tenant_id=tenant_id, lang=lang)
        binary = pdf_binary  # Use converted PDF binary for parsing
    
    # Handle HTML files - convert to PDF first
    elif re.search(r"\.(html?|htm)$", filename, re.IGNORECASE):
        trace_id = kwargs.get('trace_id')
        pdf_binary, pdf_filename = convert_html_to_pdf(
            filename, binary=binary, callback=callback, trace_id=trace_id
        )
        # Parse the converted PDF
        pdf_parser = create_pdf_parser(pdf_filename, parser_config, tenant_id=tenant_id, lang=lang)
        binary = pdf_binary  # Use converted PDF binary for parsing
    
    # Handle Markdown files directly
    elif re.search(r"\.(md|markdown|html?|htm|txt|csv)$", filename, re.IGNORECASE):
        if binary:
            encoding = find_codec(binary)
            txt = binary.decode(encoding, errors="ignore")
        else:
            with open(filename, "r") as f:
                txt = f.read()
        
        # Use the smart-based chunking method from split_service.py
        chunks = smart_based_chunking(txt, parser_config)
        
        # Process the chunks into the expected format
        res = []
        for i, chunk_content in enumerate(chunks):
            doc_chunk = copy.deepcopy(doc)
            doc_chunk["content_with_weight"] = chunk_content
            doc_chunk["chunk_id"] = f"{filename}-chunk-{i}"
            
            # Add position information to maintain document order
            # For non-PDF files, use chunk index as position
            from powerrag.app import add_positions
            add_positions(doc_chunk, [[i]*5])
            
            tokenize(doc_chunk, chunk_content, is_english)
            res.append(doc_chunk)
        
        if callback:
            callback(1.0, "Finished chunking.")
        
        return res
    
    else:
        raise NotImplementedError(f"File type not supported yet: {filename}. Supported types: PDF, Office (docx, pptx), HTML, Markdown")

    if pdf_parser:
        md, _ = pdf_parser(binary, from_page, to_page, callback=callback, kb_id=kb_id)
        # 检查md是否为空
        if not md:
            return []
        # pdf_parser returns a list, extract the first element (markdown content)
        md_content = md[0] if isinstance(md, list) else md
        # Use the order-guaranteed chunking method to ensure consistency with original document
        chunks = smart_based_chunking(md_content=md_content, parser_config=parser_config)

    for i, chunk_content in enumerate(chunks):
        doc_chunk = copy.deepcopy(doc)
        doc_chunk["content_with_weight"] = chunk_content
        doc_chunk["chunk_id"] = f"{filename}-chunk-{i}"
        
        # Add position information to maintain document order
        # If pdf_parser is available, try to get actual positions from PDF
        if pdf_parser:
            try:
                # Try to get position from PDF parser
                _, poss = pdf_parser.crop(chunk_content, need_position=True)
                from powerrag.app import add_positions
                add_positions(doc_chunk, poss)
            except (NotImplementedError, AttributeError, Exception):
                # Fallback: use chunk index as position
                from powerrag.app import add_positions
                add_positions(doc_chunk, [[i]*5])
        else:
            # No PDF parser: use chunk index as position
            from powerrag.app import add_positions
            add_positions(doc_chunk, [[i]*5])
        
        tokenize(doc_chunk, chunk_content, is_english)
        res.append(doc_chunk)

    if callback:
        callback(1.0, "Finished chunking.")

    return res

def tokenize(doc, content, eng):
    """
    Tokenize the content and add to document
    """
    # Implementation based on common pattern in other chunk methods
    doc["content_ltks"] = rag_tokenizer.fine_grained_tokenize(content)
    doc["content_sm_ltks"] = rag_tokenizer.tokenize(content)
    return doc

