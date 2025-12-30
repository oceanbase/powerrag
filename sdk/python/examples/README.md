# RAGFlow SDK Examples

本目录包含使用 RAGFlow SDK 的示例脚本。

## 示例脚本

### batch_upload.py

通用的批量文档上传工具，支持多种文件格式和灵活的字段映射。

#### 功能特性

- ✅ 支持多种文件格式：
  - **多文档格式**（一个文件包含多个文档）：
    - **JSON**: 数组格式，包含多个文档对象
    - **JSONL**: 每行一个 JSON 对象
    - **CSV**: 每行一个文档（第一行为表头）
    - **XLSX/XLS**: Excel 文件，每行一个文档（第一行为表头）
  - **单文档格式**（一个文件对应一个文档）：
    - **PDF**: PDF 文档
    - **Office**: Word (.docx, .doc), PowerPoint (.pptx, .ppt), Excel (.xlsx, .xls)
    - **HTML**: HTML 文件 (.html, .htm)
    - **Markdown**: Markdown 文件 (.md, .markdown)
    - **文本**: 文本文件 (.txt)
    - **图片**: 图片文件 (.jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp)
    - **其他**: 邮件 (.eml), EPUB (.epub) 等 PowerRAG 支持的格式
- ✅ 迭代器模式，懒加载（不会一次性加载所有文件到内存）
- ✅ 支持断点续传（resume）
- ✅ 字段映射器，灵活映射数据源字段到标准格式
- ✅ 自动重试机制（指数退避）
- ✅ Snapshot 管理，防止重复处理

#### 标准字段格式

上传的文档会被映射为以下标准格式：

```python
{
    "title": "文档标题",
    "content": "文档内容",
    "metadata": {
        "doc_id": "文档ID（可选）",
        "doc_url": "文档URL（可选）",
        "tags": ["标签1", "标签2"]  # 可选
    }
}
```

#### 使用方法

##### 基本用法

```bash
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files
```

##### 上传到现有数据集

```bash
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    -i DATASET_ID
```

##### 自定义字段映射

如果数据源的字段名与默认不同，可以指定字段映射：

```bash
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    --title-field "article_title" \
    --content-field "article_body" \
    --doc-id-field "article_id" \
    --tags-field "categories" \
    --tags-separator ";"
```

##### 自定义批次大小

```bash
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    -b 20
```

##### 断点续传

如果上传过程中断，可以使用 `--resume` 参数从上次中断的地方继续：

```bash
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    --resume
```

##### 后台运行

使用 `nohup` 在后台运行，不输出日志：

```bash
nohup python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    &> /dev/null &
```

**说明**：
- `nohup`：确保进程在终端关闭后继续运行
- `&> /dev/null`：将标准输出和标准错误都重定向到 `/dev/null`，不保存日志
- `&`：在后台运行进程

如果需要查看进程状态，可以使用：
```bash
# 查看进程
ps aux | grep batch_upload.py

# 查看进程 ID（PID）
pgrep -f batch_upload.py
```

##### 指定文件类型

只处理特定类型的文件：

```bash
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    --file-patterns "*.json" "*.jsonl"
```

##### 控制多文档格式

控制哪些文件扩展名应被当作多文档格式处理：

```bash
# 默认：json 和 jsonl 作为多文档格式
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files

# 只将 json 作为多文档格式（jsonl 将被当作单文档格式）
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    --multi-doc-extensions json

# 将 json、jsonl 和 csv 都作为多文档格式
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    --multi-doc-extensions json jsonl csv

# 将 CSV、XLSX、XLS 作为单文档格式处理（只将 json 和 jsonl 作为多文档格式）
python examples/batch_upload.py \
    -k YOUR_API_KEY \
    -H http://localhost:9380 \
    -d /path/to/files \
    --multi-doc-extensions json jsonl
```

**注意**：
- 默认情况下，`json`、`jsonl`、`csv`、`xlsx`、`xls` 被当作多文档格式
- 可以通过 `--multi-doc-extensions` 参数控制哪些扩展名应被当作多文档格式
- 如果某个扩展名不在列表中，对应的文件将被当作单文档格式处理
- 对于 `json` 文件，只有数组格式（以 `[` 开头）才会被当作多文档格式
- 对于 `jsonl` 文件，如果在其扩展名列表中，始终被当作多文档格式
- **示例**：如果设置 `--multi-doc-extensions json jsonl`，则 `csv`、`xlsx`、`xls` 文件将被当作单文档格式处理（文件名作为 title，文件内容作为 content）

#### 参数说明

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--api-key` | `-k` | 是 | RAGFlow API 密钥 |
| `--host-address` | `-H` | 是 | RAGFlow 服务器地址（如：http://localhost:9380） |
| `--data-dir` | `-d` | 是 | 包含文件的目录路径 |
| `--dataset-id` | `-i` | 否 | 要使用的数据集 ID（如果不提供，将创建新数据集） |
| `--dataset-name` | `-n` | 否 | 新数据集的名称（默认：自动生成） |
| `--batch-size` | `-b` | 否 | 上传文档的批次大小（默认：5） |
| `--snapshot-file` | `-s` | 否 | 用于断点续传的快照文件路径（默认：upload_snapshot.json） |
| `--resume` | - | 否 | 从上次快照恢复上传 |
| `--file-extension` | - | 否 | 上传文档的文件扩展名（默认：txt） |
| `--title-field` | - | 否 | 标题字段名（默认：自动检测） |
| `--content-field` | - | 否 | 内容字段名（默认：自动检测） |
| `--doc-id-field` | - | 否 | 文档ID字段名（默认：自动检测） |
| `--doc-url-field` | - | 否 | 文档URL字段名（默认：自动检测） |
| `--tags-field` | - | 否 | 标签字段名（默认：自动检测） |
| `--tags-separator` | - | 否 | 标签分隔符（默认：,） |
| `--file-patterns` | - | 否 | 文件匹配模式（如：*.json *.csv） |
| `--multi-doc-extensions` | - | 否 | 指定哪些文件扩展名应被当作多文档格式处理（默认：json jsonl csv xlsx xls）。不在列表中的扩展名将被当作单文档格式处理 |

#### 文件格式说明

##### 多文档格式（一个文件包含多个文档）

**JSON 格式**（数组格式）：
```json
[
    {
        "id": "doc_001",
        "title": "文档标题",
        "text": "文档内容...",
        "tags": "tag1, tag2, tag3"  // 逗号分隔字符串（可以有空格）
    },
    {
        "id": "doc_002",
        "title": "另一个文档",
        "text": "更多内容...",
        "tags": ["tag2", "tag4"]  // 数组格式
    }
]
```

**JSONL 格式**（每行一个 JSON 对象）：
```jsonl
{"id": "doc_001", "title": "文档1", "text": "内容1", "tags": "tag1, tag2"}  // 逗号分隔字符串
{"id": "doc_002", "title": "文档2", "text": "内容2", "tags": ["tag3", "tag4"]}  // 数组格式
```

**CSV 格式**（第一行为表头，每行一个文档）：
```csv
id,title,content,tags
doc_001,文档1,内容1,"tag1, tag2"  // 逗号分隔字符串（可以有空格）
doc_002,文档2,内容2,"tag3"
```

**Excel 格式**（第一行为表头，每行一个文档）：
| id | title | content | tags |
|----|-------|---------|------|
| doc_001 | 文档1 | 内容1 | tag1, tag2 |
| doc_002 | 文档2 | 内容2 | tag3 |

**Tags 字段格式说明**：
- **逗号分隔字符串**：`"tag1, tag2, tag3"` 或 `"tag1,tag2,tag3"`（空格会被自动去除）
- **数组格式**：`["tag1", "tag2", "tag3"]`
- 两种格式都支持，工具会自动识别并解析

##### 单文档格式（一个文件对应一个文档）

对于单文档格式（PDF、Office、HTML、Markdown、文本、图片等），工具会自动处理：
- **title**: 自动使用文件名（不含扩展名）作为标题
- **content**: 文件内容（文本文件直接读取内容，二进制文件由 PowerRAG 解析）
- **metadata**: 为空（不包含 doc_id、doc_url、tags 等字段）

**示例**：
- `document.pdf` → title: "document", content: PDF 解析后的内容
- `report.docx` → title: "report", content: Word 文档解析后的内容
- `article.md` → title: "article", content: Markdown 文件内容
- `image.png` → title: "image", content: 图片 OCR 识别后的内容

#### 字段自动检测

如果不指定字段映射，工具会自动检测以下字段名：

- **title**: `title`, `name`, `subject`, `heading`, `header`
- **content**: `content`, `text`, `body`, `description`, `desc`, `data`
- **doc_id**: `id`, `doc_id`, `_id`, `document_id`, `docid`
- **doc_url**: `url`, `link`, `uri`, `doc_url`, `source_url`
- **tags**: `tags`, `tag`, `categories`, `category`, `labels`, `label`

#### 断点续传机制

工具支持断点续传功能：

1. **快照保存**：每次成功上传批次后自动保存进度快照
2. **文件级恢复**：记录已完全处理的文件，避免重复处理
3. **恢复上传**：使用 `--resume` 参数可以从上次中断的地方继续
4. **快照文件**：默认保存在 `upload_snapshot.json`，可通过 `-s` 参数自定义

快照文件包含以下信息：
- `processed_files`: 已完全处理的文件列表
- `total_processed`: 已处理的文档总数
- `dataset_id`: 数据集 ID（如果使用现有数据集）
- `timestamp`: 快照时间戳

#### 迭代器模式（编程方式）

对于需要更多控制的场景，可以使用迭代器模式，将文档提取和上传逻辑分离：

```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import BatchUploader, DocumentExtractor, FieldMapper

# 初始化
rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")

# 创建字段映射器
field_mapper = FieldMapper(
    title_field="article_title",
    content_field="article_body",
    tags_field="categories"
)

# 创建文档提取器
extractor = DocumentExtractor(field_mapper=field_mapper)

# 创建上传器
uploader = BatchUploader(rag)

# 获取或创建数据集
uploader.get_or_create_dataset(dataset_name="My Dataset")

# 方式1: 使用文档提取器的迭代器，然后手动上传
for batch, file_path, is_file_complete in extractor.extract_batches(
    data_dir="/path/to/files",
    batch_size=10
):
    # 处理批次
    print(f"Processing batch from {file_path}: {len(batch)} documents")
    
    # 可以在这里添加自定义处理逻辑
    # ...
    
    # 手动上传批次
    uploader.dataset.upload_documents_with_meta(batch)
    
    # 如果文件处理完成，可以执行额外操作
    if is_file_complete:
        print(f"File {file_path} completed")

# 方式2: 手动控制文档提取（如果需要自定义处理）
batch_iterator = extractor.extract_batches(
    data_dir="/path/to/files",
    batch_size=10
)

for batch, file_path, is_file_complete in batch_iterator:
    # 可以在这里添加自定义处理逻辑
    print(f"Processing batch from {file_path}: {len(batch)} documents")
    
    # 手动上传批次
    uploader.dataset.upload_documents_with_meta(batch, file_extension="txt")
    
    if is_file_complete:
        print(f"File {file_path} completed")
```

#### 错误处理

工具包含自动重试机制：
- 默认最多重试 10 次
- 使用指数退避策略（最大等待时间 8 秒）
- 失败时会记录错误信息并保存快照

#### 内存优化

工具使用迭代器模式，具有以下内存优化特性：

1. **懒加载**：文件只在需要时读取，不会一次性加载所有文件到内存
2. **批次处理**：文档按批次处理，每批次大小可配置
3. **流式处理**：大文件可以流式读取，不会占用过多内存

#### 注意事项

1. **文件顺序**：工具会按文件名排序处理文件，这对于断点续传很重要
2. **批次大小**：较小的批次大小可以提高容错性，但会增加 API 调用次数
3. **网络稳定性**：如果网络不稳定，建议使用较小的批次大小和启用断点续传
4. **数据集权限**：确保 API 密钥有权限访问指定的数据集
5. **Excel 支持**：需要安装 `pandas` 和 `openpyxl`：`pip install pandas openpyxl`

#### 故障排除

**问题：找不到数据集**
- 检查数据集 ID 是否正确
- 确认 API 密钥有权限访问该数据集

**问题：上传失败**
- 检查网络连接
- 查看日志中的错误信息
- 尝试使用 `--resume` 参数恢复上传

**问题：字段映射错误**
- 检查数据源字段名是否正确
- 使用 `--title-field` 等参数显式指定字段映射
- 查看日志中的字段检测信息

**问题：Excel 文件读取失败**
- 确保已安装 `pandas` 和 `openpyxl`：`pip install pandas openpyxl`
- 检查 Excel 文件格式是否正确
- 尝试将 Excel 文件转换为 CSV 格式

## 迁移指南

### 从 WikiUploader 迁移到 BatchUploader

如果你之前使用 `WikiUploader` 上传 Wiki JSON 文件，可以按以下方式迁移到新的 `BatchUploader`：

**旧代码（WikiUploader）：**
```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import WikiUploader

rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")
uploader = WikiUploader(rag)

total_docs, total_files = uploader.upload_wiki_json_files(
    data_dir="/path/to/json/files",
    batch_size=10
)
```

**新代码（BatchUploader）：**
```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.tools import BatchUploader, DocumentExtractor, FieldMapper

rag = RAGFlow(api_key="YOUR_API_KEY", base_url="http://localhost:9380")

# 创建字段映射器（Wiki JSON 格式：title, text, id, tags）
field_mapper = FieldMapper(
    title_field="title",
    content_field="text",
    doc_id_field="id",
    tags_field="tags"
)

# 创建文档提取器和上传器
extractor = DocumentExtractor(field_mapper=field_mapper)
uploader = BatchUploader(rag)

total_docs, total_files = uploader.upload(
    document_extractor=extractor,
    data_dir="/path/to/json/files",
    batch_size=10
)
```

新工具的优势：
- ✅ 支持更多文件格式（JSON、JSONL、CSV、XLSX、XLS 等）
- ✅ 更灵活的字段映射配置
- ✅ 更好的断点续传机制（文件级 + 文档索引级）
- ✅ 统一的 API 接口
