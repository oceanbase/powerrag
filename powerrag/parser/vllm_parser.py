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
import logging
import base64
import re
import json
import sys
from io import BytesIO
import pdfplumber
from typing import Union, Dict, TypedDict, Tuple, List, Optional
from api.utils.configs import get_base_config
from rag.utils.storage_factory import STORAGE_IMPL
from openai import OpenAI
from PIL import Image
import io


# Constants for image processing
MIN_PIXELS = 3136
MAX_PIXELS = 11289600


# Default prompt for layout recognition
DEFAULT_LAYOUT_PROMPT = """Please output the layout information from the PDF image, including each layout element's bbox, its category, and the corresponding text content within the bbox.

1. Bbox format: [x1, y1, x2, y2]

2. Layout Categories: The possible categories are ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title'].

3. Text Extraction & Formatting Rules:
    - Picture: For the 'Picture' category, the text field should be omitted.
    - Formula: Format its text as LaTeX.
    - Table: Format its text as HTML.
    - All Others (Text, Title, etc.): Format their text as Markdown.

4. Constraints:
    - The output text must be the original text from the image, with no translation.
    - All layout elements must be sorted according to human reading order.

5. Final Output: The entire output must be a single JSON object.
"""


class ImageDict(TypedDict):
    """Type definition for image dictionary in response"""

    images: Dict[str, str]  # filename -> base64 string


class VllmParser:
    """
    Generic parser using vLLM API for document parsing.
    
    This parser uses standard OpenAI-compatible vLLM API to perform document parsing.
    It supports any vision-language model deployed via vLLM.
    
    Args:
        filename: Name of the document file
        model_name: Name of the model to use (e.g., "dotsocr-model", "qwen-vl", etc.)
        vllm_url: vLLM service URL (if None, will read from config)
        config_key: Configuration key for reading vLLM URL (default: "vllm" or "dots_ocr")
        prompt: Custom prompt for the model (default: DEFAULT_LAYOUT_PROMPT)
        enable_ocr: Whether to enable OCR processing (for backward compatibility)
    """
    
    def __init__(
        self, 
        filename: str,
        model_name: str = "dotsocr-model",
        vllm_url: Optional[str] = None,
        config_key: str = "vllm",
        prompt: str = DEFAULT_LAYOUT_PROMPT,
        enable_ocr: bool = False
    ):
        self.lang_list = ["ch"]
        self.filename = filename
        self.enable_ocr = enable_ocr
        self.model_name = model_name
        self.prompt = prompt
        self.config_key = config_key
        
        # Set vllm_url if provided, otherwise will be read from config in __call__
        self.vllm_url = vllm_url

    def __call__(self, binary=None, from_page=0, to_page=100000, callback=None, doc_id: str = "default", kb_id: str = "default"):
        if callback:
            callback(msg=f"start to parse by vLLM model: {self.model_name}")

        # Get vLLM URL from config if not provided in __init__
        if self.vllm_url is None:
            config = get_base_config(self.config_key, {}) or {}
            vllm_url_base = config.get('vllm_url', '')
            if not vllm_url_base:
                # Fallback to dots_ocr config for backward compatibility
                dots_ocr_config = get_base_config("dots_ocr", {}) or {}
                vllm_url_base = dots_ocr_config.get('vllm_url', '')
            self.vllm_url = f"{vllm_url_base}/v1" if vllm_url_base else None
        
        if not self.vllm_url:
            error_msg = f"vLLM URL not configured. Please set {self.config_key}.vllm_url in config or pass vllm_url to __init__"
            logging.error(error_msg)
            if callback:
                callback(msg=error_msg)
            return []
        
        try:
            # Parse document using vLLM
            # Pass kb_id and doc_id to parse_document so images are stored in the correct directory
            status, result = self.parse_document(
                self.filename, 
                binary, 
                from_page=from_page, 
                to_page=to_page, 
                vllm_url=self.vllm_url,
                doc_id=doc_id,
                kb_id=kb_id
            )
        except Exception as e:
            logging.error(f"Failed to parse document with vLLM: {str(e)}")
            if callback:
                callback(msg=f"Error: {str(e)}")
            return []
            
        if status != 200:
            if callback:
                callback(msg=result)
            return []
        else:
            if callback:
                callback(msg="parse finished, start to store images")

        # Process results
        if result:
            file_results = result.get("results", {})
            if file_results:
                first_file = next(iter(file_results.values()))
                images: ImageDict = first_file.get("images", {})
                md_content = first_file.get("md_content", "").replace("\n\n", "\n")
                
                # Images are already stored in layoutjson2md, but we may need to update URLs
                # if they were stored in a temporary directory. Since we now pass kb_id and doc_id to
                # parse_document, images should already be in the correct location.
                # However, we still call store_images for backward compatibility and to handle
                # any images that might come from the API response (though vLLM doesn't return separate images)
                output_dir = f"{kb_id}/{doc_id}" if kb_id and doc_id else (doc_id if doc_id else "default")
                new_md_content = self.store_images(md_content, images, output_dir=output_dir)
                return [new_md_content], []
            else:
                return [""], []
        else:
            return [""], []

    def parse_document(self, filename, binary=None, from_page: int = 0, to_page: int = 100000, vllm_url=None, doc_id: str = None, kb_id: str = None) -> Tuple[int, Union[Dict, str]]:
        """
        Parse document using vLLM API

        Args:
            filename: Name of the document file
            binary: Optional binary content of the file. If provided, this will be used instead of reading from filename
            from_page: Starting page number to parse (default: 0)
            to_page: Ending page number to parse (default: 100000)
            vllm_url: vLLM service URL for inference
            doc_id: Document ID for storing images
            kb_id: Knowledge base ID for storing images. Images will be stored in kb_id/doc_id path.

        Returns:
            Tuple containing:
                - HTTP status code (int)
                - Response content (Dict on success, error message string on failure)
        """
        try:
            # Prepare input data
            if binary is not None:
                input_data = binary
            elif os.path.isfile(filename):
                with open(filename, "rb") as f:
                    input_data = f.read()
            else:
                return 400, f"Unable to process document: {filename}"

            # Convert PDF to images for processing
            images = self._pdf_to_images(input_data, from_page, to_page)
            
            # Process each image with vLLM
            # Use kb_id/doc_id as output_dir if provided, otherwise use a temporary directory
            if kb_id and doc_id:
                output_dir = f"{kb_id}/{doc_id}"
            elif doc_id:
                output_dir = doc_id
            else:
                output_dir = f"vllm_temp_{os.path.basename(filename).replace('.', '_')}"
            
            all_md_content = []
            for i, image_pil in enumerate(images):
                try:
                    # Run vLLM inference
                    response_text = self._inference_with_vllm(image_pil, vllm_url=vllm_url)
                    cells, filtered = self.post_process_output(
                        response_text,
                        image_pil,
                        image_pil,
                        min_pixels=MIN_PIXELS,
                        max_pixels=MAX_PIXELS,
                    )
                    if not filtered:
                        # Pass output_dir and page_index to layoutjson2md for image storage
                        page_md_content = self.layoutjson2md(
                            image_pil, 
                            cells, 
                            text_key='text',
                            output_dir=output_dir,
                            page_index=i
                        )
                        all_md_content.append(page_md_content)
                    else:
                        # Fallback: use cleaned response as text
                        all_md_content.append(str(cells))
                except Exception as e:
                    logging.error(f"vLLM inference failed on page {i}: {str(e)}")
                    return 500, f"vLLM inference failed on page {i}: {str(e)}"
            
            # Combine results into markdown format
            md_content = "\n\n".join(all_md_content)
            
            # Prepare result structure to match API response
            # Note: Images are already stored and URLs are already in md_content
            result = {
                "results": {
                    os.path.basename(filename): {
                        "md_content": md_content,
                        "images": {}  # Images are already stored and URLs are in md_content
                    }
                }
            }
            
            logging.info(f"[vLLM] Successfully parsed document with {len(images)} pages using model: {self.model_name}")
            return 200, result
            
        except Exception as e:
            logging.error(f"[vLLM] Unexpected error: {e}")
            return 500, f"vLLM parsing failed: {str(e)}"

    def post_process_output(self, response, origin_image, input_image, min_pixels=None, max_pixels=None):
        json_load_failed = False
        cells = response
        try:
            cells = json.loads(cells)
            cells = self.post_process_cells(
                origin_image,
                cells,
                input_image.width,
                input_image.height,
                min_pixels=min_pixels,
                max_pixels=max_pixels
            )
            return cells, False
        except Exception as e:
            logging.warning(f"cells post process error: {e}")
            json_load_failed = True

        if json_load_failed:
            cleaner = OutputCleaner()
            response_clean = cleaner.clean_model_output(cells)
            if isinstance(response_clean, list):
                response_clean = "\n\n".join([cell['text'] for cell in response_clean if 'text' in cell])
            return response_clean, True

    def post_process_cells(
            self,
            origin_image: Image.Image,
            cells: List[Dict],
            input_width,  # server input width, also has smart_resize in server
            input_height,
            factor: int = 28,
            min_pixels: int = 3136,
            max_pixels: int = 11289600
    ) -> List[Dict]:
        """
        Post-processes cell bounding boxes, converting coordinates from the resized dimensions back to the original dimensions.

        Args:
            origin_image: The original PIL Image.
            cells: A list of cells containing bounding box information.
            input_width: The width of the input image sent to the server.
            input_height: The height of the input image sent to the server.
            factor: Resizing factor.
            min_pixels: Minimum number of pixels.
            max_pixels: Maximum number of pixels.

        Returns:
            A list of post-processed cells.
        """
        assert isinstance(cells, list) and len(cells) > 0 and isinstance(cells[0], dict)
        min_pixels = min_pixels or MIN_PIXELS
        max_pixels = max_pixels or MAX_PIXELS
        original_width, original_height = origin_image.size

        input_height, input_width = smart_resize(input_height, input_width, min_pixels=min_pixels,
                                                 max_pixels=max_pixels)

        scale_x = input_width / original_width
        scale_y = input_height / original_height

        cells_out = []
        for cell in cells:
            bbox = cell['bbox']
            bbox_resized = [
                int(float(bbox[0]) / scale_x),
                int(float(bbox[1]) / scale_y),
                int(float(bbox[2]) / scale_x),
                int(float(bbox[3]) / scale_y)
            ]
            cell_copy = cell.copy()
            cell_copy['bbox'] = bbox_resized
            cells_out.append(cell_copy)

        return cells_out

    def _inference_with_vllm(self, image, vllm_url):
        """
        Run inference using vLLM API (standard OpenAI-compatible interface)
        
        Args:
            image: PIL Image object
            vllm_url: vLLM service URL
            
        Returns:
            Inference result text
        """
        try:
            # Use vLLM API (standard OpenAI-compatible interface)
            client = OpenAI(api_key=os.environ.get("API_KEY", "0"), base_url=vllm_url)
            
            # Convert PIL image to base64
            image_base64 = self._pil_image_to_base64(image)
            
            messages = []
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_base64},
                        },
                        {"type": "text", "text": f"<|img|><|imgpad|><|endofimg|>{self.prompt}"}
                    ],
                }
            )
            
            response = client.chat.completions.create(
                messages=messages, 
                model=self.model_name,  # Use the model name from initialization
                max_completion_tokens=32768,
                temperature=0.1,
                top_p=0.9)
            response_text = response.choices[0].message.content
            return response_text
            
        except Exception as e:
            logging.error(f"vLLM inference error: {str(e)}")
            raise

    def layoutjson2md(self, image: Image.Image, cells: list, text_key: str = 'text', no_page_hf: bool = False, 
                     output_dir: str = None, page_index: int = 0) -> str:
        """
        Converts a layout JSON format to Markdown.

        In the layout JSON, formulas are LaTeX, tables are HTML, and text is Markdown.

        Args:
            image: A PIL Image object.
            cells: A list of dictionaries, each representing a layout cell.
            text_key: The key for the text field in the cell dictionary.
            no_page_header_footer: If True, skips page headers and footers.
            output_dir: Directory for storing images (if None, images will be embedded as base64).
            page_index: Page index for generating unique image filenames.

        Returns:
            str: The text in Markdown format.
        """
        text_items = []
        picture_index = 0

        for i, cell in enumerate(cells):
            x1, y1, x2, y2 = [int(coord) for coord in cell['bbox']]
            text = cell.get(text_key, "")

            if no_page_hf and cell['category'] in ['Page-header', 'Page-footer']:
                continue

            if cell['category'] == 'Picture':
                image_crop = image.crop((x1, y1, x2, y2))
                
                # If output_dir is provided, store image to bucket and use URL
                if output_dir:
                    # Generate unique image filename
                    img_filename = f"page_{page_index}_img_{picture_index}.png"
                    picture_index += 1
                    
                    try:
                        # Convert PIL image to bytes
                        buffered = BytesIO()
                        image_crop.save(buffered, format='PNG')
                        img_bytes = buffered.getvalue()
                        
                        # Store image in storage (bucket)
                        STORAGE_IMPL.put(output_dir, img_filename, img_bytes)
                        
                        # Generate URL for the image
                        powerrag_config = get_base_config("powerrag", {}) or {}
                        api_url = os.environ.get("PUBLIC_SERVER_URL", "http://localhost:6000")
                        image_url = f"http://{api_url}/v1/chunk/image/{output_dir}/{img_filename}"
                        
                        # Use HTML img tag with URL
                        text_items.append(f'<img src="{image_url}" alt="$$00$$" style="max-width: 60%; height: auto;">')
                    except Exception as e:
                        logging.error(f"Failed to store image {img_filename}: {str(e)}")
                        # Fallback to base64 if storage fails
                        image_base64 = self.PILimage_to_base64(image_crop)
                        text_items.append(f"![]({image_base64})")
                else:
                    # Fallback: embed as base64 if no output_dir provided
                    image_base64 = self.PILimage_to_base64(image_crop)
                    text_items.append(f"![]({image_base64})")
            elif cell['category'] == 'Formula':
                text_items.append(self.get_formula_in_markdown(text))
            else:
                text = self.clean_text(text)
                text_items.append(f"{text}")

        markdown_text = '\n\n'.join(text_items)
        return markdown_text

    def PILimage_to_base64(self, image, format='PNG'):
        buffered = BytesIO()
        image.save(buffered, format=format)
        base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f"data:image/{format.lower()};base64,{base64_str}"

    def get_formula_in_markdown(self, text: str) -> str:
        """
        Formats a string containing a formula into a standard Markdown block.

        Args:
            text (str): The input string, potentially containing a formula.

        Returns:
            str: The formatted string, ready for Markdown rendering.
        """
        # Remove leading/trailing whitespace
        text = text.strip()

        # Check if it's already enclosed in $$
        if text.startswith('$$') and text.endswith('$$'):
            text_new = text[2:-2].strip()
            if not '$' in text_new:
                return f"$$\n{text_new}\n$$"
            else:
                return text

        # Handle \[...\] format, convert to $$...$$
        if text.startswith('\\[') and text.endswith('\\]'):
            inner_content = text[2:-2].strip()
            return f"$$\n{inner_content}\n$$"

        # Check if it's enclosed in \[ \]
        if len(re.findall(r'.*\\\[.*\\\].*', text)) > 0:
            return text

        # Handle inline formulas ($...$)
        pattern = r'\$([^$]+)\$'
        matches = re.findall(pattern, text)
        if len(matches) > 0:
            # It's an inline formula, return it as is
            return text

            # If no LaTeX markdown syntax is present, return directly
        if not self.has_latex_markdown(text):
            return text

        # Handle unnecessary LaTeX formatting like \usepackage
        if 'usepackage' in text:
            text = self.clean_latex_preamble(text)

        if text[0] == '`' and text[-1] == '`':
            text = text[1:-1]

        # Enclose the final text in a $$ block with newlines
        text = f"$$\n{text}\n$$"
        return text

    def has_latex_markdown(self, text: str) -> bool:
        """
        Checks if a string contains LaTeX markdown patterns.

        Args:
            text (str): The string to check.

        Returns:
            bool: True if LaTeX markdown is found, otherwise False.
        """
        if not isinstance(text, str):
            return False

        # Define regular expression patterns for LaTeX markdown
        latex_patterns = [
            r'\$\$.*?\$\$',  # Block-level math formula $$...$$
            r'\$[^$\n]+?\$',  # Inline math formula $...$
            r'\\begin\{.*?\}.*?\\end\{.*?\}',  # LaTeX environment \begin{...}...\end{...}
            r'\\[a-zA-Z]+\{.*?\}',  # LaTeX command \command{...}
            r'\\[a-zA-Z]+',  # Simple LaTeX command \command
            r'\\\[.*?\\\]',  # Display math formula \[...\]
            r'\\\(.*?\\\)',  # Inline math formula \(...\)
        ]

        # Check if any of the patterns match
        for pattern in latex_patterns:
            if re.search(pattern, text, re.DOTALL):
                return True

        return False

    def clean_latex_preamble(self, latex_text: str) -> str:
        """
        Removes LaTeX preamble commands like document class and package imports.

        Args:
            latex_text (str): The original LaTeX text.

        Returns:
            str: The cleaned LaTeX text without preamble commands.
        """
        # Define patterns to be removed
        patterns = [
            r'\\documentclass\{[^}]+\}',  # \documentclass{...}
            r'\\usepackage\{[^}]+\}',  # \usepackage{...}
            r'\\usepackage\[[^\]]*\]\{[^}]+\}',  # \usepackage[options]{...}
            r'\\begin\{document\}',  # \begin{document}
            r'\\end\{document\}',  # \end{document}
        ]

        # Apply each pattern to clean the text
        cleaned_text = latex_text
        for pattern in patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

        return cleaned_text

    def clean_text(self, text: str) -> str:
        """
        Cleans text by removing extra whitespace.

        Args:
            text: The original text.

        Returns:
            str: The cleaned text.
        """
        if not text:
            return ""

        # Remove leading and trailing whitespace
        text = text.strip()

        # Replace multiple consecutive whitespace characters with a single space
        if text[:2] == '`$' and text[-2:] == '$`':
            text = text[1:-1]

        return text

    def _pil_image_to_base64(self, image):
        """
        Convert PIL image to base64 string
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded image string
        """
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

    def _pdf_to_images(self, pdf_data: bytes, from_page: int = 0, to_page: int = 100000) -> list:
        """
        Convert PDF pages to images for processing
        
        Args:
            pdf_data: PDF file data as bytes
            from_page: Starting page (0-indexed)
            to_page: Ending page (0-indexed, exclusive)
            
        Returns:
            List of PIL Image objects
        """
        images = []
        
        try:
            with sys.modules["global_shared_lock_pdfplumber"]:
                pdf = pdfplumber.open(BytesIO(pdf_data))
                
            # Adjust page range
            start_page = max(0, from_page)
            end_page = min(len(pdf.pages), to_page) if to_page != 100000 else len(pdf.pages)
            
            # Convert specified pages to images
            for i in range(start_page, end_page):
                page = pdf.pages[i]
                # Convert page to image
                img = page.to_image(resolution=200)  # Adjust resolution as needed
                images.append(img.original)  # Store PIL Image object directly
                
            pdf.close()
            
        except Exception as e:
            logging.error(f"Failed to convert PDF to images: {str(e)}")
            raise
            
        return images

    def store_images(self, md_content: str, images: ImageDict, output_dir: str) -> str:
        """
        Store images from OCR response to storage and update markdown content

        Args:
            md_content: The markdown content containing image references
            images: Dictionary of image data
            output_dir: Base directory for storing images

        Returns:
            Updated markdown content with new image URLs
        """
        if not images:
            return md_content

        image_info = []
        updated_content = md_content

        # Handle both formats: direct dict and nested dict with "images" key
        images_data = images.get("images", images) if isinstance(images, dict) else images

        for img_name, img_base64 in images_data.items():
            try:
                # Remove data URL prefix if present
                if "," in img_base64:
                    img_base64 = img_base64.split(",", 1)[1]

                # Decode base64 to bytes
                img_bytes = base64.b64decode(img_base64)

                # Store image in storage
                STORAGE_IMPL.put(output_dir, img_name, img_bytes)

                # Generate URL for the image using RAGFlow image access endpoint
                # Get RAGFlow server configuration
                powerrag_config = get_base_config("powerrag", {}) or {}
                api_url = os.environ.get("PUBLIC_SERVER_URL", "http://localhost:6000")

                # Construct the image URL using the auth_image endpoint
                image_url = f"http://{api_url}/v1/chunk/image/{output_dir}/{img_name}"

                # Add to result list
                image_info.append((img_name, image_url))

                # Update markdown content to use new image URL
                # Match both standard markdown image syntax and HTML img tags
                md_pattern = f"!\\[([^\\]]*)\\]\\([^)]*{re.escape(img_name)}\\)"
                html_pattern = f"<img[^>]*src=[\"']?[^\"']*{re.escape(img_name)}[^\"']*[\"']?[^>]*>"

                # Replace markdown image syntax with HTML img tags
                def replace_md_with_html(match):
                    alt_text = "$$00$$"
                    return f'<img src="{image_url}" alt="{alt_text}" style="max-width: 60%; height: auto;">'

                updated_content = re.sub(md_pattern, replace_md_with_html, updated_content)

                # Replace existing HTML img tags
                def replace_html_img(match):
                    img_tag = match.group(0)
                    # 提取src属性中的图片路径并替换
                    src_pattern = f"([\"']?)([^\"']*{re.escape(img_name)}[^\"']*)([\"']?)"
                    return re.sub(src_pattern, f"\\1{image_url}\\3", img_tag)

                updated_content = re.sub(html_pattern, replace_html_img, updated_content)
            except Exception as e:
                logging.error(f"Failed to store image {img_name}: {str(e)}")
                continue

        return updated_content

    def crop(self, ck, need_position=False):
        """
        Crop image from text content and extract position information.
        
        Args:
            ck: Text content (may contain position tags or image references)
            need_position: Whether to return position information
            
        Returns:
            Tuple of (image, positions) where:
            - image: PIL Image object or None
            - positions: List of position tuples [(page_num, left, right, top, bottom), ...] or None
        """
        if not ck or not ck.strip():
            if need_position:
                return None, None
            return None
        
        # Try to extract positions from text if it contains position tags
        # Format: @@page_num\tleft\tright\ttop\tbottom##
        poss = self._extract_positions(ck)
        
        if not poss:
            # No position tags found, return None
            if need_position:
                return None, None
            return None
        
        # If we have positions but no page_images, we can't crop
        # Return positions if needed, but no image
        if not hasattr(self, 'page_images') or not self.page_images:
            if need_position:
                # Return positions in the format expected by add_positions
                # Format: [(page_num, left, right, top, bottom), ...]
                formatted_positions = []
                for pns, left, right, top, bottom in poss:
                    # Use the first page number if it's a list
                    page_num = pns[0] if isinstance(pns, list) else pns
                    formatted_positions.append((page_num, left, right, top, bottom))
                return None, formatted_positions
            return None
        
        # We have positions and page_images, try to crop
        try:
            imgs = []
            positions = []
            
            for pns, left, right, top, bottom in poss:
                # Use the first page number if it's a list
                page_num = pns[0] if isinstance(pns, list) else pns
                
                # Ensure page_num is within bounds
                if page_num < 0 or page_num >= len(self.page_images):
                    continue
                
                # Crop the image from the page
                img = self.page_images[page_num]
                x0, y0, x1, y1 = int(left), int(top), int(right), int(bottom)
                
                # Ensure coordinates are within image bounds
                x0 = max(0, min(x0, img.size[0]))
                y0 = max(0, min(y0, img.size[1]))
                x1 = max(x0, min(x1, img.size[0]))
                y1 = max(y0, min(y1, img.size[1]))
                
                if x1 > x0 and y1 > y0:
                    crop_img = img.crop((x0, y0, x1, y1))
                    imgs.append(crop_img)
                    if need_position:
                        positions.append((page_num, x0, x1, y0, y1))
            
            if not imgs:
                if need_position:
                    return None, None
                return None
            
            # Combine multiple cropped images if needed
            if len(imgs) == 1:
                result_img = imgs[0]
            else:
                # Concatenate images vertically
                total_height = sum(img.size[1] for img in imgs)
                max_width = max(img.size[0] for img in imgs)
                result_img = Image.new("RGB", (max_width, total_height), (255, 255, 255))
                y_offset = 0
                for img in imgs:
                    result_img.paste(img, (0, y_offset))
                    y_offset += img.size[1]
            
            if need_position:
                return result_img, positions
            return result_img
            
        except Exception as e:
            logging.warning(f"Failed to crop image from text: {e}")
            if need_position:
                return None, None
            return None
    
    @staticmethod
    def _extract_positions(txt):
        """
        Extract position information from text containing position tags.
        
        Format: @@page_num\tleft\tright\ttop\tbottom##
        
        Returns:
            List of tuples: [(page_numbers, left, right, top, bottom), ...]
        """
        poss = []
        if not txt:
            return poss
        
        # Pattern to match position tags: @@page_num\tleft\tright\ttop\tbottom##
        pattern = r"@@([0-9-]+)\t([0-9.]+)\t([0-9.]+)\t([0-9.]+)\t([0-9.]+)##"
        
        for match in re.finditer(pattern, txt):
            pn_str, left_str, right_str, top_str, bottom_str = match.groups()
            
            # Parse page numbers (can be a range like "1-3")
            if '-' in pn_str:
                pn_start, pn_end = map(int, pn_str.split('-'))
                pns = list(range(pn_start - 1, pn_end))  # Convert to 0-based index
            else:
                pns = [int(pn_str) - 1]  # Convert to 0-based index
            
            left = float(left_str)
            right = float(right_str)
            top = float(top_str)
            bottom = float(bottom_str)
            
            poss.append((pns, left, right, top, bottom))
        
        return poss
    
    @staticmethod
    def remove_tag(txt):
        """Remove position tags from text."""
        if not txt:
            return txt
        # Remove position tags: @@page_num\tleft\tright\ttop\tbottom##
        return re.sub(r"@@[0-9-]+\t[0-9.\t]+##", "", txt)

    @staticmethod
    def total_page_number(fnm, binary=None):
        try:
            with sys.modules["global_shared_lock_pdfplumber"]:
                pdf = pdfplumber.open(fnm) if not binary else pdfplumber.open(BytesIO(binary))
            total_page = len(pdf.pages)
            pdf.close()
            return total_page
        except Exception:
            logging.exception("total_page_number")
            return 0


def smart_resize(height: int, width: int, min_pixels: int = MIN_PIXELS, max_pixels: int = MAX_PIXELS) -> Tuple[int, int]:
    """
    Resize image dimensions while maintaining aspect ratio and respecting pixel limits.
    
    Args:
        height: Original height
        width: Original width
        min_pixels: Minimum total pixels
        max_pixels: Maximum total pixels
        
    Returns:
        Tuple of (new_height, new_width)
    """
    total_pixels = height * width
    
    if total_pixels < min_pixels:
        scale = (min_pixels / total_pixels) ** 0.5
        height = int(height * scale)
        width = int(width * scale)
    elif total_pixels > max_pixels:
        scale = (max_pixels / total_pixels) ** 0.5
        height = int(height * scale)
        width = int(width * scale)
    
    return height, width


class OutputCleaner:
    """Simple output cleaner for fallback processing"""
    
    def clean_model_output(self, output):
        """Clean model output - basic implementation"""
        if isinstance(output, str):
            # Try to extract JSON from text
            try:
                # Look for JSON object in the output
                json_match = re.search(r'\{.*\}', output, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except:
                pass
        return output


# Backward compatibility: DotsOcrParser as an alias
DotsOcrParser = VllmParser

