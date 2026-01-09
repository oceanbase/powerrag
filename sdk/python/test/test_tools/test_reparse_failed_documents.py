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

import pytest
from unittest.mock import Mock, MagicMock, patch, call

from ragflow_sdk.tools import FailedDocumentReparser


class TestFailedDocumentReparser:
    """Unit tests for FailedDocumentReparser with mocked PowerRAG interfaces."""
    
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
        
        # Mock async_parse_documents
        dataset.async_parse_documents = Mock()
        
        # Mock list_documents to return empty list by default
        dataset.list_documents = Mock(return_value=[])
        
        return dataset
    
    def test_init(self, mock_rag):
        """Test FailedDocumentReparser initialization."""
        reparser = FailedDocumentReparser(mock_rag)
        assert reparser.rag == mock_rag
        assert reparser.dataset is None
    
    def test_init_with_dataset(self, mock_rag, mock_dataset):
        """Test FailedDocumentReparser initialization with dataset."""
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        assert reparser.rag == mock_rag
        assert reparser.dataset == mock_dataset
    
    def test_set_dataset(self, mock_rag, mock_dataset):
        """Test set_dataset method."""
        reparser = FailedDocumentReparser(mock_rag)
        reparser.set_dataset(mock_dataset)
        assert reparser.dataset == mock_dataset
    
    def test_get_dataset(self, mock_rag, mock_dataset):
        """Test get_dataset method."""
        mock_rag.list_datasets = Mock(return_value=[mock_dataset])
        
        reparser = FailedDocumentReparser(mock_rag)
        dataset = reparser.get_dataset("test_dataset_id")
        
        assert dataset == mock_dataset
        assert reparser.dataset == mock_dataset
        mock_rag.list_datasets.assert_called_once_with(id="test_dataset_id")
    
    def test_get_dataset_not_found(self, mock_rag):
        """Test get_dataset when dataset is not found."""
        mock_rag.list_datasets = Mock(return_value=[])
        
        reparser = FailedDocumentReparser(mock_rag)
        
        with pytest.raises(Exception) as excinfo:
            reparser.get_dataset("non_existent_id")
        
        assert "Dataset with ID 'non_existent_id' not found" in str(excinfo.value)
    
    def test_reparse_failed_documents_no_failed(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents when there are no failed documents."""
        # Mock documents with all successful
        mock_doc1 = Mock()
        mock_doc1.id = "doc1"
        mock_doc1.run = "DONE"
        
        mock_doc2 = Mock()
        mock_doc2.id = "doc2"
        mock_doc2.run = "DONE"
        
        mock_dataset.list_documents = Mock(return_value=[mock_doc1, mock_doc2])
        
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        total_failed, total_reparsed = reparser.reparse_failed_documents()
        
        assert total_failed == 0
        assert total_reparsed == 0
        assert not mock_dataset.async_parse_documents.called
    
    def test_reparse_failed_documents_with_failed(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with failed documents."""
        # Mock documents: some failed, some successful
        mock_doc1 = Mock()
        mock_doc1.id = "doc1"
        mock_doc1.run = "FAIL"
        
        mock_doc2 = Mock()
        mock_doc2.id = "doc2"
        mock_doc2.run = "DONE"
        
        mock_doc3 = Mock()
        mock_doc3.id = "doc3"
        mock_doc3.run = "FAIL"
        
        mock_dataset.list_documents = Mock(return_value=[mock_doc1, mock_doc2, mock_doc3])
        
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        total_failed, total_reparsed = reparser.reparse_failed_documents(reparse_batch_size=2)
        
        assert total_failed == 2
        assert total_reparsed == 2
        # Should be called once with batch of 2 failed documents
        mock_dataset.async_parse_documents.assert_called_once_with(["doc1", "doc3"])
    
    def test_reparse_failed_documents_batch_processing(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with batch processing."""
        # Create 5 failed documents
        failed_docs = []
        for i in range(5):
            mock_doc = Mock()
            mock_doc.id = f"doc{i}"
            mock_doc.run = "FAIL"
            failed_docs.append(mock_doc)
        
        mock_dataset.list_documents = Mock(return_value=failed_docs)
        
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        total_failed, total_reparsed = reparser.reparse_failed_documents(reparse_batch_size=2)
        
        assert total_failed == 5
        assert total_reparsed == 5
        # Should be called 3 times: 2 batches of 2, then 1 batch of 1
        assert mock_dataset.async_parse_documents.call_count == 3
        # Check batch contents
        calls = mock_dataset.async_parse_documents.call_args_list
        assert calls[0][0][0] == ["doc0", "doc1"]
        assert calls[1][0][0] == ["doc2", "doc3"]
        assert calls[2][0][0] == ["doc4"]
    
    def test_reparse_failed_documents_pagination(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with pagination."""
        # First page: 2 failed documents
        page1_docs = []
        for i in range(2):
            mock_doc = Mock()
            mock_doc.id = f"doc{i}"
            mock_doc.run = "FAIL"
            page1_docs.append(mock_doc)
        
        # Second page: 1 failed document
        page2_docs = []
        mock_doc = Mock()
        mock_doc.id = "doc2"
        mock_doc.run = "FAIL"
        page2_docs.append(mock_doc)
        
        # Third page: empty (end of pagination)
        page3_docs = []
        
        mock_dataset.list_documents = Mock(side_effect=[page1_docs, page2_docs, page3_docs])
        
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        total_failed, total_reparsed = reparser.reparse_failed_documents(page_size=2)
        
        assert total_failed == 3
        assert total_reparsed == 3
        # Should fetch 2 pages:
        # - page 1 returns a full page (2 docs)
        # - page 2 returns a partial page (1 doc) and the implementation stops
        assert mock_dataset.list_documents.call_count == 2
        # Check pagination parameters
        calls = mock_dataset.list_documents.call_args_list
        assert calls[0] == call(page=1, page_size=2, orderby="id", desc=False)
        assert calls[1] == call(page=2, page_size=2, orderby="id", desc=False)
    
    def test_reparse_failed_documents_with_dataset_id(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with dataset_id parameter."""
        mock_rag.list_datasets = Mock(return_value=[mock_dataset])
        
        # Mock documents with failed ones
        mock_doc = Mock()
        mock_doc.id = "doc1"
        mock_doc.run = "FAIL"
        mock_dataset.list_documents = Mock(return_value=[mock_doc])
        
        reparser = FailedDocumentReparser(mock_rag)
        total_failed, total_reparsed = reparser.reparse_failed_documents(dataset_id="test_dataset_id")
        
        assert total_failed == 1
        assert total_reparsed == 1
        mock_rag.list_datasets.assert_called_once_with(id="test_dataset_id")
        mock_dataset.async_parse_documents.assert_called_once_with(["doc1"])
    
    def test_reparse_failed_documents_no_dataset_error(self, mock_rag):
        """Test reparse_failed_documents raises error when no dataset is set."""
        reparser = FailedDocumentReparser(mock_rag)
        
        with pytest.raises(ValueError) as excinfo:
            reparser.reparse_failed_documents()
        
        assert "Either dataset must be set or dataset_id must be provided" in str(excinfo.value)
    
    def test_reparse_failed_documents_invalid_batch_size(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with invalid reparse_batch_size."""
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        
        with pytest.raises(ValueError) as excinfo:
            reparser.reparse_failed_documents(reparse_batch_size=0)
        
        assert "reparse_batch_size must be greater than 0" in str(excinfo.value)
        
        with pytest.raises(ValueError) as excinfo:
            reparser.reparse_failed_documents(reparse_batch_size=-1)
        
        assert "reparse_batch_size must be greater than 0" in str(excinfo.value)
    
    def test_reparse_failed_documents_invalid_page_size(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with invalid page_size."""
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        
        with pytest.raises(ValueError) as excinfo:
            reparser.reparse_failed_documents(page_size=0)
        
        assert "page_size must be greater than 0" in str(excinfo.value)
        
        with pytest.raises(ValueError) as excinfo:
            reparser.reparse_failed_documents(page_size=-1)
        
        assert "page_size must be greater than 0" in str(excinfo.value)
    
    def test_reparse_failed_documents_case_insensitive_fail(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents handles case-insensitive FAIL status."""
        # Test different case variations
        test_cases = ["fail", "FAIL", "Fail", "fAiL"]
        
        for run_status in test_cases:
            mock_dataset.async_parse_documents.reset_mock()
            
            mock_doc = Mock()
            mock_doc.id = "doc1"
            mock_doc.run = run_status
            mock_dataset.list_documents = Mock(return_value=[mock_doc])
            
            reparser = FailedDocumentReparser(mock_rag, mock_dataset)
            total_failed, total_reparsed = reparser.reparse_failed_documents()
            
            assert total_failed == 1
            assert total_reparsed == 1
            mock_dataset.async_parse_documents.assert_called_once_with(["doc1"])
    
    def test_reparse_failed_documents_retry_on_error(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents retries on error."""
        mock_doc = Mock()
        mock_doc.id = "doc1"
        mock_doc.run = "FAIL"
        mock_dataset.list_documents = Mock(return_value=[mock_doc])
        
        # First call raises exception, second call succeeds
        mock_dataset.async_parse_documents = Mock(side_effect=[Exception("Network error"), None])
        
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        
        # Should retry and eventually succeed
        total_failed, total_reparsed = reparser.reparse_failed_documents(reparse_batch_size=1)
        
        assert total_failed == 1
        assert total_reparsed == 1
        # Should be called twice (initial + retry)
        assert mock_dataset.async_parse_documents.call_count == 2
    
    def test_reparse_failed_documents_mixed_status(self, mock_rag, mock_dataset):
        """Test reparse_failed_documents with mixed document statuses."""
        # Create documents with various statuses
        mock_doc_fail = Mock()
        mock_doc_fail.id = "doc_fail"
        mock_doc_fail.run = "FAIL"
        
        mock_doc_done = Mock()
        mock_doc_done.id = "doc_done"
        mock_doc_done.run = "DONE"
        
        mock_doc_cancel = Mock()
        mock_doc_cancel.id = "doc_cancel"
        mock_doc_cancel.run = "CANCEL"
        
        mock_doc_fail2 = Mock()
        mock_doc_fail2.id = "doc_fail2"
        mock_doc_fail2.run = "FAIL"
        
        mock_dataset.list_documents = Mock(return_value=[
            mock_doc_fail, mock_doc_done, mock_doc_cancel, mock_doc_fail2
        ])
        
        reparser = FailedDocumentReparser(mock_rag, mock_dataset)
        total_failed, total_reparsed = reparser.reparse_failed_documents()
        
        assert total_failed == 2
        assert total_reparsed == 2
        # Should only reparse failed documents
        mock_dataset.async_parse_documents.assert_called_once_with(["doc_fail", "doc_fail2"])
    
    def test_retry_with_backoff(self, mock_rag):
        """Test retry_with_backoff static method."""
        call_count = [0]
        
        def failing_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Test error")
            return "success"
        
        wrapped_func = FailedDocumentReparser.retry_with_backoff(failing_func, max_retries=5, max_backoff=1)
        result = wrapped_func()
        
        assert result == "success"
        assert call_count[0] == 3
    
    def test_retry_with_backoff_max_retries(self, mock_rag):
        """Test retry_with_backoff exhausts max retries."""
        call_count = [0]
        
        def always_failing_func():
            call_count[0] += 1
            raise Exception("Test error")
        
        wrapped_func = FailedDocumentReparser.retry_with_backoff(always_failing_func, max_retries=3, max_backoff=0.01)
        
        with pytest.raises(Exception) as excinfo:
            wrapped_func()
        
        assert "Test error" in str(excinfo.value)
        assert call_count[0] == 3

