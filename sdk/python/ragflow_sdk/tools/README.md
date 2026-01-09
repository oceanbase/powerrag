# RAGFlow SDK Tools API Reference

本文档介绍 RAGFlow SDK 工具模块的 API 参考。

## 目录

- [FileReader](#filereader) - 文件读取器
- [DocumentExtractor](#documentextractor) - 文档提取器
- [FieldMapper](#fieldmapper) - 字段映射器
- [BatchUploader](#batchuploader) - 批量上传器
- [Models](#models) - 数据模型

---

## FileReader

文件读取器，支持多种文件格式的批量迭代读取。

### 类定义

```python
class FileReader:
    def __init__(
        self,
        field_mapper: Optional[FieldMapper] = None,
        multi_doc_extensions: Optional[List[str]] = None
    )
```

### 参数

- `field_mapper` (Optional[FieldMapper]): 字段映射器实例，用于字段映射
- `multi_doc_extensions` (Optional[List[str]]): 应被视为多文档格式的文件扩展名列表（不含点号）
  - 默认: `['json', 'jsonl']`
  - 不在列表中的扩展名将被视为单文档格式

### 方法

#### `is_multi_document_format(file_path: str) -> bool`

检查文件是否为多文档格式。

**参数:**
- `file_path` (str): 文件路径

**返回:**
- `bool`: 如果文件包含多个文档返回 `True`，否则返回 `False`

**示例:**
```python
reader = FileReader()
is_multi = reader.is_multi_document_format("data.json")
```

#### `read_file(file_path: str, start_index: int = 0) -> Iterator[Dict[str, Any]]`

读取文件并生成文档。

**参数:**
- `file_path` (str): 文件路径
- `start_index` (int): 起始文档索引（对于多文档格式，跳过此索引之前的文档）

**返回:**
- `Iterator[Dict[str, Any]]`: 文档字典的迭代器

**示例:**
```python
reader = FileReader()
for doc in reader.read_file("data.json"):
    print(doc)
```

#### `read_files_batch(file_paths: List[str], batch_size: int, processed_files: Optional[List[str]] = None) -> Iterator[List[Dict[str, Any]]]`

批量读取多个文件。

**参数:**
- `file_paths` (List[str]): 要读取的文件路径列表
- `batch_size` (int): 每批文档数量
- `processed_files` (Optional[List[str]]): 已处理文件路径列表（将被跳过）

**返回:**
- `Iterator[List[Dict[str, Any]]]`: 文档批次列表的迭代器

**示例:**
```python
reader = FileReader()
file_paths = ["file1.json", "file2.json"]
for batch in reader.read_files_batch(file_paths, batch_size=10):
    print(f"Batch size: {len(batch)}")
```

### 支持的文件格式

#### 多文档格式
- **JSON**: 数组格式（以 `[` 开头）
- **JSONL**: 每行一个 JSON 对象
- **CSV**: 每行一个文档（第一行为表头）
- **XLSX/XLS**: Excel 文件，每行一个文档（第一行为表头）

#### 单文档格式
- **PDF**: PDF 文档
- **Office**: Word (.docx, .doc), PowerPoint (.pptx, .ppt)
- **HTML**: HTML 文件 (.html, .htm)
- **Markdown**: Markdown 文件 (.md, .markdown)
- **文本**: 文本文件 (.txt)
- **图片**: 图片文件 (.jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp)
- **其他**: 邮件 (.eml), EPUB (.epub)

---

## DocumentExtractor

文档提取器，从文件/目录中提取文档。

### 类定义

```python
class DocumentExtractor:
    def __init__(
        self,
        field_mapper: Optional[FieldMapper] = None,
        multi_doc_extensions: Optional[List[str]] = None
    )
```

### 参数

- `field_mapper` (Optional[FieldMapper]): 字段映射器实例
- `multi_doc_extensions` (Optional[List[str]]): 多文档格式扩展名列表
  - 默认: `['json', 'jsonl', 'csv', 'xlsx', 'xls']`

### 方法

#### `extract_documents(data_dir: str, file_patterns: Optional[List[str]] = None, processed_files: Optional[List[str]] = None) -> Iterator[Tuple[Dict[str, Any], str]]`

从目录中的文件提取文档。

**参数:**
- `data_dir` (str): 包含文件的目录
- `file_patterns` (Optional[List[str]]): 可选的文件匹配模式列表
- `processed_files` (Optional[List[str]]): 已处理文件路径列表（将被跳过）

**返回:**
- `Iterator[Tuple[Dict[str, Any], str]]`: 文档字典和文件路径的元组迭代器

**示例:**
```python
extractor = DocumentExtractor()
for doc, file_path in extractor.extract_documents("/path/to/files"):
    print(f"Document from {file_path}: {doc['title']}")
```

#### `extract_batches(data_dir: str, batch_size: int, file_patterns: Optional[List[str]] = None, file_cursor: Optional[Dict[str, int]] = None) -> Iterator[Tuple[List[Dict[str, Any]], str, bool]]`

从目录中的文件批量提取文档。

**参数:**
- `data_dir` (str): 包含文件的目录
- `batch_size` (int): 每批文档数量
- `file_patterns` (Optional[List[str]]): 可选的文件匹配模式列表
- `file_cursor` (Optional[Dict[str, int]]): 可选的文件路径到文档索引的映射字典，用于从指定索引恢复

**返回:**
- `Iterator[Tuple[List[Dict[str, Any]], str, bool]]`: 文档批次列表、当前文件路径和文件是否完成的元组迭代器

**示例:**
```python
extractor = DocumentExtractor()
for batch, file_path, is_complete in extractor.extract_batches(
    data_dir="/path/to/files",
    batch_size=10
):
    print(f"Batch from {file_path}: {len(batch)} documents")
    if is_complete:
        print(f"File {file_path} completed")
```

---

## FieldMapper

字段映射器，将源文档字段转换为 RAGFlow 标准格式。

### 类定义

```python
class FieldMapper:
    def __init__(
        self,
        title_field: Optional[str] = None,
        content_field: Optional[str] = None,
        doc_id_field: Optional[str] = None,
        doc_url_field: Optional[str] = None,
        tags_field: Optional[str] = None,
        tags_separator: str = ',',
        config: Optional[FieldMappingConfig] = None
    )
```

### 参数

- `title_field` (Optional[str]): 标题字段名（None = 自动检测）
- `content_field` (Optional[str]): 内容字段名（None = 自动检测）
- `doc_id_field` (Optional[str]): 文档ID字段名（None = 自动检测）
- `doc_url_field` (Optional[str]): 文档URL字段名（None = 自动检测）
- `tags_field` (Optional[str]): 标签字段名（None = 自动检测）
- `tags_separator` (str): 标签分隔符（默认: `','`）
- `config` (Optional[FieldMappingConfig]): 字段映射配置实例（如果提供，将覆盖单独字段）

### 方法

#### `map(doc: Dict[str, Any]) -> Dict[str, Any]`

将源文档映射为 RAGFlow 标准格式。

**参数:**
- `doc` (Dict[str, Any]): 源文档字典

**返回:**
- `Dict[str, Any]`: RAGFlow 格式的映射文档

**标准格式:**
```python
{
    "title": str,
    "content": str,
    "metadata": {
        "doc_id": str (optional),
        "doc_url": str (optional),
        "tags": List[str] (optional)
    }
}
```

**示例:**
```python
mapper = FieldMapper(
    title_field="article_title",
    content_field="article_body",
    tags_field="categories"
)

source_doc = {
    "article_title": "My Article",
    "article_body": "Content here...",
    "categories": "tech, python"
}

mapped_doc = mapper.map(source_doc)
# Result:
# {
#     "title": "My Article",
#     "content": "Content here...",
#     "metadata": {
#         "tags": ["tech", "python"]
#     }
# }
```

### 自动字段检测

如果不指定字段映射，工具会自动检测以下字段名：

- **title**: `title`, `name`, `subject`, `heading`, `header`
- **content**: `content`, `text`, `body`, `description`, `desc`, `data`
- **doc_id**: `id`, `doc_id`, `_id`, `document_id`, `docid`
- **doc_url**: `url`, `link`, `uri`, `doc_url`, `source_url`
- **tags**: `tags`, `tag`, `categories`, `category`, `labels`, `label`

### 标签格式支持

支持以下标签格式：

- **数组格式**: `["tag1", "tag2", "tag3"]`
- **逗号分隔字符串**: `"tag1, tag2, tag3"` 或 `"tag1,tag2,tag3"`（空格会被自动去除）

---

## BatchUploader

批量上传器，用于将大量文档上传到 RAGFlow。

### 类定义

```python
class BatchUploader:
    def __init__(self, rag: RAGFlow, dataset: Optional[DataSet] = None)
```

### 参数

- `rag` (RAGFlow): RAGFlow 客户端实例
- `dataset` (Optional[DataSet]): 可选的数据集实例

### 方法

#### `set_dataset(dataset: DataSet)`

设置要用于上传的数据集。

**参数:**
- `dataset` (DataSet): 数据集实例

#### `get_or_create_dataset(dataset_id: Optional[str] = None, dataset_name: Optional[str] = None) -> DataSet`

获取现有数据集或创建新数据集。

**参数:**
- `dataset_id` (Optional[str]): 可选的现有数据集 ID
- `dataset_name` (Optional[str]): 可选的新数据集名称（默认: 自动生成）

**返回:**
- `DataSet`: 数据集实例

**示例:**
```python
uploader = BatchUploader(rag)
dataset = uploader.get_or_create_dataset(dataset_name="My Dataset")
```

#### `upload(document_extractor: DocumentExtractor, data_dir: str, dataset_id: Optional[str] = None, dataset_name: Optional[str] = None, batch_size: int = 5, snapshot_file: str = "upload_snapshot.json", resume: bool = False, file_extension: str = "txt", file_patterns: Optional[List[str]] = None) -> Tuple[int, int]`

从目录上传文档到 RAGFlow。

**参数:**
- `document_extractor` (DocumentExtractor): 文档提取器实例
- `data_dir` (str): 包含要上传文件的目录
- `dataset_id` (Optional[str]): 可选的数据集 ID
- `dataset_name` (Optional[str]): 可选的新数据集名称
- `batch_size` (int): 每批文档数量（默认: 5）
- `snapshot_file` (str): 用于断点续传的快照文件路径（默认: "upload_snapshot.json"）
- `resume` (bool): 是否从快照恢复（默认: False）
- `file_extension` (str): 上传文档的文件扩展名（默认: "txt"）
- `file_patterns` (Optional[List[str]]): 可选的文件匹配模式列表

**返回:**
- `Tuple[int, int]`: (已处理文档总数, 已处理文件总数)

**示例:**
```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import BatchUploader, DocumentExtractor

rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")
extractor = DocumentExtractor()
uploader = BatchUploader(rag)

total_docs, total_files = uploader.upload(
    document_extractor=extractor,
    data_dir="/path/to/files",
    batch_size=10,
    resume=True
)
```

#### `retry_with_backoff(func, max_retries: int = 10, max_backoff: int = 8)`

带指数退避的重试包装器（静态方法）。

**参数:**
- `func`: 要重试的函数
- `max_retries` (int): 最大重试次数（默认: 10）
- `max_backoff` (int): 最大重试间隔（秒）（默认: 8）

**返回:**
- 带重试逻辑的包装函数

#### `save_snapshot(snapshot_file: str, file_cursors: List[FileCursor], total_processed: int, dataset_id: Optional[str] = None)`

保存处理快照到文件（静态方法）。

**参数:**
- `snapshot_file` (str): 快照文件路径
- `file_cursors` (List[FileCursor]): 文件游标实体列表，每个游标跟踪一个文件的处理进度
- `total_processed` (int): 已处理文档总数
- `dataset_id` (Optional[str]): 可选的数据集 ID

#### `load_snapshot(snapshot_file: str) -> Optional[Snapshot]`

从文件加载处理快照（静态方法）。

**参数:**
- `snapshot_file` (str): 快照文件路径

**返回:**
- `Optional[Snapshot]`: 快照实体，如果文件不存在或无效则返回 None

### 特性

- ✅ 迭代器模式的批量处理
- ✅ 基于快照的断点续传支持
- ✅ 自动重试（指数退避）
- ✅ 文件级和文档索引级的恢复支持

---

## Models

### FileType

文件类型枚举。

```python
class FileType(Enum):
    JSON_ARRAY = "json_array"
    JSONL = "jsonl"
    CSV = "csv"
    EXCEL = "excel"
    SINGLE = "single"
```

### DocumentFormat

文档格式枚举。

```python
class DocumentFormat(Enum):
    MULTI_DOC = "multi_doc"  # 一个文件包含多个文档
    SINGLE_DOC = "single_doc"  # 一个文件对应一个文档
```

### DocumentMetadata

文档元数据实体。

```python
@dataclass
class DocumentMetadata:
    doc_id: Optional[str] = None
    doc_url: Optional[str] = None
    tags: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentMetadata"
    def is_empty(self) -> bool
```

**方法说明:**
- `to_dict()`: 将元数据转换为字典格式
- `from_dict()`: 从字典创建元数据实体
- `is_empty()`: 检查元数据是否为空（所有字段都为 None）

### Document

RAGFlow 标准格式的文档实体。

```python
@dataclass
class Document:
    title: str
    content: str
    metadata: Optional[DocumentMetadata] = None
    
    def to_dict(self) -> Dict
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document"
```

### FieldMappingConfig

字段映射配置。

```python
@dataclass
class FieldMappingConfig:
    title_field: Optional[str] = None
    content_field: Optional[str] = None
    doc_id_field: Optional[str] = None
    doc_url_field: Optional[str] = None
    tags_field: Optional[str] = None
    tags_separator: str = ','
```

### FileCursor

文件游标实体，用于跟踪单个文件的文档处理进度。

```python
@dataclass
class FileCursor:
    file_path: str
    doc_index: int
    
    def to_dict(self) -> Dict[str, Any]
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileCursor"
```

**字段说明:**
- `file_path` (str): 文件路径
- `doc_index` (int): 下一个要处理的文档索引（索引 >= 此值的文档已处理）

**方法说明:**
- `to_dict()`: 将文件游标转换为字典格式
- `from_dict()`: 从字典创建文件游标实体

### Snapshot

处理快照实体，用于断点续传支持。

```python
@dataclass
class Snapshot:
    file_cursors: List[FileCursor] = field(default_factory=list)
    total_processed: int = 0
    timestamp: float = 0.0
    dataset_id: Optional[str] = None
    
    def get_cursor(self, file_path: str) -> Optional[FileCursor]
    def set_cursor(self, file_path: str, doc_index: int) -> None
    def remove_cursor(self, file_path: str) -> None
    def to_dict(self) -> Dict[str, Any]
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot"
```

**字段说明:**
- `file_cursors` (List[FileCursor]): 文件游标实体列表，每个游标跟踪一个文件的处理进度
- `total_processed` (int): 已处理文档总数
- `timestamp` (float): 快照创建时间戳
- `dataset_id` (Optional[str]): 可选的数据集 ID

**方法说明:**
- `get_cursor(file_path)`: 获取指定文件路径的游标
- `set_cursor(file_path, doc_index)`: 设置或更新文件路径的游标
- `remove_cursor(file_path)`: 移除文件路径的游标
- `to_dict()`: 将快照转换为字典格式
- `from_dict()`: 从字典创建快照实体

### BatchInfo

批量处理信息。

```python
@dataclass
class BatchInfo:
    batch_documents: List[Dict[str, Any]]
    file_path: str
    is_file_complete: bool
```

---

## 使用示例

### 基本用法

```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import BatchUploader, DocumentExtractor, FieldMapper

# 初始化 RAGFlow 客户端
rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")

# 创建字段映射器（可选）
field_mapper = FieldMapper(
    title_field="article_title",
    content_field="article_body",
    tags_field="categories"
)

# 创建文档提取器
extractor = DocumentExtractor(field_mapper=field_mapper)

# 创建批量上传器
uploader = BatchUploader(rag)

# 上传文档
total_docs, total_files = uploader.upload(
    document_extractor=extractor,
    data_dir="/path/to/files",
    batch_size=10,
    resume=True
)

print(f"Uploaded {total_docs} documents from {total_files} files")
```

### 使用迭代器模式

```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import BatchUploader, DocumentExtractor

rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")
extractor = DocumentExtractor()
uploader = BatchUploader(rag)

# 获取或创建数据集
uploader.get_or_create_dataset(dataset_name="My Dataset")

# 使用迭代器模式提取和上传
for batch, file_path, is_file_complete in extractor.extract_batches(
    data_dir="/path/to/files",
    batch_size=10
):
    # 可以在这里添加自定义处理逻辑
    print(f"Processing batch from {file_path}: {len(batch)} documents")
    
    # 手动上传批次
    uploader.dataset.upload_documents_with_meta(batch, file_extension="txt")
    
    if is_file_complete:
        print(f"File {file_path} completed")
```

### 自定义字段映射

```python
from ragflow_sdk.tools import FieldMapper

# 创建自定义字段映射器
mapper = FieldMapper(
    title_field="article_title",
    content_field="article_body",
    doc_id_field="article_id",
    doc_url_field="article_url",
    tags_field="categories",
    tags_separator=";"
)

# 映射文档
source_doc = {
    "article_title": "My Article",
    "article_body": "Content...",
    "article_id": "123",
    "article_url": "https://example.com/article",
    "categories": "tech;python;ai"
}

mapped_doc = mapper.map(source_doc)
```

---

## 注意事项

1. **内存优化**: 工具使用迭代器模式，支持懒加载，不会一次性加载所有文件到内存
2. **断点续传**: 支持文件级和文档索引级的断点续传，适合处理大量文档
3. **错误处理**: 包含自动重试机制（指数退避），默认最多重试 10 次
4. **文件顺序**: 工具会按文件名排序处理文件，这对于断点续传很重要
5. **Excel 支持**: 需要安装 `pandas` 和 `openpyxl`：`pip install pandas openpyxl`

