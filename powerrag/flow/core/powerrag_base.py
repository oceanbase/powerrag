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

from abc import abstractmethod
from typing import Any, Dict
from enum import Enum
from rag.flow.base import ProcessBase, ProcessParamBase


class ComponentType(Enum):
    """PowerRAG component types"""
    PARSER = "parser"
    EXTRACTOR = "extractor"
    SPLITTER = "splitter"


class PowerRAGConfig:
    """Configuration for PowerRAG components"""
    
    def __init__(self, enabled: bool = True, priority: int = 0, config: Dict[str, Any] = None):
        self.enabled = enabled
        self.priority = priority
        self.config = config or {}


class PowerRAGComponentParam(ProcessParamBase):
    """Base parameter class for PowerRAG components"""
    
    def __init__(self):
        super().__init__()
        self.component_type = ""
        self.enabled = True
        self.priority = 0
        self.custom_config = {}
    
    def check(self):
        """Validate parameters"""
        pass


class PowerRAGComponent(ProcessBase):
    """Base class for all PowerRAG components that can be used in pipeline"""
    component_name = "PowerRAGComponent"  # Default component name
    
    def __init__(self, canvas, id, param: PowerRAGComponentParam):
        super().__init__(canvas, id, param)
        self.component_type = self._get_component_type()
        self.name = self.__class__.__name__
    
    @abstractmethod
    def _get_component_type(self) -> ComponentType:
        """Return the type of this component"""
        pass
    
    async def _invoke(self, **kwargs):
        """Invoke the component - to be implemented by subclasses"""
        raise NotImplementedError()
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        custom_config = getattr(self._param, 'custom_config', {})
        return custom_config.get(key, default)
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate input data format"""
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get component metadata"""
        return {
            "name": self.name,
            "type": self.component_type.value,
            "enabled": self.is_enabled(),
            "priority": self.get_priority(),
            "config": getattr(self._param, 'custom_config', {})
        }