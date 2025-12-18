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

import json
import os
import glob
import argparse
import time
import logging
from pathlib import Path

from sdk.python.ragflow_sdk.ragflow import RAGFlow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def read_json_file(file_path):
    """Read and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


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


def count_total_documents(file_list):
    """Count total documents in all JSON files."""
    total_docs = 0
    file_doc_counts = {}
    
    logging.info("Scanning files to count total documents...")
    for file_path in file_list:
        try:
            json_list = read_json_file(file_path)
            doc_count = len(json_list)
            file_doc_counts[file_path] = doc_count
            total_docs += doc_count
        except Exception as e:
            logging.warning(f"Warning: Error reading file {file_path} for counting: {e}")
            file_doc_counts[file_path] = 0
    
    return total_docs, file_doc_counts


def save_snapshot(snapshot_file, file_name, doc_index, total_processed, dataset_id=None):
    """Save processing snapshot to file."""
    snapshot = {
        "file_name": file_name,
        "doc_index": doc_index,
        "total_processed": total_processed,
        "timestamp": time.time()
    }
    if dataset_id:
        snapshot["dataset_id"] = dataset_id
    with open(snapshot_file, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2)


def load_snapshot(snapshot_file):
    """Load processing snapshot from file."""
    if not os.path.exists(snapshot_file):
        return None
    try:
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Warning: Failed to load snapshot: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Upload wiki JSON files to RAGFlow')
    parser.add_argument('-k', '--api-key', required=True, help='RAGFlow API key')
    parser.add_argument('-H', '--host-address', required=True, help='RAGFlow host address (e.g., http://localhost:9380)')
    parser.add_argument('-d', '--data-dir', required=True, help='Directory containing JSON files')
    parser.add_argument('-i', '--dataset-id', help='Dataset ID to use (if not provided, a new dataset will be created)')
    parser.add_argument('-b', '--batch-size', type=int, default=5, help='Batch size for uploading documents (default: 5)')
    parser.add_argument('-s', '--snapshot-file', default='upload_snapshot.json', help='Snapshot file for resume support (default: upload_snapshot.json)')
    parser.add_argument('--resume', action='store_true', help='Resume from last snapshot')
    
    args = parser.parse_args()
    
    # Initialize RAGFlow client
    rag = RAGFlow(args.api_key, args.host_address)
    
    # Get all JSON files
    json_pattern = os.path.join(args.data_dir, "*.json")
    file_list = glob.glob(json_pattern)
    file_list.sort()  # Process files in order (important for resume)
    
    logging.info(f"Found {len(file_list)} JSON files to process")
    
    # Load snapshot if resume is requested
    resume_file_name = None
    resume_doc_index = 0
    total_processed_docs = 0
    files_processed = 0
    dataset_id = args.dataset_id
    
    if args.resume:
        snapshot = load_snapshot(args.snapshot_file)
        if snapshot:
            resume_file_name = snapshot.get("file_name")
            resume_doc_index = snapshot.get("doc_index", 0)
            total_processed_docs = snapshot.get("total_processed", 0)
            # Restore dataset_id from snapshot if not provided in args
            if not dataset_id and "dataset_id" in snapshot:
                dataset_id = snapshot["dataset_id"]
                logging.info(f"📍 Restored dataset_id from snapshot: {dataset_id}")
            
            # Calculate how many files were completely processed
            for file_path in file_list:
                file_name = os.path.basename(file_path)
                if file_name < resume_file_name:
                    files_processed += 1
                elif file_name == resume_file_name:
                    # Current file is being processed, not completed yet
                    break
            
            logging.info(f"📍 Resuming from snapshot: {resume_file_name}, document index: {resume_doc_index}")
            logging.info(f"📍 Already processed: {total_processed_docs} documents, {files_processed} files completed")
        else:
            logging.warning("⚠️  No valid snapshot found, starting from beginning")
    
    # Get or create dataset
    if dataset_id:
        # Use existing dataset
        datasets = rag.list_datasets(id=dataset_id)
        if not datasets:
            raise Exception(f"Dataset with ID '{dataset_id}' not found")
        ds = datasets[0]
        logging.info(f"Using existing dataset: {ds.name} (ID: {ds.id})")
    else:
        # Create new dataset
        dataset_name = f"wiki_upload_{time.strftime('%Y%m%d_%H%M%S')}"
        ds = rag.create_dataset(name=dataset_name)
        dataset_id = ds.id
        logging.info(f"Created new dataset: {ds.name} (ID: {ds.id})")
    
    # Count total documents first
    total_documents, file_doc_counts = count_total_documents(file_list)
    logging.info(f"Total documents to import: {total_documents}")
    logging.info("-" * 60)
    
    batch_add_docs = []
    current_file_name = None
    current_doc_index = 0
    
    # Helper function to upload and parse a batch
    def upload_and_parse_batch(batch, is_final=False):
        """Upload a batch of documents and parse them."""
        nonlocal total_processed_docs, files_processed, current_file_name, current_doc_index
        
        if not batch:
            return
        
        batch_type = "final" if is_final else "batch"
        logging.info(f"  Uploading {batch_type} of {len(batch)} documents...")
        docs = ds.upload_documents_with_meta(batch, file_extension="txt")
        total_processed_docs += len(docs)
        logging.info(f"  Progress: {total_processed_docs}/{total_documents} documents processed, {files_processed}/{len(file_list)} files completed")
        
        # Save snapshot after successful upload
        if current_file_name:
            save_snapshot(args.snapshot_file, current_file_name, current_doc_index, total_processed_docs, dataset_id)
    
    # Wrap upload_and_parse_batch with retry logic
    upload_and_parse_batch_with_retry = retry_with_backoff(upload_and_parse_batch, max_retries=10, max_backoff=8)
    
    # Process each file
    for file_path in file_list:
        file_name = os.path.basename(file_path)
        expected_docs_in_file = file_doc_counts.get(file_path, 0)
        current_file_docs_processed = 0
        current_file_name = file_name
        
        # Skip files before resume point
        if resume_file_name and file_name < resume_file_name:
            logging.info(f"\n⏭️  Skipping file (already processed): {file_name}")
            continue
        
        # Determine starting index for this file
        start_index = 0
        if resume_file_name and file_name == resume_file_name:
            start_index = resume_doc_index
            logging.info(f"\n▶️  Resuming file: {file_name} from document index {start_index} (expected {expected_docs_in_file} documents)")
        else:
            logging.info(f"\nProcessing file: {file_name} (expected {expected_docs_in_file} documents)")
        
        try:
            json_list = read_json_file(file_path)
            
            # Process each JSON object in the file
            for doc_idx, json_obj in enumerate(json_list):
                # Skip documents before resume point
                if doc_idx < start_index:
                    continue
                
                current_doc_index = doc_idx + 1  # Track progress (1-based for readability)
                
                # Prepare document data
                doc_data = {
                    "title": json_obj["title"],
                    "content": json_obj["text"],
                    "metadata": {
                        "doc_id": json_obj["id"],
                        "tags": [item.strip() for item in json_obj["tags"].split(",") if item.strip()]
                    }
                }
                batch_add_docs.append(doc_data)
                current_file_docs_processed += 1
                
                # Upload batch when it reaches batch_size
                if len(batch_add_docs) == args.batch_size:
                    upload_and_parse_batch_with_retry(batch_add_docs)
                    batch_add_docs = []
            
            # Process remaining documents in current file if any
            if batch_add_docs:
                upload_and_parse_batch_with_retry(batch_add_docs)
                batch_add_docs = []
            
            # Mark file as completed
            files_processed += 1
            logging.info(f"  File {file_name} completed: {current_file_docs_processed}/{expected_docs_in_file} documents")
        
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            # If error occurred, still try to process any accumulated batch
            if batch_add_docs:
                upload_and_parse_batch_with_retry(batch_add_docs)
                batch_add_docs = []
            continue
    
    # Process any remaining documents in the final batch (should not happen, but just in case)
    if batch_add_docs:
        upload_and_parse_batch_with_retry(batch_add_docs, is_final=True)
    
    logging.info("\n" + "=" * 60)
    logging.info(f"✅ All done! Total documents processed: {total_processed_docs}/{total_documents}")
    logging.info(f"✅ Total files processed: {files_processed}/{len(file_list)}")
    
    # Clean up snapshot file on successful completion
    if os.path.exists(args.snapshot_file):
        os.remove(args.snapshot_file)
        logging.info(f"🧹 Snapshot file removed: {args.snapshot_file}")


if __name__ == "__main__":
    main()

