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
Example script for reparsing failed documents in a RAGFlow dataset.

This script demonstrates how to use the FailedDocumentReparser tool to
find and reparse all failed documents in a dataset.
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
from ragflow_sdk.tools import FailedDocumentReparser


def setup_logging(log_file: str = None):
    """
    Configure logging to output to both file and console.
    
    Args:
        log_file: Path to log file. If None, defaults to './logs/reparse_failed_documents.log'
    """
    if log_file is None:
        log_file = './logs/reparse_failed_documents.log'
    
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
        description='Reparse all failed documents in a RAGFlow dataset',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reparse failed documents with default batch size (50)
  python reparse_failed_documents.py -k YOUR_API_KEY -H http://localhost:9380 -i DATASET_ID

  # Reparse with custom batch size
  python reparse_failed_documents.py -k YOUR_API_KEY -H http://localhost:9380 -i DATASET_ID -b 100

  # Reparse with custom page size for fetching documents
  python reparse_failed_documents.py -k YOUR_API_KEY -H http://localhost:9380 -i DATASET_ID --page-size 5000
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
        '-i', '--dataset-id',
        required=True,
        help='Dataset ID to reparse failed documents from'
    )
    parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=1000,
        help='Batch size for reparsing documents (default: 50)'
    )
    parser.add_argument(
        '--page-size',
        type=int,
        default=10000,
        help='Page size for fetching documents (default: 10000)'
    )
    parser.add_argument(
        '--log-file',
        default='./logs/reparse_failed_documents.log',
        help='Path to log file (default: ./logs/reparse_failed_documents.log)'
    )
    
    args = parser.parse_args()
    
    # Setup logging after parsing arguments
    setup_logging(args.log_file)
    
    # Initialize RAGFlow client
    try:
        rag = RAGFlow(args.api_key, args.host_address)
        logging.info(f"Connected to RAGFlow at {args.host_address}")
    except Exception as e:
        logging.error(f"Failed to initialize RAGFlow client: {e}")
        sys.exit(1)
    
    # Initialize FailedDocumentReparser
    reparser = FailedDocumentReparser(rag)
    
    # Reparse failed documents
    try:
        total_failed, total_reparsed = reparser.reparse_failed_documents(
            dataset_id=args.dataset_id,
            reparse_batch_size=args.batch_size,
            page_size=args.page_size
        )
        
        logging.info(f"\n✅ Reparsing completed successfully!")
        logging.info(f"   Total failed documents: {total_failed}")
        logging.info(f"   Total reparsed: {total_reparsed}")
        if total_failed > 0:
            logging.info(f"   Success rate: {total_reparsed / total_failed * 100:.2f}%")
        
    except KeyboardInterrupt:
        logging.warning("\n⚠️  Reparsing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"\n❌ Reparsing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

