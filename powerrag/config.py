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
PowerRAG Configuration Module

This module provides configuration management for PowerRAG components.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PowerRAGConfigManager:
    """Configuration manager for PowerRAG"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config = self._load_config()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Look for config in project root
        project_root = Path(__file__).parent.parent
        return str(project_root / "conf" / "powerrag_config.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.info(f"PowerRAG config file not found at {self.config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load PowerRAG config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "enabled": True,
            "log_level": "INFO",
            "components": {
                "parsers": {
                    "advanced_pdf": {
                        "enabled": True,
                        "priority": 10,
                        "config": {
                            "extract_tables": True,
                            "extract_images": False,
                            "preserve_layout": True,
                            "use_ocr": False
                        }
                    },
                    "advanced_docx": {
                        "enabled": True,
                        "priority": 10,
                        "config": {
                            "extract_tables": True,
                            "extract_images": False,
                            "preserve_headers": True,
                            "preserve_footers": True
                        }
                    }
                },
                "extractors": {
                    "entity_extractor": {
                        "enabled": True,
                        "priority": 5,
                        "config": {
                            "entity_types": ["PERSON", "ORG", "GPE", "MONEY", "DATE", "TIME"],
                            "use_regex": True,
                            "use_llm": False,
                            "confidence_threshold": 0.5
                        }
                    },
                    "keyword_extractor": {
                        "enabled": True,
                        "priority": 5,
                        "config": {
                            "max_keywords": 20,
                            "min_word_length": 3,
                            "remove_stopwords": True,
                            "use_tfidf": True
                        }
                    },
                    "summary_extractor": {
                        "enabled": False,
                        "priority": 3,
                        "config": {
                            "max_sentences": 3,
                            "max_length": 200,
                            "use_llm": False
                        }
                    }
                },
                "splitters": {
                    "semantic_splitter": {
                        "enabled": True,
                        "priority": 8,
                        "config": {
                            "similarity_threshold": 0.7,
                            "use_sentence_embeddings": True,
                            "min_sentences_per_chunk": 2,
                            "max_sentences_per_chunk": 10
                        }
                    },
                    "hierarchical_splitter": {
                        "enabled": True,
                        "priority": 7,
                        "config": {
                            "preserve_headers": True,
                            "preserve_lists": True,
                            "max_header_level": 3,
                            "min_chunk_size": 200
                        }
                    },
                    "adaptive_splitter": {
                        "enabled": True,
                        "priority": 9,
                        "config": {
                            "adaptive_chunk_size": True,
                            "density_threshold": 0.5,
                            "complexity_threshold": 0.7
                        }
                    }
                }
            },
            "pipeline": {
                "max_workers": 4,
                "timeout": 300,
                "retry_attempts": 3,
                "fallback_enabled": True
            },
            "integration": {
                "auto_register": True,
                "override_existing": False,
                "log_integration": True
            }
        }
    
    def get_config(self, key: str = None, default: Any = None) -> Any:
        """Get configuration value"""
        if key is None:
            return self._config
        
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save_config(self) -> bool:
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"PowerRAG config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save PowerRAG config: {e}")
            return False
    
    def is_enabled(self) -> bool:
        """Check if PowerRAG is enabled"""
        return self.get_config("enabled", True)
    
    def get_component_config(self, component_type: str, component_name: str) -> Dict[str, Any]:
        """Get configuration for a specific component"""
        return self.get_config(f"components.{component_type}.{component_name}", {})
    
    def set_component_config(self, component_type: str, component_name: str, config: Dict[str, Any]) -> None:
        """Set configuration for a specific component"""
        self.set_config(f"components.{component_type}.{component_name}", config)
        self.save_config()
    
    def is_component_enabled(self, component_type: str, component_name: str) -> bool:
        """Check if a component is enabled"""
        return self.get_component_config(component_type, component_name).get("enabled", True)
    
    def enable_component(self, component_type: str, component_name: str) -> None:
        """Enable a component"""
        config = self.get_component_config(component_type, component_name)
        config["enabled"] = True
        self.set_component_config(component_type, component_name, config)
    
    def disable_component(self, component_type: str, component_name: str) -> None:
        """Disable a component"""
        config = self.get_component_config(component_type, component_name)
        config["enabled"] = False
        self.set_component_config(component_type, component_name, config)


# Global configuration manager
_config_manager = PowerRAGConfigManager()


def get_config_manager() -> PowerRAGConfigManager:
    """Get the global configuration manager"""
    return _config_manager


def get_config(key: str = None, default: Any = None) -> Any:
    """Get configuration value from global manager"""
    return _config_manager.get_config(key, default)


def set_config(key: str, value: Any) -> None:
    """Set configuration value in global manager"""
    _config_manager.set_config(key, value)


def is_powerrag_enabled() -> bool:
    """Check if PowerRAG is enabled"""
    return _config_manager.is_enabled()