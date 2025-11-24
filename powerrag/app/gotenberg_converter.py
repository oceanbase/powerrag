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
Gotenberg document converter utilities.

This module provides functions to convert various document formats to PDF
using Gotenberg service. Reference: https://gotenberg.dev/docs/routes
"""

import os
import logging
import io
import requests
from typing import Optional, Callable, Tuple
from api.utils.configs import get_base_config

logger = logging.getLogger(__name__)


def _get_gotenberg_url() -> str:
    """Get Gotenberg service URL from configuration."""
    gotenberg_config = get_base_config("gotenberg", {}) or {}
    return gotenberg_config.get("url", "http://localhost:3000")


def _perform_conversion(
    url: str,
    files: dict,
    filename: str,
    callback: Optional[Callable],
    trace_id: Optional[str],
    timeout: int,
    doc_type: str
) -> Tuple[bytes, str]:
    """
    Perform the actual conversion request to Gotenberg.
    
    Args:
        url: Gotenberg API endpoint URL
        files: Files dictionary for multipart/form-data request
        filename: Original filename
        callback: Optional callback function for progress updates
        trace_id: Optional trace ID for request tracking
        timeout: Request timeout in seconds
        doc_type: Document type string for logging (e.g., "Office document", "HTML document")
    
    Returns:
        Tuple of (pdf_binary, pdf_filename)
    
    Raises:
        GotenbergBadRequestError: If Gotenberg returns 400 Bad Request
        GotenbergServiceUnavailableError: If Gotenberg returns 503 Service Unavailable
        GotenbergError: For other conversion errors
    """
    # Optional: Add trace header for request tracking
    headers = {}
    if trace_id:
        headers['Gotenberg-Trace'] = str(trace_id)
    
    logger.info(f"Converting {doc_type} to PDF via Gotenberg: {filename}")
    response = requests.post(url, files=files, headers=headers, timeout=timeout)
    
    # Handle different response status codes according to Gotenberg docs
    if response.status_code == 200:
        pdf_binary = response.content
        pdf_filename = os.path.splitext(filename)[0] + ".pdf"
        logger.info(f"Successfully converted {filename} to PDF ({len(pdf_binary)} bytes)")
        
        if callback:
            callback(0.2, f"{doc_type} converted to PDF successfully")
        
        return pdf_binary, pdf_filename
    elif response.status_code == 400:
        error_msg = f"Gotenberg conversion failed: Bad Request - {response.text}"
        logger.error(error_msg)
        raise GotenbergBadRequestError(error_msg)
    elif response.status_code == 503:
        error_msg = f"Gotenberg conversion failed: Service Unavailable - {response.text}"
        logger.error(error_msg)
        raise GotenbergServiceUnavailableError(error_msg)
    else:
        error_msg = f"Gotenberg conversion failed with status {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise GotenbergError(error_msg)


def convert_office_to_pdf(
    filename: str,
    binary: Optional[bytes] = None,
    callback: Optional[Callable] = None,
    trace_id: Optional[str] = None,
    timeout: int = 120
) -> Tuple[bytes, str]:
    """
    Convert Office documents (Word, Excel, PowerPoint) to PDF using Gotenberg LibreOffice route.
    
    Reference: https://gotenberg.dev/docs/routes#office-documents-into-pdfs-route
    
    Args:
        filename: Path to the Office document file
        binary: Optional binary content of the file. If None, file will be read from disk.
        callback: Optional callback function for progress updates (progress, message)
        trace_id: Optional trace ID for request tracking
        timeout: Request timeout in seconds (default: 120)
    
    Returns:
        Tuple of (pdf_binary, pdf_filename)
    
    Raises:
        GotenbergBadRequestError: If Gotenberg returns 400 Bad Request
        GotenbergServiceUnavailableError: If Gotenberg returns 503 Service Unavailable
        GotenbergNetworkError: If network errors occur
        GotenbergError: For other conversion errors
    """
    if callback:
        callback(0.15, "Converting Office document to PDF...")
    
    gotenberg_url = _get_gotenberg_url()
    url = f"{gotenberg_url}/forms/libreoffice/convert"
    
    # Prepare file content using context manager for proper resource management
    try:
        if binary:
            # Use BytesIO for binary content (no need to close)
            # Ensure binary is bytes type for consistency
            office_content = binary if isinstance(binary, bytes) else binary.encode('utf-8')
            files = {'files': (os.path.basename(filename), io.BytesIO(office_content))}
            return _perform_conversion(
                url, files, filename, callback, trace_id, timeout, "Office document"
            )
        else:
            # Use context manager to ensure file is always closed, even on exception
            with open(filename, 'rb') as file_handle:
                files = {'files': (os.path.basename(filename), file_handle)}
                return _perform_conversion(
                    url, files, filename, callback, trace_id, timeout, "Office document"
                )
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to convert Office document to PDF (network error): {str(e)}"
        logger.error(error_msg)
        if callback:
            callback(-1, error_msg)
        # Preserve original exception type by wrapping it
        raise GotenbergNetworkError(error_msg) from e
    except GotenbergConversionError:
        # Re-raise Gotenberg-specific exceptions as-is
        raise
    except Exception as e:
        error_msg = f"Failed to convert Office document to PDF: {str(e)}"
        logger.error(error_msg)
        if callback:
            callback(-1, error_msg)
        # Wrap unexpected exceptions
        raise GotenbergError(error_msg) from e


def convert_html_to_pdf(
    filename: str,
    binary: Optional[bytes] = None,
    callback: Optional[Callable] = None,
    trace_id: Optional[str] = None,
    timeout: int = 120
) -> Tuple[bytes, str]:
    """
    Convert HTML documents to PDF using Gotenberg Chromium route.
    
    Reference: https://gotenberg.dev/docs/routes#html-file-into-pdf-route
    
    Note: According to Gotenberg docs, the filename must be 'index.html' for HTML route.
    
    Args:
        filename: Path to the HTML file (original filename for logging)
        binary: Optional binary content of the file. If None, file will be read from disk.
        callback: Optional callback function for progress updates (progress, message)
        trace_id: Optional trace ID for request tracking
        timeout: Request timeout in seconds (default: 120)
    
    Returns:
        Tuple of (pdf_binary, pdf_filename)
    
    Raises:
        GotenbergBadRequestError: If Gotenberg returns 400 Bad Request
        GotenbergServiceUnavailableError: If Gotenberg returns 503 Service Unavailable
        GotenbergNetworkError: If network errors occur
        GotenbergError: For other conversion errors
    """
    if callback:
        callback(0.15, "Converting HTML document to PDF...")
    
    gotenberg_url = _get_gotenberg_url()
    url = f"{gotenberg_url}/forms/chromium/convert/html"
    
    # Prepare file content - Gotenberg requires filename to be 'index.html' for HTML route
    # Use context manager for proper resource management
    try:
        if binary:
            # Use BytesIO for binary content (no need to close)
            html_content = binary if isinstance(binary, bytes) else binary.encode('utf-8')
            files = {'files': ('index.html', io.BytesIO(html_content))}
            return _perform_conversion(
                url, files, filename, callback, trace_id, timeout, "HTML document"
            )
        else:
            # Use context manager to ensure file is always closed, even on exception
            with open(filename, 'rb') as file_handle:
                files = {'files': ('index.html', file_handle)}
                return _perform_conversion(
                    url, files, filename, callback, trace_id, timeout, "HTML document"
                )
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to convert HTML document to PDF (network error): {str(e)}"
        logger.error(error_msg)
        if callback:
            callback(-1, error_msg)
        # Preserve original exception type by wrapping it
        raise GotenbergNetworkError(error_msg) from e
    except GotenbergConversionError:
        # Re-raise Gotenberg-specific exceptions as-is
        raise
    except Exception as e:
        error_msg = f"Failed to convert HTML document to PDF: {str(e)}"
        logger.error(error_msg)
        if callback:
            callback(-1, error_msg)
        # Wrap unexpected exceptions
        raise GotenbergError(error_msg) from e

# Custom exception classes for better error handling
class GotenbergConversionError(Exception):
    """Base exception for all Gotenberg conversion errors."""
    pass


class GotenbergBadRequestError(GotenbergConversionError):
    """Raised when Gotenberg returns a 400 Bad Request status."""
    pass


class GotenbergServiceUnavailableError(GotenbergConversionError):
    """Raised when Gotenberg returns a 503 Service Unavailable status."""
    pass


class GotenbergNetworkError(GotenbergConversionError):
    """Raised when network errors occur during conversion."""
    pass


class GotenbergError(GotenbergConversionError):
    """Raised for other Gotenberg conversion errors."""
    pass