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
import tempfile
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

from ragflow_sdk.tools import BatchUploader, DocumentExtractor, FieldMapper
from ragflow_sdk.tools.models import Snapshot, FileCursor


class TestBatchUploader:
    """Unit tests for BatchUploader with mocked PowerRAG interfaces."""
    
    @pytest.fixture
    def mock_rag(self):
        """Create a mock RAGFlow client."""
        rag = Mock()
        rag.api_url = "http://test.com/api/v1"
        rag.user_key = "test_key"
        return rag
    
    @pytest.fixture
    def mock_dataset(self, mock_rag):
        """Create a mock DataSet."""
        dataset = Mock()
        dataset.id = "test_dataset_id"
        dataset.name = "test_dataset"
        dataset.rag = mock_rag
        
        # Mock upload_documents_with_meta to return mock documents
        def mock_upload(docs, group_id_field=None, file_extension="txt"):
            mock_docs = []
            for i, doc in enumerate(docs):
                mock_doc = Mock()
                mock_doc.id = f"doc_{i}"
                mock_doc.title = doc.get("title", "")
                mock_doc.content = doc.get("content", "")
                mock_docs.append(mock_doc)
            return mock_docs
        
        dataset.upload_documents_with_meta = Mock(side_effect=mock_upload)
        return dataset
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def _create_json_file(self, temp_dir, filename, data):
        """Helper to create a JSON file."""
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return filepath
    
    def _create_jsonl_file(self, temp_dir, filename, data_list):
        """Helper to create a JSONL file."""
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data_list:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        return filepath
    
    def _create_csv_file(self, temp_dir, filename, rows):
        """Helper to create a CSV file."""
        import csv
        filepath = os.path.join(temp_dir, filename)
        if rows:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        else:
            # Create empty CSV with header
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['title', 'content'])
                writer.writeheader()
        return filepath
    
    def _create_text_file(self, temp_dir, filename, content):
        """Helper to create a text file."""
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    @pytest.mark.parametrize("extension,create_func,test_data", [
        # Multi-doc formats - all extensions must be covered
        ("json", "_create_json_file", [
            {"title": "Doc 1", "content": "Content 1", "id": "1"},
            {"title": "Doc 2", "content": "Content 2", "id": "2"},
            {"title": "Doc 3", "content": "Content 3", "id": "3"}
        ]),
        ("jsonl", "_create_jsonl_file", [
            {"title": "Doc 1", "content": "Content 1", "id": "1"},
            {"title": "Doc 2", "content": "Content 2", "id": "2"},
            {"title": "Doc 3", "content": "Content 3", "id": "3"}
        ]),
        ("csv", "_create_csv_file", [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": "Content 2"},
            {"title": "Doc 3", "content": "Content 3"}
        ]),
    ])
    def test_upload_multi_doc_formats(self, mock_rag, mock_dataset, temp_dir, extension, create_func, test_data):
        """Test uploading multi-document formats (json, jsonl, csv, xlsx, xls)."""
        # Create test file
        filename = f"test.{extension}"
        create_method = getattr(self, create_func)
        filepath = create_method(temp_dir, filename, test_data)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(multi_doc_extensions=["json", "jsonl", "csv", "xlsx", "xls"])
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=2,
            file_extension="txt"
        )
        
        # Verify upload was called
        assert mock_dataset.upload_documents_with_meta.called
        assert total_docs == len(test_data)
        assert total_files == 1
        
        # Verify uploaded documents
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        assert len(all_uploaded_docs) == len(test_data)
        for i, doc in enumerate(all_uploaded_docs):
            assert doc["title"] == test_data[i].get("title", "")
            assert doc["content"] == test_data[i].get("content", "")
    
    @pytest.mark.parametrize("extension", ["xlsx", "xls"])
    def test_upload_excel_formats(self, mock_rag, mock_dataset, temp_dir, extension):
        """Test uploading Excel formats (xlsx, xls)."""
        pytest.importorskip("pandas")
        
        import pandas as pd
        
        # Create test Excel file
        filename = f"test.{extension}"
        filepath = os.path.join(temp_dir, filename)
        test_data = [
            {"title": "Doc 1", "content": "Content 1"},
            {"title": "Doc 2", "content": "Content 2"},
            {"title": "Doc 3", "content": "Content 3"}
        ]
        
        if extension == 'xlsx':
            # Use pandas with openpyxl for xlsx
            df = pd.DataFrame(test_data)
            df.to_excel(filepath, index=False, engine='openpyxl')
        else:
            # For xls, use xlwt directly (pandas 2.0+ doesn't support xlwt writer)
            try:
                import xlwt
                workbook = xlwt.Workbook()
                worksheet = workbook.add_sheet('Sheet1')
                
                # Write header
                headers = list(test_data[0].keys())
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header)
                
                # Write data rows
                for row, data in enumerate(test_data, start=1):
                    for col, header in enumerate(headers):
                        worksheet.write(row, col, data[header])
                
                workbook.save(filepath)
            except ImportError:
                pytest.skip("xlwt is not installed")
        
        # Create uploader and extractor with xlsx/xls as multi-doc format
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(multi_doc_extensions=['json', 'jsonl', 'csv', 'xlsx', 'xls'])
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=2,
            file_extension=extension
        )
        
        # Verify upload was called
        assert mock_dataset.upload_documents_with_meta.called
        assert total_docs == 3
        assert total_files == 1
    
    def _create_excel_file(self, temp_dir, filename, test_data):
        """Helper to create Excel file (xlsx or xls)."""
        pytest.importorskip("pandas")
        import pandas as pd
        
        filepath = os.path.join(temp_dir, filename)
        extension = os.path.splitext(filename)[1].lower()
        
        if extension == '.xlsx':
            df = pd.DataFrame(test_data)
            df.to_excel(filepath, index=False, engine='openpyxl')
        else:  # .xls
            try:
                import xlwt
                workbook = xlwt.Workbook()
                worksheet = workbook.add_sheet('Sheet1')
                
                headers = list(test_data[0].keys())
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header)
                
                for row, data in enumerate(test_data, start=1):
                    for col, header in enumerate(headers):
                        worksheet.write(row, col, data[header])
                
                workbook.save(filepath)
            except ImportError:
                pytest.skip("xlwt is not installed")
        
        return filepath
    
    @pytest.mark.parametrize("extension,batch_size,total_docs,scenario", [
        # Test different batch size scenarios for each format
        ("json", 5, 5, "exact"),      # Exactly batch_size
        ("json", 3, 10, "exceeds"),    # More than batch_size (multiple batches)
        ("json", 10, 3, "less"),       # Less than batch_size
        ("json", 3, 7, "partial"),    # Partial last batch (7 docs, batch_size=3 -> 3 batches)
        ("jsonl", 5, 5, "exact"),
        ("jsonl", 3, 10, "exceeds"),
        ("jsonl", 10, 3, "less"),
        ("jsonl", 3, 7, "partial"),
        ("csv", 5, 5, "exact"),
        ("csv", 3, 10, "exceeds"),
        ("csv", 10, 3, "less"),
        ("csv", 3, 7, "partial"),
        ("xlsx", 5, 5, "exact"),
        ("xlsx", 3, 10, "exceeds"),
        ("xlsx", 10, 3, "less"),
        ("xlsx", 3, 7, "partial"),
        ("xls", 5, 5, "exact"),
        ("xls", 3, 10, "exceeds"),
        ("xls", 10, 3, "less"),
        ("xls", 3, 7, "partial"),
    ])
    def test_single_file_multi_doc_batch_scenarios(self, mock_rag, mock_dataset, temp_dir, 
                                                    extension, batch_size, total_docs, scenario):
        """Test single file with multiple documents across different batch size scenarios.
        
        Covers:
        - exact: document count equals batch_size (single full batch)
        - exceeds: document count exceeds batch_size (multiple batches)
        - less: document count less than batch_size (single partial batch)
        - partial: document count creates partial last batch
        """
        # Create test data
        test_data = [
            {"title": f"Doc {i}", "content": f"Content {i}"} 
            for i in range(total_docs)
        ]
        
        # Create file based on extension
        filename = f"test.{extension}"
        if extension in ["json", "jsonl", "csv"]:
            create_method = getattr(self, f"_create_{extension}_file" if extension != "jsonl" else "_create_jsonl_file")
            filepath = create_method(temp_dir, filename, test_data)
        else:  # xlsx or xls
            filepath = self._create_excel_file(temp_dir, filename, test_data)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(multi_doc_extensions=["json", "jsonl", "csv", "xlsx", "xls"])
        
        # Upload documents
        total_docs_uploaded, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=batch_size,
            file_extension="txt"
        )
        
        # Verify upload was called
        assert mock_dataset.upload_documents_with_meta.called
        assert total_docs_uploaded == total_docs
        assert total_files == 1
        
        # Verify batch count based on scenario
        expected_batch_count = (total_docs + batch_size - 1) // batch_size  # Ceiling division
        assert mock_dataset.upload_documents_with_meta.call_count == expected_batch_count
        
        # Verify all documents were uploaded correctly
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        assert len(all_uploaded_docs) == total_docs
        for i, doc in enumerate(all_uploaded_docs):
            assert doc["title"] == f"Doc {i}"
            assert doc["content"] == f"Content {i}"
        
        # Verify batch sizes (all batches except last should be full)
        for i, call_args in enumerate(call_args_list):
            docs = call_args[0][0]
            if i < len(call_args_list) - 1:
                assert len(docs) == batch_size, f"Batch {i} should be full (size={batch_size})"
            else:
                # Last batch may be smaller
                expected_last_batch_size = total_docs % batch_size
                if expected_last_batch_size == 0:
                    expected_last_batch_size = batch_size
                assert len(docs) == expected_last_batch_size, \
                    f"Last batch should have {expected_last_batch_size} docs, got {len(docs)}"
    
    @pytest.mark.parametrize("extension", ["json", "jsonl", "csv"])
    def test_single_file_large_document_count(self, mock_rag, mock_dataset, temp_dir, extension):
        """Test single file with large number of documents to verify batch processing works correctly."""
        batch_size = 7
        total_docs = 100  # Large number of documents
        
        # Create test data with many documents
        test_data = [
            {"title": f"Doc {i}", "content": f"Content {i}", "id": str(i)} 
            for i in range(total_docs)
        ]
        
        # Create file
        filename = f"large_test.{extension}"
        create_method = getattr(self, f"_create_{extension}_file" if extension != "jsonl" else "_create_jsonl_file")
        filepath = create_method(temp_dir, filename, test_data)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(multi_doc_extensions=["json", "jsonl", "csv", "xlsx", "xls"])
        
        # Upload documents
        total_docs_uploaded, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=batch_size,
            file_extension="txt"
        )
        
        # Verify all documents were uploaded
        assert total_docs_uploaded == total_docs
        assert total_files == 1
        
        # Verify correct number of batches
        expected_batch_count = (total_docs + batch_size - 1) // batch_size
        assert mock_dataset.upload_documents_with_meta.call_count == expected_batch_count
        
        # Verify document order and completeness
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        assert len(all_uploaded_docs) == total_docs
        # Verify first and last documents
        assert all_uploaded_docs[0]["title"] == "Doc 0"
        assert all_uploaded_docs[-1]["title"] == f"Doc {total_docs - 1}"
        # Verify sequential order
        for i, doc in enumerate(all_uploaded_docs):
            assert doc["title"] == f"Doc {i}", f"Document order mismatch at index {i}"
    
    @pytest.mark.parametrize("extension,content", [
        # Single-doc formats - select a few for testing
        ("txt", "This is a test document content."),
        ("md", "# Test Document\n\nThis is markdown content."),
        ("pdf", b"PDF content"),  # Binary content
    ])
    def test_upload_single_doc_formats(self, mock_rag, mock_dataset, temp_dir, extension, content):
        """Test uploading single-document formats."""
        filename = f"test.{extension}"
        filepath = os.path.join(temp_dir, filename)
        
        if isinstance(content, bytes):
            # For binary files like PDF
            with open(filepath, 'wb') as f:
                f.write(content)
        else:
            # For text files
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            file_extension="txt"
        )
        
        # Verify upload was called
        assert mock_dataset.upload_documents_with_meta.called
        assert total_docs == 1
        assert total_files == 1
        
        # Verify uploaded document
        call_args = mock_dataset.upload_documents_with_meta.call_args
        docs = call_args[0][0]
        assert len(docs) == 1
        assert docs[0]["title"] == f"test.{extension}"  # Filename with extension
        if isinstance(content, str):
            assert docs[0]["content"] == content
    
    def test_upload_with_field_mapper(self, mock_rag, mock_dataset, temp_dir):
        """Test uploading with field mapper for multi-doc format."""
        # Create JSON file with custom field names
        test_data = [
            {"name": "Doc 1", "text": "Content 1", "docid": "1", "link": "http://example.com/1", "tag": "tag1,tag2"},
            {"name": "Doc 2", "text": "Content 2", "docid": "2", "link": "http://example.com/2", "tag": "tag3"}
        ]
        filepath = self._create_json_file(temp_dir, "test.json", test_data)
        
        # Create field mapper with custom mappings
        field_mapper = FieldMapper(
            title_field="name",
            content_field="text",
            doc_id_field="docid",
            doc_url_field="link",
            tags_field="tag"
        )
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(field_mapper=field_mapper)
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            file_extension="txt"
        )
        
        # Verify upload was called
        assert mock_dataset.upload_documents_with_meta.called
        assert total_docs == 2
        
        # Verify field mapping
        call_args = mock_dataset.upload_documents_with_meta.call_args
        docs = call_args[0][0]
        assert len(docs) == 2
        assert docs[0]["title"] == "Doc 1"
        assert docs[0]["content"] == "Content 1"
        assert docs[0]["metadata"]["doc_id"] == "1"
        assert docs[0]["metadata"]["doc_url"] == "http://example.com/1"
        assert docs[0]["metadata"]["tags"] == ["tag1", "tag2"]
    
    def test_snapshot_generation_and_resume(self, mock_rag, mock_dataset, temp_dir):
        """Test snapshot generation and resuming from snapshot."""
        # Create JSON file with multiple documents
        test_data = [
            {"title": f"Doc {i}", "content": f"Content {i}"} for i in range(10)
        ]
        filepath = self._create_json_file(temp_dir, "test.json", test_data)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        snapshot_file = os.path.join(temp_dir, "snapshot.json")
        
        # First upload - process all documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            snapshot_file=snapshot_file,
            resume=False,
            file_extension="txt"
        )
        
        # Verify snapshot was created (but will be cleaned up after completion)
        # Since upload completes successfully, snapshot is removed
        # So we verify the upload worked correctly
        assert total_docs == 10
        assert total_files == 1
        
        # Verify all documents were uploaded
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        assert len(all_uploaded_docs) == 10
    
    def test_snapshot_resume_partial_processing(self, mock_rag, mock_dataset, temp_dir):
        """Test resuming from snapshot with partial file processing."""
        # Create JSON file with multiple documents
        test_data = [
            {"title": f"Doc {i}", "content": f"Content {i}"} for i in range(10)
        ]
        filepath = self._create_json_file(temp_dir, "test.json", test_data)
        
        # Manually create a snapshot with partial progress
        snapshot_file = os.path.join(temp_dir, "snapshot.json")
        file_cursors = [FileCursor(file_path=filepath, doc_index=5)]
        BatchUploader.save_snapshot(snapshot_file, file_cursors, total_processed=5, dataset_id="test_dataset_id")
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        # Resume from snapshot
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=3,
            snapshot_file=snapshot_file,
            resume=True,
            file_extension="txt"
        )
        
        # Verify that remaining documents were uploaded
        # Should process documents starting from index 5
        assert mock_dataset.upload_documents_with_meta.called
        
        # Check that documents were resumed from index 5
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        # Should have uploaded remaining 5 documents (indices 5-9)
        assert len(all_uploaded_docs) == 5
        assert all_uploaded_docs[0]["title"] == "Doc 5"
        assert all_uploaded_docs[-1]["title"] == "Doc 9"
    
    @pytest.mark.parametrize("multi_doc_extensions,file_extension,expected_multi_doc", [
        # Test multi_doc_extensions configuration
        (["json", "jsonl", "csv"], "json", True),
        (["json", "jsonl", "csv"], "jsonl", True),
        (["json", "jsonl", "csv"], "csv", True),
        (["json", "jsonl", "csv"], "txt", False),  # txt not in multi_doc_extensions
        (["json"], "csv", False),  # csv not in multi_doc_extensions when only json is specified
        ([], "json", False),  # Empty list means all are single-doc
    ])
    def test_multi_doc_extensions_config(self, mock_rag, mock_dataset, temp_dir, 
                                         multi_doc_extensions, file_extension, expected_multi_doc):
        """Test that multi_doc_extensions configuration is respected."""
        # Create test file based on extension
        filename = f"test.{file_extension}"
        
        if file_extension == "json":
            test_data = [
                {"title": "Doc 1", "content": "Content 1"},
                {"title": "Doc 2", "content": "Content 2"}
            ]
            filepath = self._create_json_file(temp_dir, filename, test_data)
        elif file_extension == "jsonl":
            test_data = [
                {"title": "Doc 1", "content": "Content 1"},
                {"title": "Doc 2", "content": "Content 2"}
            ]
            filepath = self._create_jsonl_file(temp_dir, filename, test_data)
        elif file_extension == "csv":
            test_data = [
                {"title": "Doc 1", "content": "Content 1"},
                {"title": "Doc 2", "content": "Content 2"}
            ]
            filepath = self._create_csv_file(temp_dir, filename, test_data)
        else:  # txt or other single-doc format
            filepath = self._create_text_file(temp_dir, filename, "Single document content")
        
        # Create extractor with custom multi_doc_extensions
        extractor = DocumentExtractor(multi_doc_extensions=multi_doc_extensions)
        
        # Verify file type detection
        is_multi = extractor.file_reader.is_multi_document_format(filepath)
        assert is_multi == expected_multi_doc, \
            f"Expected {file_extension} to be {'multi-doc' if expected_multi_doc else 'single-doc'} " \
            f"with multi_doc_extensions={multi_doc_extensions}, but got {is_multi}"
        
        # Create uploader
        uploader = BatchUploader(mock_rag, mock_dataset)
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            file_extension="txt"
        )
        
        # Verify upload was called
        assert mock_dataset.upload_documents_with_meta.called
        
        if expected_multi_doc:
            # Multi-doc files should yield multiple documents
            assert total_docs >= 1
        else:
            # Single-doc files should yield exactly 1 document
            assert total_docs == 1
    
    def test_batch_upload_with_field_mapper_snapshot(self, mock_rag, mock_dataset, temp_dir):
        """Test batch upload with field mapper and snapshot for multi-doc format."""
        # Create JSON file with custom fields
        test_data = [
            {"name": f"Doc {i}", "text": f"Content {i}", "id": str(i)} 
            for i in range(8)
        ]
        filepath = self._create_json_file(temp_dir, "test.json", test_data)
        
        # Create field mapper
        field_mapper = FieldMapper(
            title_field="name",
            content_field="text",
            doc_id_field="id"
        )
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(field_mapper=field_mapper)
        
        snapshot_file = os.path.join(temp_dir, "snapshot.json")
        
        # Upload with batch_size=3 to create multiple batches
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=3,
            snapshot_file=snapshot_file,
            resume=False,
            file_extension="txt"
        )
        
        # Verify all documents were uploaded
        assert total_docs == 8
        assert total_files == 1
        
        # Verify field mapping was applied
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        assert len(all_uploaded_docs) == 8
        for i, doc in enumerate(all_uploaded_docs):
            assert doc["title"] == f"Doc {i}"
            assert doc["content"] == f"Content {i}"
            assert doc["metadata"]["doc_id"] == str(i)
        
        # Note: snapshot file is cleaned up after successful completion
        # This is expected behavior - snapshot is only kept for resume scenarios
    
    def test_snapshot_resume_with_field_mapper(self, mock_rag, mock_dataset, temp_dir):
        """Test resuming from snapshot with field mapper for multi-doc format."""
        # Create JSON file with custom fields
        test_data = [
            {"name": f"Doc {i}", "text": f"Content {i}", "id": str(i)} 
            for i in range(10)
        ]
        filepath = self._create_json_file(temp_dir, "test.json", test_data)
        
        # Create field mapper
        field_mapper = FieldMapper(
            title_field="name",
            content_field="text",
            doc_id_field="id"
        )
        
        # Manually create snapshot with partial progress
        snapshot_file = os.path.join(temp_dir, "snapshot.json")
        file_cursors = [FileCursor(file_path=filepath, doc_index=4)]
        BatchUploader.save_snapshot(snapshot_file, file_cursors, total_processed=4, dataset_id="test_dataset_id")
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor(field_mapper=field_mapper)
        
        # Resume from snapshot
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=3,
            snapshot_file=snapshot_file,
            resume=True,
            file_extension="txt"
        )
        
        # Verify remaining documents were uploaded with field mapping
        assert mock_dataset.upload_documents_with_meta.called
        
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        # Should have uploaded remaining 6 documents (indices 4-9)
        assert len(all_uploaded_docs) == 6
        assert all_uploaded_docs[0]["title"] == "Doc 4"
        assert all_uploaded_docs[0]["metadata"]["doc_id"] == "4"
        assert all_uploaded_docs[-1]["title"] == "Doc 9"
        assert all_uploaded_docs[-1]["metadata"]["doc_id"] == "9"
    
    def test_upload_empty_file(self, mock_rag, mock_dataset, temp_dir):
        """Test uploading empty file."""
        # Create empty JSON file
        filepath = self._create_json_file(temp_dir, "empty.json", [])
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            file_extension="txt"
        )
        
        # Empty file should result in 0 documents
        assert total_docs == 0
        # File was processed but had no documents, so no cursor is created
        # fully_processed_files counts files with cursor > 0, so should be 0
        assert total_files == 0
    
    def test_upload_multiple_files(self, mock_rag, mock_dataset, temp_dir):
        """Test uploading multiple files."""
        # Create multiple JSON files
        for i in range(3):
            test_data = [
                {"title": f"Doc {i}-{j}", "content": f"Content {i}-{j}"} 
                for j in range(2)
            ]
            self._create_json_file(temp_dir, f"test_{i}.json", test_data)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        # Upload documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            file_extension="txt"
        )
        
        # Verify all files were processed
        assert total_docs == 6  # 3 files * 2 docs each
        assert total_files == 3
        
        # Verify all documents were uploaded
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        assert len(all_uploaded_docs) == 6
    
    def test_snapshot_single_doc_file(self, mock_rag, mock_dataset, temp_dir):
        """Test snapshot with single-document file."""
        # Create a single-doc text file
        filepath = self._create_text_file(temp_dir, "test.txt", "Single document content")
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        snapshot_file = os.path.join(temp_dir, "snapshot.json")
        
        # Upload document
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            snapshot_file=snapshot_file,
            resume=False,
            file_extension="txt"
        )
        
        # Verify upload
        assert total_docs == 1
        assert total_files == 1
        
        # Manually create snapshot to test resume
        file_cursors = [FileCursor(file_path=filepath, doc_index=1)]
        BatchUploader.save_snapshot(snapshot_file, file_cursors, total_processed=1, dataset_id="test_dataset_id")
        
        # Reset mock
        mock_dataset.upload_documents_with_meta.reset_mock()
        
        # Resume from snapshot - single-doc file should be skipped
        total_docs_resume, total_files_resume = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=5,
            snapshot_file=snapshot_file,
            resume=True,
            file_extension="txt"
        )
        
        # Single-doc file with doc_index > 0 should be skipped
        # So no new uploads should occur
        assert not mock_dataset.upload_documents_with_meta.called or total_docs_resume == 0
    
    def test_snapshot_mixed_files(self, mock_rag, mock_dataset, temp_dir):
        """Test snapshot with mixed single-doc and multi-doc files."""
        # Create a single-doc file
        txt_file = self._create_text_file(temp_dir, "test.txt", "Single doc content")
        
        # Create a multi-doc JSON file
        json_data = [
            {"title": f"Doc {i}", "content": f"Content {i}"} for i in range(5)
        ]
        json_file = self._create_json_file(temp_dir, "test.json", json_data)
        
        # Create uploader and extractor
        uploader = BatchUploader(mock_rag, mock_dataset)
        extractor = DocumentExtractor()
        
        snapshot_file = os.path.join(temp_dir, "snapshot.json")
        
        # Upload all documents
        total_docs, total_files = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=3,
            snapshot_file=snapshot_file,
            resume=False,
            file_extension="txt"
        )
        
        # Verify upload
        assert total_docs == 6  # 1 single-doc + 5 multi-doc
        assert total_files == 2
        
        # Create partial snapshot: txt file processed, json file partially processed
        file_cursors = [
            FileCursor(file_path=txt_file, doc_index=1),  # Single-doc: processed
            FileCursor(file_path=json_file, doc_index=3)   # Multi-doc: 3 of 5 processed
        ]
        BatchUploader.save_snapshot(snapshot_file, file_cursors, total_processed=4, dataset_id="test_dataset_id")
        
        # Reset mock
        mock_dataset.upload_documents_with_meta.reset_mock()
        
        # Resume from snapshot
        total_docs_resume, total_files_resume = uploader.upload(
            document_extractor=extractor,
            data_dir=temp_dir,
            dataset_id="test_dataset_id",
            batch_size=3,
            snapshot_file=snapshot_file,
            resume=True,
            file_extension="txt"
        )
        
        # Should resume json file from index 3, skip txt file
        assert mock_dataset.upload_documents_with_meta.called
        
        # Verify remaining 2 documents from json file were uploaded
        call_args_list = mock_dataset.upload_documents_with_meta.call_args_list
        all_uploaded_docs = []
        for call_args in call_args_list:
            docs = call_args[0][0]
            all_uploaded_docs.extend(docs)
        
        assert len(all_uploaded_docs) == 2  # Remaining 2 docs from json file
        assert all_uploaded_docs[0]["title"] == "Doc 3"
        assert all_uploaded_docs[1]["title"] == "Doc 4"

