#!/usr/bin/env python3
#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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
Example script for batch uploading documents to RAGFlow using BatchUploader.

This script demonstrates how to use the BatchUploader tool to upload
documents from various file formats (JSON, JSONL, CSV, XLSX, XLS) to RAGFlow.
"""

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Add parent directory to path to import ragflow_sdk
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import BatchUploader, DocumentExtractor, FieldMapper


def setup_logging(log_file: str = None):
    """
    Configure logging to output to both file and console.
    
    Args:
        log_file: Path to log file. If None, defaults to './logs/batch_upload.log'
    """
    if log_file is None:
        log_file = './logs/batch_upload.log'
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging to file: {os.path.abspath(log_file)}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch upload documents to RAGFlow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload to a new dataset
  python batch_upload.py -k YOUR_API_KEY -H http://localhost:9380 -d /path/to/files

  # Upload to an existing dataset
  python batch_upload.py -k YOUR_API_KEY -H http://localhost:9380 -d /path/to/files -i DATASET_ID

  # Upload with custom field mapping
  python batch_upload.py -k YOUR_API_KEY -H http://localhost:9380 -d /path/to/files \\
      --title-field "article_title" --content-field "article_body"

  # Upload with custom batch size and resume support
  python batch_upload.py -k YOUR_API_KEY -H http://localhost:9380 -d /path/to/files -b 10 --resume
        """
    )
    parser.add_argument(
        '-k', '--api-key',
        required=True,
        help='RAGFlow API key'
    )
    parser.add_argument(
        '-H', '--host-address',
        required=True,
        help='RAGFlow host address (e.g., http://localhost:9380)'
    )
    parser.add_argument(
        '-d', '--data-dir',
        required=True,
        help='Directory containing files to upload'
    )
    parser.add_argument(
        '-i', '--dataset-id',
        help='Dataset ID to use (if not provided, a new dataset will be created)'
    )
    parser.add_argument(
        '-n', '--dataset-name',
        help='Name for new dataset (default: auto-generated)'
    )
    parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=5,
        help='Batch size for uploading documents (default: 5)'
    )
    parser.add_argument(
        '-s', '--snapshot-file',
        default='upload_snapshot.json',
        help='Snapshot file for resume support (default: upload_snapshot.json)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last snapshot'
    )
    parser.add_argument(
        '--file-extension',
        default='txt',
        help='File extension for uploaded documents (default: txt)'
    )
    parser.add_argument(
        '--title-field',
        help='Source field name for title (default: auto-detect)'
    )
    parser.add_argument(
        '--content-field',
        help='Source field name for content (default: auto-detect)'
    )
    parser.add_argument(
        '--doc-id-field',
        help='Source field name for doc_id (default: auto-detect)'
    )
    parser.add_argument(
        '--doc-url-field',
        help='Source field name for doc_url (default: auto-detect)'
    )
    parser.add_argument(
        '--tags-field',
        help='Source field name for tags (default: auto-detect)'
    )
    parser.add_argument(
        '--tags-separator',
        default=',',
        help='Separator for tags string (default: ,)'
    )
    parser.add_argument(
        '--file-patterns',
        nargs='+',
        help='File patterns to match (e.g., *.json *.csv)'
    )
    parser.add_argument(
        '--multi-doc-extensions',
        nargs='+',
        default=['json', 'jsonl', 'csv', 'xlsx', 'xls'],
        help='File extensions (without dot) to treat as multi-document formats. Default: json jsonl csv xlsx xls'
    )
    parser.add_argument(
        '--log-file',
        default='./logs/batch_upload.log',
        help='Path to log file (default: ./logs/batch_upload.log)'
    )
    
    args = parser.parse_args()
    
    # Setup logging after parsing arguments
    setup_logging(args.log_file)
    
    # Validate data directory
    if not os.path.isdir(args.data_dir):
        logging.error(f"Error: Data directory '{args.data_dir}' does not exist")
        sys.exit(1)
    
    # Initialize RAGFlow client
    try:
        rag = RAGFlow(args.api_key, args.host_address)
        logging.info(f"Connected to RAGFlow at {args.host_address}")
    except Exception as e:
        logging.error(f"Failed to initialize RAGFlow client: {e}")
        sys.exit(1)
    
    # Create field mapper if custom mappings provided
    field_mapper = None
    if any([args.title_field, args.content_field, args.doc_id_field, 
            args.doc_url_field, args.tags_field]):
        field_mapper = FieldMapper(
            title_field=args.title_field,
            content_field=args.content_field,
            doc_id_field=args.doc_id_field,
            doc_url_field=args.doc_url_field,
            tags_field=args.tags_field,
            tags_separator=args.tags_separator
        )
    
    # Create document extractor
    extractor = DocumentExtractor(
        field_mapper=field_mapper,
        multi_doc_extensions=args.multi_doc_extensions
    )
    
    # Initialize BatchUploader
    uploader = BatchUploader(rag)
    
    # Upload files
    try:
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=args.data_dir,
            dataset_id=args.dataset_id,
            dataset_name=args.dataset_name,
            batch_size=args.batch_size,
            snapshot_file=args.snapshot_file,
            resume=args.resume,
            file_extension=args.file_extension,
            file_patterns=args.file_patterns
        )
        
        logging.info(f"\n✅ Upload completed successfully!")
        logging.info(f"   Total documents: {total_docs}")
        logging.info(f"   Total files: {total_files}")
        logging.info(f"   Dataset ID: {uploader.dataset.id}")
        logging.info(f"   Dataset Name: {uploader.dataset.name}")
        
    except KeyboardInterrupt:
        logging.warning("\n⚠️  Upload interrupted by user")
        logging.info(f"💡 You can resume later using: --resume")
        sys.exit(1)
    except Exception as e:
        logging.error(f"\n❌ Upload failed: {e}")
        logging.info(f"💡 You can resume later using: --resume")
        sys.exit(1)


if __name__ == "__main__":
    main()

