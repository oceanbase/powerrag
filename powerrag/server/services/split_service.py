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

"""PowerRAG Text Splitting Service

This service provides text chunking/splitting functionality.
It does NOT handle document parsing - only takes text strings as input.

Uses powerrag/app chunking methods based on parser_id.
"""

import re
import logging
from typing import Dict, Any, List, Tuple
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from numpy.f2py.auxfuncs import throw_error

from api.db import ParserType
from powerrag.utils.nlp_utils import num_tokens_from_string

logger = logging.getLogger(__name__)

# Chunker Factory - mapping parser_id to chunking module
CHUNKER_FACTORY = {}


class PowerRAGSplitService:
    """
    Service for text splitting/chunking

    This service takes text strings and applies powerrag/app chunking methods.
    Input: Plain text (str type), usually in markdown format
    Output: Chunks based on selected parser_id
    """

    def __init__(self):
        # 初始化时动态导入chunker，避免循环导入
        self._init_chunker_factory()

    def _init_chunker_factory(self):
        """动态导入chunker模块，避免循环导入"""
        global CHUNKER_FACTORY
        if not CHUNKER_FACTORY:
            global regex_based_chunking, title_based_chunking, smart_based_chunking
            CHUNKER_FACTORY.update({
                ParserType.TITLE.value: title_based_chunking,  # PowerRAG Title Chunker
                ParserType.REGEX.value: regex_based_chunking,  # PowerRAG regex Chunker
                ParserType.SMART.value: smart_based_chunking,  # PowerRAG smart Chunker
            })
        self.chunker_factory = CHUNKER_FACTORY

    def _get_chunker(self, parser_id: str):
        """
        Get chunker module based on parser_id

        Args:
            parser_id: Parser ID (e.g., "title", "naive", "paper")

        Returns:
            Chunker module from rag.app or powerrag.app
        """
        chunker = self.chunker_factory.get(parser_id.lower())
        if not chunker:
            logger.error(f"Chunker '{parser_id}' not found, using general (naive) chunker")
            raise ValueError(f"Chunker '{parser_id}' not found")
        return chunker

    def split_text(self, text: str, parser_id: str = "title", config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Split text into chunks using powerrag/app chunking methods

        Args:
            text: Plain text string to split (str type), usually in markdown format
            parser_id: Parser/chunker ID (e.g., "title", "naive", "paper")
            config: Chunking configuration (optional)

        Returns:
            Dict containing chunks and metadata

        Example:
            ```python
            service = PowerRAGSplitService()

            # Using title chunker (PowerRAG)
            result = service.split_text(
                text="# Title 1\n\nContent...\n\n## Subtitle\n\nMore content...",
                parser_id="title",
                config={"title_level": 3, "chunk_token_num": 256}
            )
            ```
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be str type, got {type(text)}")

        if not text or not text.strip():
            raise ValueError("text cannot be empty")

        if config is None:
            config = {}

        try:
            # Get chunker based on parser_id
            chunker = self._get_chunker(parser_id)
            logger.info(f"Using chunker: {parser_id} for text splitting")

            # Prepare callback
            def dummy(prog=None, msg=""):
                """Dummy callback for progress"""
                pass

            # Build parser_config based on parser_id
            if parser_id == ParserType.TITLE.value:
                # Title parser specific config
                parser_config = {
                    "title_level": config.get("title_level", 3),
                    "chunk_token_num": config.get("chunk_token_num", 256),
                    "delimiter": config.get("delimiter", "\n。.；;！!？?"),
                }
                chunks, titles = chunker(text, parser_config=parser_config)
                # For title-based chunking, combine chunks with titles
                combined_chunks = []
                for i, chunk in enumerate(chunks):
                    if isinstance(chunk, tuple):
                        # chunk is (content, title)
                        combined_chunks.append(chunk[0])  # chunk with title
                    else:
                        combined_chunks.append(chunk)
                chunks = combined_chunks
            elif parser_id == ParserType.REGEX.value:
                # Pattern parser specific config
                parser_config = {
                    "regex_pattern": config.get("regex_pattern", config.get("pattern", r'[.!?]+\s*')),
                    "chunk_token_num": config.get("chunk_token_num", 512),
                    "min_chunk_tokens": config.get("min_chunk_tokens", 128),
                    "delimiter": config.get("delimiter", "\n。.；;！!？?"),
                }
                chunks = chunker(text, parser_config=parser_config)
            elif parser_id == ParserType.SMART.value:
                # Smart parser specific config
                parser_config = {
                    "chunk_token_num": config.get("chunk_token_num", 256),
                    "min_chunk_tokens": config.get("min_chunk_tokens", 64)
                }

                # Smart chunking returns a list of chunks directly
                chunks = chunker(text, parser_config=parser_config)
            else:
                # Use config as-is for other parsers
                chunks=[]
                throw_error("Chunker not found")

            # Ensure all chunks are strings and handle encoding
            processed_chunks = []
            for chunk in chunks:
                if isinstance(chunk, tuple):
                    # If chunk is a tuple, take the first element
                    chunk_content = chunk[0]
                else:
                    chunk_content = chunk

                # Ensure chunk is a string
                if isinstance(chunk_content, bytes):
                    processed_chunks.append(chunk_content.decode('utf-8'))
                elif isinstance(chunk_content, str):
                    processed_chunks.append(chunk_content)
                else:
                    processed_chunks.append(str(chunk_content))

            logger.info(f"Split text with parser '{parser_id}': {len(processed_chunks)} chunks")

            return {
                "parser_id": parser_id,
                "chunks": processed_chunks,
                "total_chunks": len(processed_chunks),
                "text_length": len(text),
                "metadata": {
                    "chunker": "powerrag",
                    "config": config
                }
            }

        except Exception as e:
            logger.error(f"Error splitting text with parser '{parser_id}': {e}", exc_info=True)
            raise


# ==============================================
# Regex-based chunking
# ==============================================
def regex_based_chunking(
        txt: str,
        parser_config: Dict[str, Any] = None
) -> List[str]:
    """
    使用自定义正则表达式对文本进行严格分块

    Args:
        txt: 要分块的文本
        parser_config: 分块配置参数
            - chunk_token_num: 目标分块大小（tokens）
            - min_chunk_tokens: 最小分块大小（tokens）
            - regex_pattern: 自定义正则表达式，用于初步分割文本单元
            - delimiter: 用于拆分过大切片的分隔符字符串

    Returns:
        分块列表
    """
    if not txt.strip():
        return []

    if parser_config is None:
        parser_config = {}

    chunk_token_num = parser_config.get("chunk_token_num", 256)
    min_chunk_tokens = parser_config.get("min_chunk_tokens", 128)
    regex_pattern = parser_config.get("regex_pattern", r'[.!?]+\s*')
    delimiter = parser_config.get("delimiter", "\n。.；;！!？？")
    
    # 验证参数合理性
    if chunk_token_num <= 0:
        raise ValueError("chunk_token_num 必须为正数")
    if min_chunk_tokens <= 0 or min_chunk_tokens > chunk_token_num:
        raise ValueError("min_chunk_tokens 必须为正数且不大于 chunk_token_num")

    # 使用正则表达式进行初步分割，保留分隔符
    # 注意：正则表达式应设计为捕获有意义的文本单元（如段落、句子等）
    parts = re.split(f'({regex_pattern})', txt)
    # 过滤空字符串并保留有效分割单元
    parts = [part for part in parts if part.strip()]

    if not parts:
        return [txt]

    chunks = []
    current_chunk = []
    current_token_count = 0

    def split_large_chunk_by_delimiter(chunk_text: str) -> List[str]:
        """使用delimiter拆分过大的切片"""
        chunk_tokens = num_tokens_from_string(chunk_text)
        if chunk_tokens <= chunk_token_num:
            return [chunk_text]
        
        # 尝试使用每个delimiter进行拆分
        for delim in delimiter:
            if delim in chunk_text:
                # 找到所有不在保护区域内的分隔符位置
                delimiter_positions = []
                start = 0
                while True:
                    pos = chunk_text.find(delim, start)
                    if pos == -1:
                        break
                    if not is_in_protected_region(chunk_text, pos):
                        delimiter_positions.append(pos)
                    start = pos + 1
                
                if not delimiter_positions:
                    continue
                
                # 按分隔符位置拆分
                result = []
                current_sub_chunk = ""
                last_pos = 0
                
                for pos in delimiter_positions:
                    segment = chunk_text[last_pos:pos + len(delim)]
                    test_chunk = current_sub_chunk + segment if current_sub_chunk else segment
                    
                    if num_tokens_from_string(test_chunk) <= chunk_token_num:
                        current_sub_chunk = test_chunk
                    else:
                        if current_sub_chunk:
                            result.append(current_sub_chunk)
                        current_sub_chunk = segment
                    last_pos = pos + len(delim)
                
                # 处理剩余文本
                if last_pos < len(chunk_text):
                    remaining = chunk_text[last_pos:]
                    test_chunk = current_sub_chunk + remaining if current_sub_chunk else remaining
                    if num_tokens_from_string(test_chunk) <= chunk_token_num:
                        current_sub_chunk = test_chunk
                    else:
                        if current_sub_chunk:
                            result.append(current_sub_chunk)
                        current_sub_chunk = remaining
                
                if current_sub_chunk:
                    result.append(current_sub_chunk)
                
                # 如果拆分成功，返回结果
                if len(result) > 1:
                    return result
        
        # 如果所有delimiter都无法拆分，返回原文本
        return [chunk_text]

    for part in parts:
        # 计算当前部分的token数量
        part_tokens = num_tokens_from_string(part)

        # 如果当前部分本身超过目标大小，使用delimiter进行拆分
        if part_tokens > chunk_token_num:
            # 先处理当前已累积的内容
            if current_token_count >= min_chunk_tokens:
                chunks.append(''.join(current_chunk))
                current_chunk = []
                current_token_count = 0
            
            # 使用delimiter拆分过大的部分
            split_parts = split_large_chunk_by_delimiter(part)
            chunks.extend(split_parts)
            continue

        # 尝试添加到当前块
        new_token_count = current_token_count + part_tokens

        if new_token_count <= chunk_token_num:
            # 未超过目标大小，直接添加
            current_chunk.append(part)
            current_token_count = new_token_count
        else:
            # 超过目标大小，检查当前块是否满足最小要求
            if current_token_count >= min_chunk_tokens:
                # 满足最小要求，结束当前块
                chunks.append(''.join(current_chunk))
                current_chunk = [part]
                current_token_count = part_tokens
            else:
                # 不满足最小要求，强制合并当前部分
                current_chunk.append(part)
                current_token_count = new_token_count
                
                # 如果合并后仍然过大，尝试使用delimiter拆分
                if current_token_count > chunk_token_num * 1.5:
                    combined_text = ''.join(current_chunk)
                    split_chunks = split_large_chunk_by_delimiter(combined_text)
                    if len(split_chunks) > 1:
                        # 拆分成功，保留第一个作为当前块，其余添加到chunks
                        current_chunk = [split_chunks[0]]
                        current_token_count = num_tokens_from_string(split_chunks[0])
                        chunks.extend(split_chunks[1:])

    # 处理剩余内容
    if current_chunk:
        combined_text = ''.join(current_chunk)
        combined_tokens = num_tokens_from_string(combined_text)
        
        # 如果剩余内容过大，尝试拆分
        if combined_tokens > chunk_token_num * 1.5:
            split_chunks = split_large_chunk_by_delimiter(combined_text)
            if len(split_chunks) > 1:
                chunks.extend(split_chunks)
            else:
                # 拆分失败，确保最后一块满足最小要求
                if combined_tokens < min_chunk_tokens and chunks:
                    chunks[-1] += combined_text
                else:
                    chunks.append(combined_text)
        else:
            # 确保最后一块满足最小要求
            if combined_tokens < min_chunk_tokens and chunks:
                chunks[-1] += combined_text
            else:
                chunks.append(combined_text)

    return chunks


# ==============================================
# Title-based chunking
# ==============================================
def title_based_chunking(md_content: str, parser_config: Dict[str, Any] = None) -> tuple[List[str], List[str]]:
    """
    Advanced chunking method that guarantees order consistency with original document
    Handles edge cases and maintains document structure integrity

    Args:
        md_content: The markdown content to split
        parser_config: Configuration for the parser

    Returns:
        Tuple of (chunks, titles) where:
        - chunks: List of markdown content chunks in strict original document order
        - titles: List of corresponding title contents for each chunk
    """
    if parser_config is None:
        parser_config = {}

    title_level = parser_config.get("title_level", 1)
    chunk_token_num = parser_config.get("chunk_token_num", 256)
    delimiter = parser_config.get("delimiter", "\n。；！？")

    if not md_content or not isinstance(title_level, int) or title_level < 1 or title_level > 4:
        return ([md_content] if md_content else [], [""] if md_content else [])

    # Split content into lines while preserving original structure
    lines = md_content.split("\n")
    chunks = []
    titles = []
    current_chunk_lines = []
    current_title = ""
    chunk_positions = []  # Track position information for debugging

    # Helper function to check if a line is a valid header of specific level
    def is_header_of_level(line: str, level: int) -> tuple[bool, str]:
        stripped_line = line.rstrip()
        # Must start at beginning of line (no whitespace)
        if stripped_line != stripped_line.lstrip():
            return False, ""

        # Must start with exact number of #s followed by space
        if not stripped_line.startswith("#" * level + " "):
            return False, ""

        # Extract title content (remove the # symbols and space)
        title_content = stripped_line[level + 1:].strip()
        return True, title_content

    # Process lines sequentially to maintain strict original order
    for i, line in enumerate(lines):
        # Check if current line is a header of the target level
        is_header, title_content = is_header_of_level(line.rstrip(), title_level)
        if is_header:
            # Save current chunk if it has content
            if current_chunk_lines:
                chunk_content = "\n".join(current_chunk_lines).strip()
                if chunk_content:  # Only add non-empty chunks
                    chunks.append(chunk_content)
                    titles.append(current_title)
                    chunk_positions.append(f"Lines {i - len(current_chunk_lines) + 1}-{i}")
                current_chunk_lines = []

            # Start new chunk with the header and update current title
            current_chunk_lines = [line]
            current_title = title_content
        else:
            # Add line to current chunk
            current_chunk_lines.append(line)

    # Add the final chunk if there's remaining content
    if current_chunk_lines:
        chunk_content = "\n".join(current_chunk_lines).strip()
        if chunk_content:  # Only add non-empty chunks
            chunks.append(chunk_content)
            titles.append(current_title)
            chunk_positions.append(f"Lines {len(lines) - len(current_chunk_lines) + 1}-{len(lines)}")

    # If no chunks were created (no headers found), return entire content as one chunk
    if not chunks:
        content = md_content.strip()
        return ([content] if content else [], [""] if content else [])

    logging.info(f"Created {len(chunks)} chunks from document with {len(lines)} lines")

    return split_with_title_chunks(chunks, chunk_token_num, delimiter, title_level), titles


def split_with_title_chunks(sections, chunk_token_num=512, delimiter="\n。；！？", title_level=3):
    """
    Split large chunks while preserving original titles for sub-chunks.
    Small chunk merging is not implemented yet (todo for future).
    """
    if not sections:
        return []
    if isinstance(sections[0], type("")):
        sections = [(s, "") for s in sections]

    def split_chunk_by_delimiter(text, target_size, original_title):
        """Split a large chunk by delimiters to get chunks close to target_size"""
        if num_tokens_from_string(text) <= target_size:
            return [(text, original_title)]

        # Try to split by each delimiter
        for delim in delimiter:
            if delim in text:
                # Find all delimiter positions that are not in protected regions
                delimiter_positions = []
                start = 0
                while True:
                    pos = text.find(delim, start)
                    if pos == -1:
                        break
                    if not is_in_protected_region(text, pos):
                        delimiter_positions.append(pos)
                    start = pos + 1

                if not delimiter_positions:
                    continue

                # Split text at safe delimiter positions
                result = []
                current_chunk = ""
                last_pos = 0

                for pos in delimiter_positions:
                    # Get the text segment including the delimiter
                    segment = text[last_pos:pos + len(delim)]

                    # When merging chunks, ensure we preserve delimiters between segments
                    if current_chunk:
                        test_chunk = current_chunk + segment
                    else:
                        test_chunk = segment

                    if num_tokens_from_string(test_chunk) <= target_size:
                        current_chunk = test_chunk
                    else:
                        if current_chunk:
                            # 检查分块是否已经包含该标题，如果包含则不重复插入
                            # 保留分隔符，不使用rstrip()
                            chunk_content = current_chunk
                            if original_title and not chunk_content.startswith(original_title):
                                chunk_with_title = f"{original_title}\n{chunk_content}"
                            else:
                                chunk_with_title = chunk_content
                            # Skip standalone title-only chunks
                            if not _is_title_only_chunk(chunk_with_title, original_title):
                                result.append((chunk_with_title, original_title))
                        current_chunk = segment
                    last_pos = pos + len(delim)

                # Handle the remaining text
                if last_pos < len(text):
                    remaining = text[last_pos:]

                    # When merging with remaining text, preserve delimiters
                    if current_chunk:
                        test_chunk = current_chunk + remaining
                    else:
                        test_chunk = remaining

                    if num_tokens_from_string(test_chunk) <= target_size:
                        current_chunk = test_chunk
                    else:
                        if current_chunk:
                            # 保留分隔符，不使用rstrip()
                            chunk_content = current_chunk
                            if original_title and not chunk_content.startswith(original_title):
                                chunk_with_title = f"{original_title}\n{chunk_content}"
                            else:
                                chunk_with_title = chunk_content
                            # Skip standalone title-only chunks
                            if not _is_title_only_chunk(chunk_with_title, original_title):
                                result.append((chunk_with_title, original_title))
                        current_chunk = remaining

                if current_chunk:
                    # 检查最后一个分块是否已经包含该标题，如果包含则不重复插入
                    # 保留分隔符，不使用rstrip()
                    chunk_content = current_chunk
                    if original_title and not chunk_content.startswith(original_title):
                        chunk_with_title = f"{original_title}\n{chunk_content}"
                    else:
                        chunk_with_title = chunk_content
                    # Skip standalone title-only chunks
                    if not _is_title_only_chunk(chunk_with_title, original_title):
                        result.append((chunk_with_title, original_title))

                # If splitting helped, return the result
                if len(result) > 1:
                    filtered_result = [(chunk, title) for chunk, title in result if chunk.strip()]
                    if filtered_result:  # Ensure we don't return empty list
                        return filtered_result

        # If no delimiter splitting worked, return the original text with its title inserted
        return [(text, original_title)]

    # 检查切片是否只有标题
    def _is_title_only_chunk(chunk_text: str, title: str) -> bool:
        """Return True if chunk_text contains only the title (no body)."""
        if not chunk_text:
            return False
        if not title:
            return False
        stripped_chunk = chunk_text.strip()
        stripped_title = title.strip()
        if not stripped_chunk:
            return False
        if stripped_chunk == stripped_title:
            return True
        # If chunk starts with the title, ensure there is non-whitespace content after it
        if stripped_chunk.startswith(stripped_title):
            remainder = stripped_chunk[len(stripped_title):].strip()
            if remainder == "" or remainder == "\n":
                return True
        return False

    def _get_title_level(title_text: str) -> int:
        """Extract the title level from markdown title text.
        Returns the level (1-6) if it's a markdown header, or 999 if no title or not a header.
        """
        if not title_text:
            return 999  # No title
        
        lines = title_text.strip().split('\n')
        if not lines:
            return 999
        
        # Check the first line for markdown header
        first_line = lines[0].strip()
        for level in range(1, 7):
            if first_line.startswith('#' * level + ' '):
                return level
        
        return 999  # Not a markdown header

    # Step 1: Merge small chunks before splitting
    # Merge chunks that are smaller than chunk_token_num / 3
    # Merge condition: current chunk's title level <= previous chunk's title level, or current chunk has no title
    merged_sections = []
    min_chunk_size = chunk_token_num / 3
    
    for section, title in sections:
        section_tokens = num_tokens_from_string(section)
        extracted_title = title if title else extract_title_from_markdown(section, title_level)
        current_title_level = _get_title_level(extracted_title)
        
        # Check if current section is too small and should be merged
        if section_tokens < min_chunk_size and merged_sections:
            # Get previous section info
            prev_section, prev_title = merged_sections[-1]
            prev_extracted_title = prev_title if prev_title else extract_title_from_markdown(prev_section, title_level)
            prev_title_level = _get_title_level(prev_extracted_title)
            
            # Merge condition: current title level <= previous title level, or current has no title (level 999)
            if current_title_level <= prev_title_level or current_title_level == 999:
                # Merge with previous section
                merged_content = prev_section + "\n\n" + section
                # Use the previous title (higher level or existing title)
                merged_title = prev_extracted_title if prev_title_level <= current_title_level else extracted_title
                merged_sections[-1] = (merged_content, merged_title)
                continue
        
        # Don't merge, add as new section
        merged_sections.append((section, extracted_title))

    # Step 2: Split large chunks after merging
    result_chunks = []
    
    for section, title in merged_sections:
        section_tokens = num_tokens_from_string(section)
        
        # Extract title from markdown section if no title provided
        extracted_title = title if title else extract_title_from_markdown(section, title_level)

        # If section is too large, split it and preserve the original title
        if section_tokens > chunk_token_num * 2:
            split_chunks = split_chunk_by_delimiter(section, chunk_token_num, extracted_title)
            result_chunks.extend(split_chunks)
        else:
            # For small chunks, keep them as-is
            result_chunks.append((section, extracted_title))

    return result_chunks


def extract_title_from_markdown(markdown_text, title_level=3):
    """Extract all consecutive title content from markdown text (all headers from the beginning)"""
    if not markdown_text:
        return ""

    lines = markdown_text.strip().split('\n')
    titles = []

    for line in lines:
        stripped_line = line.strip()
        # Check for headers (1-6 levels)
        is_header = False
        for level in range(1, 7):
            if stripped_line.startswith('#' * level + ' '):
                if level == title_level:
                    titles.append(stripped_line)
                    is_header = True
                    break

        # If we encounter a non-header line, stop collecting titles
        if not is_header and stripped_line:
            break

    # Return all collected titles joined with newlines
    return '\n'.join(titles)


def is_in_protected_region(text, position):
    """Check if a position is within a protected region (formulas, HTML tables, etc.)"""
    # Check for LaTeX math formulas
    # Inline math: $...$
    dollar_count = 0
    for i in range(position):
        if text[i] == '$':
            dollar_count += 1
    if dollar_count % 2 == 1:
        return True

    # Display math: $$...$$
    if position >= 1 and text[position - 1:position + 1] == '$$':
        return True
    if position < len(text) - 1 and text[position:position + 2] == '$$':
        return True

    # LaTeX delimiters: \(...\) and \[...\]
    if position >= 1 and text[position - 1:position + 1] in [r'\(', r'\[']:
        return True
    if position < len(text) - 1 and text[position:position + 2] in [r'\)', r'\]']:
        return True

    # Check for HTML tables
    # Find the last unclosed <table> tag before position
    table_start = text.rfind('<table', 0, position)
    if table_start != -1:
        table_end = text.find('</table>', table_start)
        if table_end == -1 or table_end > position:
            return True

    # Check for other HTML block elements that should not be split
    block_tags = ['<div', '<p', '<pre', '<code', '<blockquote']
    for tag in block_tags:
        tag_start = text.rfind(tag, 0, position)
        if tag_start != -1:
            # Find the corresponding closing tag
            tag_name = tag[1:]  # Remove '<'
            closing_tag = f'</{tag_name}>'
            tag_end = text.find(closing_tag, tag_start)
            if tag_end == -1 or tag_end > position:
                return True

    return False


# ==============================================
# Smart-based chunking
# ==============================================
def smart_based_chunking(md_content: str, parser_config: Dict[str, Any] = None) -> List[str]:
    """
    基于 AST 的 Markdown 智能分块主函数

    参数:
        md_content: Markdown 文本内容
        chunk_token_num: 最大分块 token 数
        min_chunk_tokens: 最小分块 token 数

    返回:
        分块后的文本列表
    """

    if md_content is None or not isinstance(md_content, str):
        return []

    if parser_config is None:
        parser_config = {}

    chunk_token_num = parser_config.get("chunk_token_num", 256)
    min_chunk_tokens = parser_config.get("min_chunk_tokens", 128)
    # 验证参数合理性
    if chunk_token_num <= 0:
        raise ValueError("chunk_token_num 必须为正数")
    if min_chunk_tokens <= 0 or min_chunk_tokens > chunk_token_num:
        raise ValueError("min_chunk_tokens 必须为正数且不大于 chunk_token_num")

    chunker = ASTMarkdownChunker()
    chunker.chunk(md_content, chunk_token_num, min_chunk_tokens)
    return chunker.chunks


# ==============================================
# AST-based markdown chunking
# ==============================================
class ASTMarkdownChunker:
    """
    AST-based Markdown Chunker implementing the specified requirements
    """

    def __init__(self):
        self.md_parser = MarkdownIt("commonmark", {"breaks": True, "html": True})
        self.chunks = []

    def chunk(self, text: str, chunk_tokens_number: int = 256, min_tokens_num: int = 64) -> List[str]:
        """
        Chunk markdown text using AST-based approach with specified requirements.

        Args:
            text: Markdown text to chunk
            chunk_tokens_number: Target chunk size in tokens (default: 256)
            min_tokens_num: Minimum chunk size in tokens (default: 64)

        Returns:
            List of chunked text segments
        """
        if not text or not text.strip():
            return []

        # Validate parameters
        if chunk_tokens_number <= 0 or min_tokens_num <= 0 or min_tokens_num > chunk_tokens_number:
            raise ValueError("Invalid chunk size parameters")

        # Parse markdown to AST
        tokens = self.md_parser.parse(text)
        root = SyntaxTreeNode(tokens)

        # Process the document
        self.chunks = []
        self._process_document(root, chunk_tokens_number, min_tokens_num)

        # Post-process chunks
        self._merge_small_chunks(min_tokens_num, chunk_tokens_number)
        
        # Split large chunks that exceed the target size
        self._split_large_chunks(chunk_tokens_number)

        return self.chunks

    def _process_document(self, root_node: SyntaxTreeNode, chunk_tokens_number: int, min_tokens_num: int):
        """
        Process the document root node and generate chunks according to requirements.
        """
        if not hasattr(root_node, 'children') or not root_node.children:
            # Handle simple text without structure
            content = self._render_node(root_node)
            if content.strip():
                self.chunks.append(content.strip())
            return

        # Process each top-level block
        current_chunk_content = ""
        current_title_stack = []  # Stack of (title_text, level)

        for child in root_node.children:
            current_chunk_content, current_title_stack = self._process_node(
                child,
                current_chunk_content,
                current_title_stack,
                chunk_tokens_number,
                min_tokens_num
            )

        # Add remaining content as final chunk
        if current_chunk_content.strip():
            full_content = self._build_chunk_with_titles(current_chunk_content.strip(), current_title_stack)
            if full_content.strip():
                self.chunks.append(full_content)

    def _process_node(self, node: SyntaxTreeNode, current_chunk_content: str,
                      current_title_stack: List[Tuple[str, int]],
                      chunk_tokens_number: int, min_tokens_num: int) -> Tuple[str, List[Tuple[str, int]]]:
        """
        Process a single AST node and return updated chunk content and title stack.
        """
        # Handle heading nodes - they become chunk boundaries
        if node.type == "heading":
            heading_level = len(node.markup) if hasattr(node, 'markup') else 1
            heading_text = self._extract_text_from_node(node)

            # If we have accumulated content, create a chunk with previous titles
            if current_chunk_content.strip():
                full_content = self._build_chunk_with_titles(current_chunk_content.strip(), current_title_stack)
                if full_content.strip():
                    self.chunks.append(full_content)

            # Update title stack - remove titles at same or deeper level, then add current title
            new_title_stack = [(title, level) for title, level in current_title_stack if level < heading_level]
            new_title_stack.append((heading_text, heading_level))

            # Return empty content since headings are boundaries, not content
            return "", new_title_stack

        # Handle container nodes that should not be split
        elif node.type in ["bullet_list", "ordered_list", "table", "fence", "html_block"]:
            node_content = self._render_node(node)
            new_content = current_chunk_content + node_content

            # Check if this container would make the chunk too large
            potential_chunk = self._build_chunk_with_titles(new_content, current_title_stack)
            token_count = num_tokens_from_string(potential_chunk)

            if token_count > chunk_tokens_number * 1.5:  # If significantly larger than target
                # Create chunk with current content first
                if current_chunk_content.strip():
                    full_content = self._build_chunk_with_titles(current_chunk_content.strip(), current_title_stack)
                    if full_content.strip():
                        self.chunks.append(full_content)

                # Create separate chunk for this large container
                container_chunk = self._build_chunk_with_titles(node_content, current_title_stack)
                if container_chunk.strip():
                    self.chunks.append(container_chunk)

                return "", current_title_stack
            else:
                return new_content, current_title_stack

        # Handle paragraph nodes
        elif node.type == "paragraph":
            node_content = self._render_node(node)
            new_content = current_chunk_content + node_content

            # Check chunk size
            potential_chunk = self._build_chunk_with_titles(new_content, current_title_stack)
            token_count = num_tokens_from_string(potential_chunk)

            if token_count > chunk_tokens_number:
                # Create chunk with current content
                if current_chunk_content.strip():
                    full_content = self._build_chunk_with_titles(current_chunk_content.strip(), current_title_stack)
                    if full_content.strip():
                        self.chunks.append(full_content)

                return node_content, current_title_stack
            else:
                return new_content, current_title_stack

        # Handle other block nodes with children
        elif hasattr(node, 'children') and node.children:
            # Process children recursively
            updated_content = current_chunk_content
            updated_title_stack = current_title_stack.copy()

            for child in node.children:
                updated_content, updated_title_stack = self._process_node(
                    child,
                    updated_content,
                    updated_title_stack,
                    chunk_tokens_number,
                    min_tokens_num
                )

            return updated_content, updated_title_stack

        # Handle leaf nodes
        else:
            node_content = self._render_node(node)
            if node_content.strip():
                new_content = current_chunk_content + node_content

                # Check chunk size
                potential_chunk = self._build_chunk_with_titles(new_content, current_title_stack)
                token_count = num_tokens_from_string(potential_chunk)

                if token_count > chunk_tokens_number:
                    # Create chunk with current content
                    if current_chunk_content.strip():
                        full_content = self._build_chunk_with_titles(current_chunk_content.strip(), current_title_stack)
                        if full_content.strip():
                            self.chunks.append(full_content)

                    return node_content, current_title_stack
                else:
                    return new_content, current_title_stack

            return current_chunk_content, current_title_stack

    def _build_chunk_with_titles(self, content: str, title_stack: List[Tuple[str, int]]) -> str:
        """
        Build a chunk with all relevant parent titles.

        Args:
            content: The main content of the chunk
            title_stack: Stack of titles [(title_text, level), ...]

        Returns:
            Formatted chunk with titles and content
        """
        if not content.strip():
            return ""

        # Build title hierarchy - only show the last title (current section)
        if title_stack:
            all_titles = "\n".join([f"{'#' * level} {title}" for title, level in title_stack])
            # Get the last title (current section)
            # for title_text, level in title_stack:
            #     title_line = f"{'#' * level} {title_text}"
            # title_text, level = title_stack[-1]
            # title_line = f"{'#' * level} {title_text}"
            return f"{all_titles}\n\n{content}"
        else:
            return content

    def _extract_text_from_node(self, node: SyntaxTreeNode) -> str:
        """
        Extract plain text content from a node.
        """
        if hasattr(node, 'content') and node.content:
            return node.content.strip()

        text = ""
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                if hasattr(child, 'content') and child.content:
                    text += child.content
                elif hasattr(child, 'children'):
                    text += self._extract_text_from_node(child)

        return text.strip()

    def _render_node(self, node: SyntaxTreeNode) -> str:
        """
        Render a node back to markdown text.
        """
        # Handle nodes with markup
        if hasattr(node, 'markup'):
            # Handle headings - they are handled as boundaries, not content
            if node.type == "heading":
                return ""
            # Handle list items
            elif node.type == "list_item":
                marker = node.markup if node.markup else "-"
                content = "".join([self._render_node(child) for child in node.children]) if hasattr(node,
                                                                                                    'children') and node.children else ""
                return f"{marker} {content}\n"
            # Handle code blocks
            elif node.type == "fence":
                info = f" {node.info}" if hasattr(node, 'info') and node.info else ""
                return f"```{info}\n{node.content}```\n"
            # Handle inline code
            elif node.type == "code_inline":
                return f"`{node.content}`"

        # Handle nodes with children
        if hasattr(node, 'children') and node.children:
            content = "".join([self._render_node(child) for child in node.children])

            # Handle block elements
            if node.type in ["bullet_list", "ordered_list"]:
                return content
            elif node.type == "list_item":
                return content
            elif node.type == "paragraph":
                return content + "\n\n"
            elif node.type == "table":
                # For tables, we need to preserve the original formatting
                # This is a simplified approach - in a real implementation,
                # we might want to reconstruct the table from the AST
                if hasattr(node, 'content') and node.content:
                    return node.content + "\n\n"
                else:
                    return content + "\n\n"

            return content

        # Handle leaf nodes
        if hasattr(node, 'content'):
            if node.type == "text":
                return node.content
            elif node.type == "html_block":
                return node.content
            elif node.type == "html_inline":
                return node.content
            return node.content

        return ""

    def _merge_small_chunks(self, min_tokens_num: int, chunk_tokens_number: int):
        """
        Merge chunks that are smaller than the minimum token requirement.
        """
        if len(self.chunks) <= 1:
            return

        merged_chunks = []
        current_chunk = self.chunks[0]

        for i in range(1, len(self.chunks)):
            next_chunk = self.chunks[i]

            # 计算合并后的token数
            combined_content = current_chunk + '\n' + next_chunk
            combined_tokens = num_tokens_from_string(combined_content)
            next_chunk_tokens = num_tokens_from_string(next_chunk)

            # If the next chunk is too small AND combining is reasonable, merge them
            # Only merge if the combined size is still within reasonable limits
            if (next_chunk_tokens < min_tokens_num and
                    combined_tokens <= chunk_tokens_number * 1.2):  # Reasonable combined size
                # 只有在需要合并时，才去除重复的标题前缀
                combined_content = self._merge_chunks_without_duplicate_prefix(current_chunk, next_chunk)
                current_chunk = combined_content
            else:
                merged_chunks.append(current_chunk)
                current_chunk = next_chunk

        merged_chunks.append(current_chunk)
        self.chunks = merged_chunks

    def _merge_chunks_without_duplicate_prefix(self, current_chunk: str, next_chunk: str) -> str:
        """
        Merge two chunks, removing duplicate title prefix from next_chunk if exists.

        This method finds duplicate title prefixes (lines starting with #) between the end of current_chunk
        and the beginning of next_chunk, then removes the duplicate from next_chunk
        before merging them.
        """
        if not current_chunk:
            return next_chunk
        if not next_chunk:
            return current_chunk

        # 将文本按行分割，便于比较
        current_lines = current_chunk.split('\n')
        next_lines = next_chunk.split('\n')

        # 查找重复的标题前缀行
        # 只考虑以#开头的标题行
        max_prefix_length = 0
        next_start_idx = 0

        # 从前往后检查current_chunk和next_chunk的标题行
        # 目的：找到两个块之间重复的标题前缀
        # 示例：
        # current_chunk包含:   # 一级标题\n## 二级标题\n内容...
        # next_chunk开头:      # 一级标题\## 二级标题\n### 三级标题\n内容...
        # 重复的标题前缀:      ## 一级标题\n## 二级标题
        for i in range(1, min(len(current_lines), len(next_lines)) + 1):
            # 检查current_chunk的前i行是否都是标题行
            current_prefix = current_lines[:i] if i > 0 else []
            # 检查next_chunk的前i行是否都是标题行
            next_prefix = next_lines[:i] if i > 0 else []

            # 验证是否都是标题行（以#开头）
            current_are_titles = all(line.strip().startswith('#') for line in current_prefix if line.strip())
            next_are_titles = all(line.strip().startswith('#') for line in next_prefix if line.strip())

            # 如果都是标题行且内容相同，则认为是重复的标题前缀
            if current_are_titles and next_are_titles and current_prefix == next_prefix and i > max_prefix_length:
                max_prefix_length = i
                next_start_idx = i

        # 如果找到重复标题前缀，去除next_chunk中的重复部分
        if max_prefix_length > 0:
            # 保留current_chunk的全部内容
            result_lines = current_lines
            # 只添加next_chunk中不重复的部分
            result_lines.extend(next_lines[next_start_idx:])
            return '\n'.join(result_lines)
        else:
            # 没有重复标题前缀，直接合并
            return current_chunk + '\n' + next_chunk

    def _split_large_chunks(self, chunk_tokens_number: int):
        """
        Split chunks that are too large into smaller chunks.
        
        Strategy:
        1. First try to split by markdown headings (# ## ### etc.)
        2. If no headings, split by newlines
        3. Ensure each chunk is close to chunk_tokens_number
        
        Args:
            chunk_tokens_number: Target chunk size in tokens
        """
        if not self.chunks:
            return
        
        new_chunks = []
        max_allowed_tokens = chunk_tokens_number * 1.5  # Allow 50% overflow
        
        for chunk in self.chunks:
            chunk_tokens = num_tokens_from_string(chunk)
            
            # If chunk is within acceptable size, keep it
            if chunk_tokens <= max_allowed_tokens:
                new_chunks.append(chunk)
                continue
            
            # Chunk is too large, need to split it
            split_result = self._split_chunk_by_structure(chunk, chunk_tokens_number)
            new_chunks.extend(split_result)
        
        self.chunks = new_chunks

    def _split_chunk_by_structure(self, chunk: str, target_tokens: int) -> List[str]:
        """
        Split a large chunk by its structure (headings or newlines).
        
        Args:
            chunk: The chunk to split
            target_tokens: Target size for each sub-chunk
            
        Returns:
            List of smaller chunks
        """
        # First, try to extract title prefix if exists
        lines = chunk.split('\n')
        title_lines = []
        content_start_idx = 0
        
        # Extract leading title lines (markdown headings)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and stripped.startswith('#') and ' ' in stripped:
                title_lines.append(line)
                content_start_idx = i + 1
            else:
                break
        
        title_prefix = '\n'.join(title_lines) if title_lines else ''
        content_lines = lines[content_start_idx:]
        
        # Try to split by headings within content
        result_chunks = self._split_by_headings(content_lines, title_prefix, target_tokens)
        
        # If splitting by headings didn't help (still have large chunks), split by newlines
        final_chunks = []
        for sub_chunk in result_chunks:
            sub_chunk_tokens = num_tokens_from_string(sub_chunk)
            if sub_chunk_tokens > target_tokens * 2:
                # Need further splitting by newlines
                final_chunks.extend(self._split_by_newlines(sub_chunk, title_prefix, target_tokens))
            else:
                final_chunks.append(sub_chunk)
        
        return final_chunks if final_chunks else [chunk]

    def _split_by_headings(self, content_lines: List[str], title_prefix: str, target_tokens: int) -> List[str]:
        """
        Split content by markdown headings, considering target token size.
        
        Strategy:
        1. Split content into sections by headings
        2. Merge small sections if they fit within target size
        3. Keep large sections separate (will be further split by newlines if needed)
        
        Args:
            content_lines: Content lines to split
            title_prefix: Title prefix to add to each chunk
            target_tokens: Target size for each chunk
            
        Returns:
            List of chunks split by headings
        """
        if not content_lines:
            return []
        
        # First, identify all sections (heading + content until next heading)
        sections = []
        current_section = []
        
        for line in content_lines:
            stripped = line.strip()
            is_heading = stripped and stripped.startswith('#') and ' ' in stripped
            
            if is_heading and current_section:
                # Save previous section and start new one
                sections.append(current_section)
                current_section = [line]
            else:
                current_section.append(line)
        
        # Add the last section
        if current_section:
            sections.append(current_section)
        
        # If no sections found or only one section, return as is
        if not sections:
            return []
        
        if len(sections) == 1:
            section_text = '\n'.join(sections[0])
            if title_prefix:
                return [(title_prefix + '\n\n' + section_text).strip()]
            else:
                return [section_text.strip()]
        
        # Now merge sections intelligently based on target_tokens
        chunks = []
        current_chunk_sections = []
        current_chunk_tokens = 0
        title_tokens = num_tokens_from_string(title_prefix) if title_prefix else 0
        
        for section_lines in sections:
            section_text = '\n'.join(section_lines)
            section_tokens = num_tokens_from_string(section_text)
            
            # Calculate what the total would be if we add this section
            # (including title prefix and connection between sections)
            potential_tokens = current_chunk_tokens + section_tokens
            if current_chunk_sections:
                potential_tokens += 1  # For newline between sections
            potential_tokens += title_tokens
            
            # Decision logic:
            # 1. If this section alone is too large, flush current and add it separately
            # 2. If adding this section would exceed target significantly, flush current first
            # 3. Otherwise, add to current chunk
            
            if section_tokens > target_tokens * 1.5:
                # This section is very large - needs to be in its own chunk
                # First, flush current accumulated sections
                if current_chunk_sections:
                    chunk_text = '\n'.join(['\n'.join(sec) for sec in current_chunk_sections])
                    if title_prefix:
                        full_chunk = title_prefix + '\n\n' + chunk_text
                    else:
                        full_chunk = chunk_text
                    chunks.append(full_chunk.strip())
                    current_chunk_sections = []
                    current_chunk_tokens = 0
                
                # Add large section as its own chunk
                if title_prefix:
                    full_chunk = title_prefix + '\n\n' + section_text
                else:
                    full_chunk = section_text
                chunks.append(full_chunk.strip())
                
            elif potential_tokens > target_tokens and current_chunk_sections:
                # Adding this would exceed target, flush current first
                chunk_text = '\n'.join(['\n'.join(sec) for sec in current_chunk_sections])
                if title_prefix:
                    full_chunk = title_prefix + '\n\n' + chunk_text
                else:
                    full_chunk = chunk_text
                chunks.append(full_chunk.strip())
                
                # Start new chunk with current section
                current_chunk_sections = [section_lines]
                current_chunk_tokens = section_tokens
                
            else:
                # Add to current chunk
                current_chunk_sections.append(section_lines)
                current_chunk_tokens += section_tokens
        
        # Add remaining sections
        if current_chunk_sections:
            chunk_text = '\n'.join(['\n'.join(sec) for sec in current_chunk_sections])
            if title_prefix:
                full_chunk = title_prefix + '\n\n' + chunk_text
            else:
                full_chunk = chunk_text
            chunks.append(full_chunk.strip())
        
        return chunks if chunks else ['\n'.join(content_lines)]

    def _split_by_newlines(self, chunk: str, title_prefix: str, target_tokens: int) -> List[str]:
        """
        Split a chunk by newlines to keep chunks close to target size.
        
        Args:
            chunk: The chunk to split
            title_prefix: Title prefix to add to each sub-chunk (extracted from original chunk)
            target_tokens: Target size for each sub-chunk
            
        Returns:
            List of smaller chunks
        """
        # Extract title prefix from chunk if not provided
        lines = chunk.split('\n')
        actual_title_lines = []
        content_start = 0
        
        if not title_prefix:
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and stripped.startswith('#') and ' ' in stripped:
                    actual_title_lines.append(line)
                    content_start = i + 1
                else:
                    break
            
            if actual_title_lines:
                title_prefix = '\n'.join(actual_title_lines)
                lines = lines[content_start:]
        
        chunks = []
        current_lines = []
        current_tokens = 0
        
        # Calculate title prefix tokens once
        title_tokens = num_tokens_from_string(title_prefix) if title_prefix else 0
        
        for line in lines:
            line_tokens = num_tokens_from_string(line)
            potential_tokens = current_tokens + line_tokens + title_tokens
            
            if potential_tokens > target_tokens and current_lines:
                # Finalize current chunk
                chunk_text = '\n'.join(current_lines)
                if title_prefix:
                    full_chunk = title_prefix + '\n\n' + chunk_text
                else:
                    full_chunk = chunk_text
                
                chunks.append(full_chunk.strip())
                
                # Start new chunk
                current_lines = [line]
                current_tokens = line_tokens
            else:
                current_lines.append(line)
                current_tokens += line_tokens
        
        # Add remaining lines
        if current_lines:
            chunk_text = '\n'.join(current_lines)
            if title_prefix:
                full_chunk = title_prefix + '\n\n' + chunk_text
            else:
                full_chunk = chunk_text
            
            chunks.append(full_chunk.strip())
        
        return chunks if chunks else [chunk]
