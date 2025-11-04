#!/usr/bin/env python3
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
PowerRAG Pipeline Component Example

This example shows how to use PowerRAG components in the RAGFlow pipeline.
"""

import sys
import asyncio
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MockCanvas:
    """Mock canvas for testing pipeline components"""
    
    def __init__(self):
        self.callback_calls = []
    
    def callback(self, component_id, progress, message=""):
        self.callback_calls.append((component_id, progress, message))
        print(f"Component {component_id}: {progress*100:.1f}% - {message}")


async def example_1_pipeline_parser():
    """Example 1: Using PowerRAG parser in pipeline"""
    print("=== Example 1: PowerRAG Parser in Pipeline ===")
    
    try:
        from powerrag.parsers.pipeline_parsers import AdvancedPDFParser, AdvancedPDFParserParam
        
        # Create mock canvas and parameters
        canvas = MockCanvas()
        param = AdvancedPDFParserParam()
        param.extract_tables = True
        param.extract_images = False
        
        # Create parser component
        parser = AdvancedPDFParser(canvas, "test_parser", param)
        
        print(f"✓ Parser created: {parser.name}")
        print(f"✓ Component type: {parser.component_type.value}")
        print(f"✓ Enabled: {parser.is_enabled()}")
        
        # Test parser with mock data
        result = await parser.invoke(
            filename="test.pdf",
            binary=b"dummy pdf content",
            from_page=0,
            to_page=10
        )
        
        print(f"✓ Parser result: {result}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


async def example_2_pipeline_extractor():
    """Example 2: Using PowerRAG extractor in pipeline"""
    print("\n=== Example 2: PowerRAG Extractor in Pipeline ===")
    
    try:
        from powerrag.extractors.pipeline_extractors import EntityExtractor, EntityExtractorParam
        
        # Create mock canvas and parameters
        canvas = MockCanvas()
        param = EntityExtractorParam()
        param.entity_types = ["PERSON", "ORG", "GPE"]
        param.confidence_threshold = 0.7
        
        # Create extractor component
        extractor = EntityExtractor(canvas, "test_extractor", param)
        
        print(f"✓ Extractor created: {extractor.name}")
        print(f"✓ Component type: {extractor.component_type.value}")
        
        # Test extractor
        result = await extractor.invoke(
            text="John Smith works at Microsoft Corporation in Seattle."
        )
        
        print(f"✓ Extractor result: {result}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


async def example_3_pipeline_splitter():
    """Example 3: Using PowerRAG splitter in pipeline"""
    print("\n=== Example 3: PowerRAG Splitter in Pipeline ===")
    
    try:
        from powerrag.splitters.pipeline_splitters import AdaptiveSplitter, AdaptiveSplitterParam
        
        # Create mock canvas and parameters
        canvas = MockCanvas()
        param = AdaptiveSplitterParam()
        param.chunk_size = 1000
        param.chunk_overlap = 200
        
        # Create splitter component
        splitter = AdaptiveSplitter(canvas, "test_splitter", param)
        
        print(f"✓ Splitter created: {splitter.name}")
        print(f"✓ Component type: {splitter.component_type.value}")
        
        # Test splitter
        long_text = "This is a long text that needs to be split into chunks. " * 20
        result = await splitter.invoke(text=long_text)
        
        print(f"✓ Splitter result: {result}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def example_4_component_registration():
    """Example 4: Register PowerRAG components for pipeline use"""
    print("\n=== Example 4: Component Registration ===")
    
    try:
        from powerrag.parsers.pipeline_parsers import AdvancedPDFParser, AdvancedPDFParserParam
        from powerrag.extractors.pipeline_extractors import EntityExtractor, EntityExtractorParam
        from powerrag.splitters.pipeline_splitters import AdaptiveSplitter, AdaptiveSplitterParam
        
        print("PowerRAG Pipeline Components Available:")
        print(f"  - Parser: {AdvancedPDFParser.__name__}")
        print(f"  - Extractor: {EntityExtractor.__name__}")
        print(f"  - Splitter: {AdaptiveSplitter.__name__}")
        
        print("\nTo register these components in the RAGFlow pipeline:")
        print("1. Add component classes to agent/component/__init__.py")
        print("2. Add parameter classes to the component registration")
        print("3. Update web UI to include PowerRAG components in pipeline builder")
        
        print("\nExample registration in agent/component/__init__.py:")
        print("```python")
        print("from powerrag.parsers.pipeline_parsers import AdvancedPDFParser, AdvancedPDFParserParam")
        print("from powerrag.extractors.pipeline_extractors import EntityExtractor, EntityExtractorParam")
        print("from powerrag.splitters.pipeline_splitters import AdaptiveSplitter, AdaptiveSplitterParam")
        print("```")
        
    except Exception as e:
        print(f"✗ Error: {e}")


def example_5_integration_guide():
    """Example 5: Integration guide for existing pipeline"""
    print("\n=== Example 5: Integration Guide ===")
    
    print("To integrate PowerRAG components into existing RAGFlow pipeline:")
    print()
    print("1. **Component Registration**:")
    print("   - Add PowerRAG component classes to agent/component/")
    print("   - Register them in the component system")
    print("   - Update web UI to show PowerRAG components")
    print()
    print("2. **Pipeline Usage**:")
    print("   - Users can drag PowerRAG components into pipeline builder")
    print("   - Configure component parameters through UI")
    print("   - Components will be executed as part of the pipeline")
    print()
    print("3. **Configuration**:")
    print("   - Each component has its own parameter class")
    print("   - Parameters can be configured through the UI")
    print("   - Components support validation and error handling")
    print()
    print("4. **Benefits**:")
    print("   ✓ Native pipeline integration")
    print("   ✓ UI-based configuration")
    print("   ✓ Standard error handling and logging")
    print("   ✓ Compatible with existing pipeline features")


async def main():
    """Run all examples"""
    print("PowerRAG Pipeline Component Examples")
    print("=" * 60)
    
    try:
        await example_1_pipeline_parser()
        await example_2_pipeline_extractor()
        await example_3_pipeline_splitter()
        example_4_component_registration()
        example_5_integration_guide()
        
        print("\n" + "=" * 60)
        print("🎉 All pipeline examples completed successfully!")
        print("\nPowerRAG components are ready for pipeline integration!")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
