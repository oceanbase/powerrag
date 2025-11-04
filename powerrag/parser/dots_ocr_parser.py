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


from .vllm_parser import VllmParser, DEFAULT_LAYOUT_PROMPT

# try:
#     # Try relative import first (when used as a package)
#     from .vllm_parser import VllmParser, DEFAULT_LAYOUT_PROMPT
# except (ImportError, ValueError):
#     # Fallback to absolute import (when loaded directly via importlib)
#     try:
#         from powerrag.parser.vllm_parser import VllmParser, DEFAULT_LAYOUT_PROMPT
#     except ImportError:
#         # Last resort: try importing from the same directory
#         import sys
#         import os
#         parser_dir = os.path.dirname(os.path.abspath(__file__))
#         if parser_dir not in sys.path:
#             sys.path.insert(0, parser_dir)
#         from vllm_parser import VllmParser, DEFAULT_LAYOUT_PROMPT

# Default OCR prompt for dots.ocr (same as DEFAULT_LAYOUT_PROMPT)
DEFAULT_OCR_PROMPT = DEFAULT_LAYOUT_PROMPT


class DotsOcrParser(VllmParser):
    """
    DotsOcrParser - Backward compatibility wrapper for VllmParser
    
    This class maintains backward compatibility with the original DotsOcrParser API.
    It uses VllmParser internally with model_name="dotsocr-model" and config_key="dots_ocr".
    
    For new code, consider using VllmParser directly:
        parser = VllmParser(filename="doc.pdf", model_name="dotsocr-model")
    """
    
    def __init__(self, filename, enable_ocr=False, ocr_prompt=DEFAULT_OCR_PROMPT, model_name="dotsocr-model", vllm_url=None):
        """
        Initialize DotsOcrParser (backward compatible wrapper)
        
        Args:
            filename: Name of the document file
            enable_ocr: Whether to enable OCR processing (for backward compatibility)
            ocr_prompt: Custom prompt for the model (default: DEFAULT_OCR_PROMPT)
            model_name: Name of the model to use (default: "dotsocr-model")
            vllm_url: vLLM service URL (if None, will read from dots_ocr config)
        """
        super().__init__(
            filename=filename,
            model_name=model_name,
            vllm_url=vllm_url,
            config_key="dots_ocr",
            prompt=ocr_prompt,
            enable_ocr=enable_ocr
        )
        # Keep backward compatibility attributes
        # self.start_page_id = from_page
        # self.end_page_id = to_page
        self.lang_list = ["ch","en"]
        self.ocr_prompt = ocr_prompt  # Alias for self.prompt
