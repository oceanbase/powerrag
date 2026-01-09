# ragflow-sdk

RAGFlow Python SDK 提供了与 RAGFlow 服务交互的 Python 接口，包括数据集管理、文档上传、对话等功能。

## 安装

```shell
pip install ragflow-sdk
```

## 快速开始

```python
from ragflow_sdk import RAGFlow

# 初始化客户端
rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")

# 创建数据集
dataset = rag.create_dataset(name="My Dataset")

# 上传文档
documents = dataset.upload_documents_with_meta([
    {
        "title": "Document Title",
        "content": "Document content...",
        "metadata": {
            "tags": ["tag1", "tag2"]
        }
    }
])
```

## 文档

- [工具模块 API 参考](ragflow_sdk/tools/README.md) - FileReader, DocumentExtractor, FieldMapper, BatchUploader 等工具的详细 API 文档
- [示例脚本](examples/README.md) - 批量上传等示例脚本的使用说明

## 工具模块

SDK 提供了强大的工具模块，用于批量处理和文档管理：

- **FileReader**: 支持多种文件格式的文件读取器
- **DocumentExtractor**: 从文件/目录中提取文档
- **FieldMapper**: 灵活的字段映射器，支持自动字段检测
- **BatchUploader**: 批量上传器，支持断点续传和自动重试

详细文档请参考 [工具模块 API 参考](ragflow_sdk/tools/README.md)。

## 构建和发布

### 构建 Python SDK

```shell
uv build
```

### 发布到 PyPI

```shell
uv pip install twine
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD=$YOUR_PYPI_API_TOKEN
twine upload dist/*.whl
```
