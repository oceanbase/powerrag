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
PowerRAG SDK

A Python SDK for PowerRAG API, providing easy-to-use interfaces for knowledge base management,
document processing, chunking, extraction, RAPTOR, knowledge graph, and retrieval.
"""

from .client import PowerRAGClient

__all__ = ["PowerRAGClient"]

# Alias for convenience
PowerRAG = PowerRAGClient