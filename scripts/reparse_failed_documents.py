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

import argparse
import time
import logging

from sdk.python.ragflow_sdk.ragflow import RAGFlow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def retry_with_backoff(func, max_retries=10, max_backoff=8):
    """
    Retry wrapper with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts (default: 10)
        max_backoff: Maximum retry interval in seconds (default: 8)
    """
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    # Calculate exponential backoff: 2^attempt, capped at max_backoff
                    backoff_time = min(2 ** attempt, max_backoff)
                    logging.warning(f"  ⚠️  Error: {str(e)}")
                    logging.info(f"  Retrying in {backoff_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(backoff_time)
                else:
                    # Final attempt failed, re-raise the exception
                    logging.error(f"  ❌ Failed after {max_retries} attempts: {str(e)}")
                    raise
    return wrapper


def reparse_failed_documents(rag: RAGFlow, dataset_id: str, batch_size: int = 50):
    """
    Reparse all failed documents in a dataset.
    
    Args:
        rag: RAGFlow client instance
        dataset_id: Dataset ID to reparse documents from
        batch_size: Batch size for reparsing documents (default: 50)
    """
    # Validate batch_size
    if batch_size <= 0:
        raise ValueError(f"batch_size must be greater than 0, got {batch_size}")
    if batch_size > 10000:
        raise ValueError(f"batch_size exceeds maximum limit of 10000, got {batch_size}")
    
    # Get dataset
    datasets = rag.list_datasets(id=dataset_id)
    if not datasets:
        raise Exception(f"Dataset with ID '{dataset_id}' not found")
    ds = datasets[0]
    logging.info(f"Using dataset: {ds.name} (ID: {ds.id})")
    
    # Stream processing: fetch documents page by page, filter failed ones, and reparse when batch_size is reached
    logging.info("Fetching documents from dataset and processing failed ones in batches...")
    page = 1
    page_size = 10000
    total_documents = 0
    total_failed = 0
    total_reparsed = 0
    pending_failed_doc_ids = []  # Accumulate failed document IDs until batch_size is reached
    
    def reparse_batch(doc_ids):
        """Reparse a batch of documents."""
        nonlocal total_reparsed
        # This check should not be needed if the calling code is correct,
        # but kept as a safety measure
        if not doc_ids:
            logging.warning("  ⚠️  Skipping empty batch (this should not happen)")
            return
        
        logging.info(f"  Reparsing batch of {len(doc_ids)} documents...")
        try:
            ds.async_parse_documents(doc_ids)
            total_reparsed += len(doc_ids)
            logging.info(f"  Batch completed: {len(doc_ids)} documents parsed successfully")
            logging.info(f"  Total reparsed so far: {total_reparsed}")
        except Exception as e:
            logging.error(f"  ❌ Error reparsing batch: {e}")
            raise
    
    # Wrap reparse_batch with retry logic
    reparse_batch_with_retry = retry_with_backoff(reparse_batch, max_retries=10, max_backoff=8)
    
    # Helper function to fetch documents with retry
    def fetch_documents_page(page_num, page_sz):
        """Fetch a page of documents with retry logic."""
        return ds.list_documents(page=page_num, page_size=page_sz, orderby="id", desc=False)
    
    fetch_documents_with_retry = retry_with_backoff(fetch_documents_page, max_retries=10, max_backoff=8)
    batch_number = 0
    
    while True:
        # Fetch a page of documents
        logging.info(f"Fetching page {page} (page_size={page_size})...")
        documents = fetch_documents_with_retry(page, page_size)
        
        if not documents:
            break
        
        total_documents += len(documents)
        logging.info(f"  Page {page}: fetched {len(documents)} documents (total: {total_documents})")
        
        # Filter failed documents from this page
        page_failed_docs = []
        for doc in documents:
            # Check if document parsing failed
            # run status can be "FAIL", "DONE", "CANCEL", etc.
            if isinstance(doc.run, str) and doc.run.upper() == "FAIL":
                page_failed_docs.append(doc)
                pending_failed_doc_ids.append(doc.id)
                total_failed += 1
        
        if page_failed_docs:
            logging.info(f"  Found {len(page_failed_docs)} failed documents in this page (total failed: {total_failed})")
        
        # If we've accumulated enough failed documents, reparse them
        while len(pending_failed_doc_ids) >= batch_size:
            batch_number += 1
            batch = pending_failed_doc_ids[:batch_size]
            pending_failed_doc_ids = pending_failed_doc_ids[batch_size:]  # Remove only the processed batch
            logging.info(f"\nProcessing batch {batch_number} ({len(batch)} documents)...")
            reparse_batch_with_retry(batch)
        
        # Check if this is the last page
        if len(documents) < page_size:
            break
        page += 1
    
    logging.info(f"\nFinished fetching all documents. Total: {total_documents}, Failed: {total_failed}")
    
    # Process remaining failed documents (if any)
    if pending_failed_doc_ids:
        batch_number += 1
        logging.info(f"\nProcessing final batch {batch_number} ({len(pending_failed_doc_ids)} documents)...")
        reparse_batch_with_retry(pending_failed_doc_ids)
    
    if total_failed == 0:
        logging.info("✅ No failed documents found in the dataset")
        return
    
    logging.info("\n" + "=" * 60)
    logging.info(f"✅ Reparsing completed! Successfully reparsed: {total_reparsed}/{total_failed} documents")


def main():
    parser = argparse.ArgumentParser(description='Reparse all failed documents in a RAGFlow dataset')
    parser.add_argument('-k', '--api-key', required=True, help='RAGFlow API key')
    parser.add_argument('-H', '--host-address', required=True, help='RAGFlow host address (e.g., http://localhost:9380)')
    parser.add_argument('-i', '--dataset-id', required=True, help='Dataset ID to reparse failed documents from')
    parser.add_argument('-b', '--batch-size', type=int, default=50, help='Batch size for reparsing documents (default: 50)')
    
    args = parser.parse_args()
    
    # Initialize RAGFlow client
    rag = RAGFlow(args.api_key, args.host_address)
    
    # Reparse failed documents
    reparse_failed_documents(rag, args.dataset_id, args.batch_size)


if __name__ == "__main__":
    main()

