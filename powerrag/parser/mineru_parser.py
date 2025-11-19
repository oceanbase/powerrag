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

import requests
import json
import os
import logging
import base64
import re
import sys
import threading
import subprocess
import tempfile
from pathlib import Path
from io import BytesIO
import pdfplumber
from typing import Union, Dict, TypedDict, Tuple, Optional
from api.utils.configs import get_base_config
from rag.utils.storage_factory import STORAGE_IMPL
from PIL import Image
import io
import numpy as np

LOCK_KEY_pdfplumber = "global_shared_lock_pdfplumber"
if LOCK_KEY_pdfplumber not in sys.modules:
    sys.modules[LOCK_KEY_pdfplumber] = threading.Lock()


class ImageDict(TypedDict):
    """Type definition for image dictionary in response"""

    images: Dict[str, str]  # filename -> base64 string


class MinerUPdfParser:
    def __init__(self, filename, formula_enable=True, table_enable=True, enable_ocr=False):
        self.start_page_id = 0
        self.end_page_id = -1  # -1 means parse all pages
        self.lang_list = ["ch"]
        self.parse_method = "auto"
        self.formula_enable = formula_enable
        self.table_enable = table_enable
        self.filename = filename
        self.enable_ocr = enable_ocr
        self.mineru_cli_path = "mineru"
        # if enable_ocr:
        #     global ocr
        #     ocr = OCR()

    def _check_cli_installation(self) -> bool:
        """Check if mineru CLI is installed"""
        subprocess_kwargs = {
            "capture_output": True,
            "text": True,
            "check": True,
            "encoding": "utf-8",
            "errors": "ignore",
        }
        
        try:
            result = subprocess.run([self.mineru_cli_path, "--version"], **subprocess_kwargs)
            version_info = result.stdout.strip()
            if version_info:
                logging.info(f"[MinerU CLI] Detected version: {version_info}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
            logging.debug(f"[MinerU CLI] Not available: {e}")
            return False

    def _parse_with_cli(self, pdf_path: Path, from_page: int, to_page: int) -> Tuple[int, Union[Dict, str]]:
        """
        Parse PDF using mineru CLI (fallback method)
        
        Returns:
            Tuple of (status_code, result_dict or error_message)
        """
        import shutil
        
        try:
            # Create temporary output directory
            output_dir = Path(tempfile.mkdtemp(prefix="mineru_cli_"))
            
            # Build mineru command
            cmd = [
                self.mineru_cli_path,
                "-p", str(pdf_path),
                "-o", str(output_dir),
                "-m", self.parse_method
            ]
            
            # Add language parameter
            if self.lang_list:
                cmd.extend(["-l", ",".join(self.lang_list)])
            
            logging.info(f"[MinerU CLI] Running command: {' '.join(cmd)}")
            
            # Run mineru CLI
            subprocess_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "encoding": "utf-8",
                "errors": "ignore",
            }
            
            process = subprocess.Popen(cmd, **subprocess_kwargs)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logging.error(f"[MinerU CLI] Command failed: {stderr}")
                return 500, f"MinerU CLI execution failed: {stderr}"
            
            # Read output files
            pdf_stem = pdf_path.stem
            result_dir = output_dir / pdf_stem / self.parse_method
            md_file = result_dir / f"{pdf_stem}.md"
            content_list_file = result_dir / f"{pdf_stem}_content_list.json"
            
            if not md_file.exists():
                return 500, f"MinerU CLI output file not found: {md_file}"
            
            # Read markdown content
            with open(md_file, "r", encoding="utf-8") as f:
                md_content = f.read()
            
            # Collect images
            images = {}
            images_dir = result_dir / "images"
            if images_dir.exists():
                for img_file in images_dir.glob("*"):
                    if img_file.is_file():
                        with open(img_file, "rb") as f:
                            img_base64 = base64.b64encode(f.read()).decode("utf-8")
                            images[img_file.name] = img_base64
            
            # Format result to match API response structure
            result = {
                "results": {
                    pdf_stem: {
                        "md_content": md_content,
                        "images": images
                    }
                }
            }
            
            # Clean up temporary directory
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                logging.warning(f"[MinerU CLI] Failed to clean up temp dir: {e}")
            
            logging.info(f"[MinerU CLI] Successfully parsed PDF with {len(images)} images")
            return 200, result
            
        except Exception as e:
            logging.error(f"[MinerU CLI] Unexpected error: {e}")
            return 500, f"MinerU CLI parsing failed: {str(e)}"

    def __call__(self, binary=None, from_page=0, to_page=100000, callback=None, kb_id: str = "default"):
        if callback:
            callback(msg="start to parse by mineru")
        pages = MinerUPdfParser.total_page_number(self.filename, binary=binary)
        page_size = 500
        page_ranges = [(1, 10**5)]
        all_md_content = ""
        all_images = {}
        for s, e in page_ranges:
            s -= 1
            s = max(0, s)
            e = min(e - 1, pages)
            for p in range(s, e, page_size):
                from_page = p
                to_page = min(p + page_size, e)
                try:
                    status, sub_result = self.parse_document(self.filename, binary, from_page=from_page, to_page=to_page)
                except Exception as e:
                    logging.error(f"Failed to parse page {from_page} to {to_page}: {str(e)}")
                    if callback:
                        callback(msg=f"Error: {str(e)}")
                    return []
                if status != 200:
                    if callback:
                        callback(msg=sub_result)
                    return []
                else:
                    if callback:
                        callback(msg="(page {}-{}) parse finished, start to store images".format(from_page, to_page))

                if sub_result:
                    file_results = sub_result.get("results", {})
                    if file_results:
                        first_file = next(iter(file_results.values()))
                        images: ImageDict = first_file.get("images", {})
                        md_content = first_file.get("md_content", "").replace("\n\n", "\n")
                        all_md_content += md_content
                        all_images.update(images)
                    else:
                        all_images = {"images": {}}
                        all_md_content = ""
                else:
                    all_images = {"images": {}}
                    all_md_content = ""

            new_md_content = self.store_images(all_md_content, all_images, output_dir=kb_id)
            return [new_md_content], []

    def parse_document(self, filename, binary=None, from_page: int = 0, to_page: int = 100000) -> Tuple[int, Union[Dict, str]]:
        """
        Parse document using MinerU with intelligent fallback:
        1. Try API service first (if configured)
        2. Fall back to CLI (if installed)
        3. Return error if neither available

        Args:
            filename: Name of the document file
            binary: Optional binary content of the file. If provided, this will be used instead of reading from filename
            from_page: Starting page number to parse (default: 0)
            to_page: Ending page number to parse (default: 100000)

        Returns:
            Tuple containing:
                - HTTP status code (int)
                - Response content (Dict on success, error message string on failure)
        """
        
        # Strategy 1: use CLI
        if self._check_cli_installation():
            logging.info("[MinerU] Using CLI method")
            temp_pdf_path = None
            try:
                # Prepare PDF file for CLI
                if binary is not None:
                    # Save binary to temporary file
                    temp_dir = Path(tempfile.mkdtemp(prefix="mineru_input_"))
                    temp_pdf_path = temp_dir / Path(filename).name
                    with open(temp_pdf_path, "wb") as f:
                        f.write(binary)
                    pdf_path = temp_pdf_path
                elif os.path.isfile(filename):
                    pdf_path = Path(filename)
                else:
                    return 400, f"Unable to process document: {filename}"
                
                # Parse with CLI
                status, result = self._parse_with_cli(pdf_path, from_page, to_page)
                
                # Clean up temporary file
                if temp_pdf_path and temp_pdf_path.exists():
                    try:
                        temp_pdf_path.unlink()
                        temp_pdf_path.parent.rmdir()
                    except Exception as e:
                        logging.warning(f"[MinerU CLI] Failed to clean up temp file: {e}")
                
                return status, result
            except Exception as e:
                logging.error(f"[MinerU] CLI method failed: {e}")
                # return 500, f"MinerU CLI parsing failed: {str(e)}"

    # Strategy 2: Try API service first
        mineru_config = get_base_config("mineru", {}) or {}

        try:
            logging.info("[MinerU] Attempting to use API service")
            return self._parse_with_api(filename, binary, from_page, to_page, mineru_config)
        except Exception as e:
            logging.warning(f"[MinerU] API service failed: {e}")


        # Strategy 3: No method available
        error_msg = (
            "MinerU is not available. Please either:\n"
            "1. Configure MinerU API service in conf/service_conf.yaml under 'mineru.hosts', or\n"
            "2. Install MinerU CLI: pip install -U 'mineru[core]'"
        )
        logging.error(f"[MinerU] {error_msg}")
        return 503, error_msg

    def _parse_with_api(self, filename, binary, from_page: int, to_page: int, mineru_config: dict) -> Tuple[int, Union[Dict, str]]:
        """
        Parse document using MinerU API service
        
        Args:
            filename: Document filename
            binary: Binary content of the file
            from_page: Starting page number
            to_page: Ending page number
            host: API service host URL
            mineru_config: Configuration dictionary
            
        Returns:
            Tuple of (status_code, result)
        """
        backend = mineru_config.get("backend", "pipeline")
        server_url = mineru_config.get("server_url")
        host = mineru_config.get("hosts")
        
        if backend == "vlm-http-client" and not server_url:
            raise ValueError("MinerU server_url configuration is missing when backend is vlm-http-client")

        # Prepare API endpoint
        api_url = f"{host}/file_parse"

        # Check if service is available
        try:
            response = requests.get(f"{host}/docs", timeout=5)
            if response.status_code != 200:
                raise ConnectionError(f"MinerU service returned status {response.status_code}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MinerU service: {str(e)}")
        
        # Prepare multipart form data
        files = {}
        data = {
            "return_middle_json": "false",
            "return_model_output": "false",
            "return_md": "true",
            "return_images": "true",
            "end_page_id": str(to_page if to_page != -1 else 99999),
            "parse_method": self.parse_method,
            "start_page_id": str(from_page),
            "lang_list": self.lang_list,
            "output_dir": "./output",
            "return_content_list": "false",
            "backend": backend,
            "server_url": server_url,
            "table_enable": str(self.table_enable).lower(),
            "formula_enable": str(self.formula_enable).lower(),
        }

        # Handle file upload
        if binary is not None:
            files["files"] = (filename, binary, "application/pdf")
        elif os.path.isfile(filename):
            with open(filename, "rb") as f:
                files["files"] = (filename, f.read(), "application/pdf")
        else:
            raise ValueError(f"Unable to process document: {filename}")

        # Make API request
        headers = {"accept": "application/json"}
        response = requests.post(api_url, files=files, data=data, headers=headers, timeout=300)

        # Handle response
        if response.status_code == 200:
            try:
                result = response.json()
                logging.info("[MinerU API] Successfully parsed document")
                return response.status_code, result
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON response from API")
        else:
            raise ValueError(f"API request failed with status {response.status_code}: {response.text}")

    def store_images(self, md_content: str, images: ImageDict, output_dir: str) -> str:
        """
        Store images from MinerU response to OceanBase storage and update markdown content

        Args:
            md_content: The markdown content containing image references
            images: Dictionary of image data from MinerU response
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

                # Store image in OceanBase
                STORAGE_IMPL.put(output_dir, img_name, img_bytes)

                # Generate URL for the image using PowerRAG image access endpoint
                # Get PowerRAG server configuration
                powerrag_config = get_base_config("powerrag", {}) or {}
                server_url = os.environ.get("PUBLIC_SERVER_URL", "http://localhost:6000")
                
                # Ensure server_url has protocol prefix
                if not server_url.startswith("http://") and not server_url.startswith("https://"):
                    server_url = f"http://{server_url}"
                
                # Construct the image URL using PowerRAG chunk image endpoint
                kb_id = output_dir.split('/')[0] if '/' in output_dir else output_dir
                image_url = f"{server_url}/api/v1/powerrag/chunk/image/{kb_id}/{img_name}"

                # Add to result list
                image_info.append((img_name, image_url))

                # Update markdown content to use new image URL
                # Match both standard markdown image syntax and HTML img tags
                # 改进的模式：支持路径匹配
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
                # if self.enable_ocr:
                #     image_description = self.ocr_images(img_bytes)
                #     updated_content = updated_content.replace("$$00$$", image_description)
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

    def ocr_images(self, binary) -> str:
        """
        OCR images from MinerU response to text
        
        Note: OCR functionality is currently disabled/not implemented.
        This method is kept for backward compatibility.
        """
        if binary is None:
            return ""
        # OCR functionality is not currently implemented
        # Uncomment and configure OCR if needed:
        # if ocr is None:
        #     return ""
        # try:
        #     img = Image.open(io.BytesIO(binary)).convert("RGB")
        #     img_array = np.array(img.convert("RGB"))
        #     bxs = ocr(img_array)
        #     txt = ",".join([t[0] for _, t in bxs if t[0]])
        #     return txt
        # except Exception as e:
        #     logging.error(f"Failed to ocr images: {str(e)}")
        #     return ""
        return ""

    @staticmethod
    def total_page_number(fnm, binary=None):
        try:
            with sys.modules[LOCK_KEY_pdfplumber]:
                pdf = pdfplumber.open(fnm) if not binary else pdfplumber.open(BytesIO(binary))
            total_page = len(pdf.pages)
            pdf.close()
            return total_page
        except Exception:
            logging.exception("total_page_number")
            return 0