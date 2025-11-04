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
import logging

from powerrag.app.pdf_parser_factory import create_pdf_parser
from rag.nlp import rag_tokenizer
from api.db.services.llm_service import LLMBundle
from api.db import LLMType
import requests
from PIL import Image
import io
from rag.nlp import find_codec
from api.utils.configs import get_base_config

# 引入 server/services/split_service.py 中的标题切片方法
from powerrag.server.services.split_service import title_based_chunking

logger = logging.getLogger(__name__)


def chunk(filename=None, binary=None, from_page=0, to_page=100000, lang="Chinese", callback=None, doc_id=None, kb_id=None, **kwargs):
    """
    Supported file formats are pdf, doc, docx, markdown, or plain text.
    This method apply the title ways to chunk files or text.
    Successive text will be sliced into pieces using 'title'.
    
    Args:
        filename: Optional filename (can be None for text-only chunking)
        binary: Binary content or text content (str or bytes)
        ...
    """
    parser_config = kwargs.get("parser_config", {"title_level": 3, "layout_recognize": "mineru", "chunk_token_num": 256, "delimiter": "\n!?。；！？", 
     "enable_ocr": False, "enable_image_understanding": False, "enable_table": True, "enable_formula": False})
    
    # Handle filename - use default if not provided
    if filename is None:
        filename = "text_input.md"
    
    doc = {"docnm_kwd": filename, "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))}
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])
    is_english = lang.lower() == "english"  # is_english(cks)
    tenant_id = kwargs.get("tenant_id", "default")

    # 获取解析相关配置，用于决定是否启用图片理解、公式识别、OCR等功能
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
        if callback:
            callback(0.15, "Converting Office document to PDF...")
        try:
            # Get Gotenberg service URL from config
            gotenberg_config = get_base_config("gotenberg", {}) or {}
            gotenberg_url = gotenberg_config.get("url", "http://localhost:3000")
            
            # Convert Office document to PDF using Gotenberg
            url = f"{gotenberg_url}/forms/libreoffice/convert"
            files = {'files': (filename, io.BytesIO(binary) if binary else open(filename, 'rb'))}
            
            logging.info(f"Converting Office document to PDF via Gotenberg: {filename}")
            response = requests.post(url, files=files, timeout=120)
            
            if response.status_code != 200:
                raise Exception(f"Gotenberg conversion failed with status {response.status_code}: {response.text}")
            
            pdf_binary = response.content
            logging.info(f"Successfully converted {filename} to PDF ({len(pdf_binary)} bytes)")
            
            # Parse the converted PDF
            pdf_filename = os.path.splitext(filename)[0] + ".pdf"
            pdf_parser = create_pdf_parser(pdf_filename, parser_config, tenant_id=tenant_id, lang=lang)
            binary = pdf_binary  # Use converted PDF binary for parsing
            
            if callback:
                callback(0.2, "Office document converted to PDF successfully")
        except Exception as e:
            error_msg = f"Failed to convert Office document to PDF: {str(e)}"
            logging.error(error_msg)
            if callback:
                callback(-1, error_msg)
            raise Exception(error_msg)
    
    # Handle HTML files - convert to PDF first
    elif re.search(r"\.(html?|htm)$", filename, re.IGNORECASE):
        if callback:
            callback(0.15, "Converting HTML document to PDF...")
        try:
            # Get Gotenberg service URL from config
            gotenberg_config = get_base_config("gotenberg", {}) or {}
            gotenberg_url = gotenberg_config.get("url", "http://localhost:3000")
            
            # Convert HTML document to PDF using Gotenberg
            url = f"{gotenberg_url}/forms/chromium/convert/html"
            files = {'files': (filename, io.BytesIO(binary) if binary else open(filename, 'rb'))}
            
            logging.info(f"Converting HTML document to PDF via Gotenberg: {filename}")
            response = requests.post(url, files=files, timeout=120)
            
            if response.status_code != 200:
                raise Exception(f"Gotenberg conversion failed with status {response.status_code}: {response.text}")
            
            pdf_binary = response.content
            logging.info(f"Successfully converted {filename} to PDF ({len(pdf_binary)} bytes)")
            
            # Parse the converted PDF
            pdf_filename = os.path.splitext(filename)[0] + ".pdf"
            pdf_parser = create_pdf_parser(pdf_filename, parser_config, tenant_id=tenant_id, lang=lang)
            binary = pdf_binary  # Use converted PDF binary for parsing
            
            if callback:
                callback(0.2, "HTML document converted to PDF successfully")
        except Exception as e:
            error_msg = f"Failed to convert HTML document to PDF: {str(e)}"
            logging.error(error_msg)
            if callback:
                callback(-1, error_msg)
            raise Exception(error_msg)
    
    # Handle Markdown files directly
    elif re.search(r"\.(md|markdown)$", filename, re.IGNORECASE):
        if binary:
            encoding = find_codec(binary)
            txt = binary.decode(encoding, errors="ignore")
        else:
            with open(filename, "r") as f:
                txt = f.read()
        chunks, _ = title_based_chunking(md_content=txt, parser_config=parser_config)
    
    else:
        raise NotImplementedError(f"File type not supported yet: {filename}. Supported types: PDF, Office (docx, pptx), HTML, Markdown")

    if pdf_parser:
        res, _ = pdf_parser(binary, from_page, to_page, callback=callback, parser_config=parser_config, doc_id=doc_id, kb_id=kb_id)
        # 检查res是否为空
        if not res:
            return []
        # Use the order-guaranteed chunking method to ensure consistency with original document
        chunks, _ = title_based_chunking(md_content=res, parser_config=parser_config)

    # Ensure all chunks are strings (handle case where chunks might be tuples)
    processed_chunks = []
    for chunk in chunks:
        if isinstance(chunk, tuple):
            # chunk is (content, title) tuple
            processed_chunks.append(chunk[0])  # Extract content string

    if callback:
        callback(msg=f"Created {len(processed_chunks)} chunks with order guarantee")

    # Import here to avoid circular import
    from powerrag.app import tokenize_chunks
    res = tokenize_chunks(processed_chunks, doc, is_english, pdf_parser)
    return res


def vision_ocr_images(img_data, vision_model=None, prompt=None) -> str:
    """
    OCR images from MinerU response to text

    Args:
        img_data: 图片的二进制数据
        vision_model: 视觉模型实例
        prompt: 自定义提示词，如果为None则使用默认提示词

    Returns:
        str: 图片描述文本
    """
    if img_data is None:
        return ""

    if not vision_model:
        logging.warning("Vision model not provided, falling back to OCR.\n")
        return ""

    # 自定义提示词
    default_prompt = """请描述这张图片的主要内容和关键信息，请用清晰、结构化的方式描述。"""

    try:
        # 保存图片到二进制缓冲区
        with io.BytesIO() as temp_buffer:
            try:
                with Image.open(io.BytesIO(img_data)) as img:
                    # 将图片转换为 RGB 颜色空间
                    img = img.convert("RGB")
                    # 将图片保存到二进制缓冲区，采用JPEG格式进行适当压缩
                    img.save(temp_buffer, format="JPEG")
                    temp_buffer.seek(0)
                    image_data = temp_buffer.read()
            except (Image.UnidentifiedImageError, OSError) as img_error:
                logging.error(f"Failed to process image data: {str(img_error)}")
                return ""

            try:
                ans = vision_model.describe_with_prompt(image_data, prompt or default_prompt)
                if isinstance(ans, tuple):
                    return ans[0]  # 如果返回(文本, token数)的元组，只取文本
                return ans
            except Exception as cv_error:
                logging.error(f"CV model processing failed: {str(cv_error)}")
                return ""  # 视觉模型失败时返回空字符串

    except Exception as e:
        logging.error(f"Unexpected error in vision_ocr_images: {str(e)}")
        return ""
