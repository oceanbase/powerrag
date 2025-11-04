# PowerRAG Custom Parsers

PowerRAG 自定义解析器模块，提供专门的文档解析策略。

## Title Parser（标题解析器）

### 概述

Title Parser 是 PowerRAG 的核心解析器，使用 **PowerRAG 自定义的 MinerU 解析器** (`powerrag.parser.mineru_parser.MinerUPdfParser`) 进行 PDF 解析，并按照文档的标题/章节结构组织内容。

**配置参数：**
- `parser_id`: `"title"`
- `layout_recognize`: `"mineru"`

**与 RAGFlow 的区别：**
- ❌ 不使用 `deepdoc.parser.mineru_parser`
- ✅ 使用 PowerRAG 自定义的 `powerrag.parser.mineru_parser.MinerUPdfParser`
- ✅ 支持通过 HTTP API 调用 MinerU 服务
- ✅ 自动处理图片存储和 URL 转换

### 特性

#### 1. 基于标题的智能分块

- 自动识别文档中的标题/章节
- 将内容按标题组织成逻辑块
- 保留文档的层次结构

#### 2. 标题识别规则

解析器使用以下规则识别标题：

1. **Markdown 风格标题**
   ```
   # 一级标题
   ## 二级标题
   ### 三级标题
   ```

2. **编号标题**
   ```
   1. 第一章
   2. 第二章
   I. 罗马数字标题
   ```

3. **大写标题**
   - 全部大写的文本（至少 50% 大写字母）
   - 标题格式：大部分单词首字母大写（至少 60%）

4. **长度限制**
   - 标题长度不超过 200 字符
   - 通常不以句号结尾

#### 3. 块组织策略

```
文档结构：
  Title 1
    - Content 1a
    - Content 1b
  Title 2
    - Content 2a
    - Content 2b

生成的 chunks：
  Chunk 1: Title 1 + Content 1a + Content 1b
  Chunk 2: Title 2 + Content 2a + Content 2b
```

### 使用方法

#### 在 PowerRAG 服务中使用

```python
from powerrag.app import title

# 解析文档
chunks = title.chunk(
    filename="document.pdf",
    binary=pdf_binary,
    from_page=0,
    to_page=100,
    lang="Chinese",  # or "English"
    callback=None,
    parser_config={
        "chunk_token_num": 16096,
        "delimiter": "\n!?;。；！？",
        "layout_recognize": "mineru"
    },
    tenant_id=None
)
```

#### 通过 API 使用

```bash
curl -X POST http://localhost:6000/api/v1/powerrag/parse \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "your_pdf_document_id",
    "config": {
      "lang": "Chinese",
      "chunk_token_num": 16096,
      "layout_recognize": "mineru"
    }
  }'
```

### 返回格式

每个 chunk 包含以下字段：

```json
{
  "content_with_weight": "标题\n\n内容文本...",
  "docnm_kwd": "document.pdf",
  "title_tks": [...],
  "title_sm_tks": [...],
  "title_kwd": "章节标题",
  "title_ltks": [...],
  "content_ltks": [...],
  "content_sm_ltks": [...],
  "page_num_int": [1, 2, 3],
  "position_int": [(page, x0, x1, y0, y1), ...],
  "top_int": [y_position],
  "doc_type_kwd": "pdf"
}
```

### 配置选项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `lang` | `"Chinese"` | 语言设置（Chinese/English） |
| `chunk_token_num` | `16096` | 每个块的最大 token 数 |
| `delimiter` | `"\n!?;。；！？"` | 分隔符 |
| `layout_recognize` | `"mineru"` | 布局识别方式 |
| `from_page` | `0` | 起始页码 |
| `to_page` | `100000` | 结束页码 |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MINERU_EXECUTABLE` | `"mineru"` | MinerU 可执行文件路径 |
| `MINERU_OUTPUT_DIR` | `""` | MinerU 输出目录 |
| `MINERU_DELETE_OUTPUT` | `"1"` | 是否删除 MinerU 临时输出 |

### 依赖

#### 1. MinerU 服务

PowerRAG 使用 HTTP API 调用 MinerU 服务，需要配置 MinerU 服务地址。

**配置文件：** `conf/service_conf.yaml`

```yaml
mineru:
  hosts: "http://localhost:8080"  # MinerU 服务地址
  backend: "pipeline"              # 或 "vlm-http-client"
  server_url: ""                   # backend 为 vlm-http-client 时需要
```

**启动 MinerU 服务：**
```bash
# 详见 MinerU 官方文档
pip install -U 'mineru[core]'
mineru --version
# 启动 MinerU HTTP 服务
```

#### 2. RAGFlow Tokenizer

用于文本分词：
```python
from rag.nlp import rag_tokenizer
```

#### 3. PowerRAG Parser

PowerRAG 自定义的 MinerU 解析器：
```python
from powerrag.parser.mineru_parser import MinerUPdfParser
```

### 优势

#### 1. 保留文档结构
- 按照作者的意图组织内容
- 每个块都有明确的主题（标题）
- 适合问答和检索

#### 2. 语义完整性
- 避免在段落中间切分
- 相关内容保持在同一个块中
- 提高检索准确性

#### 3. 更好的上下文
- 每个块包含标题信息
- 便于理解内容的位置和层级
- 提供更好的引用来源

### 降级策略

如果文档没有明显的标题结构：
- 自动降级为基于段落的分块
- 每个段落/小节作为一个独立的块
- 仍然保留页码和位置信息

### 示例

#### 输入 PDF

```
第一章 引言
本文档介绍了...

1.1 背景
在过去的几年里...

第二章 方法
我们采用了以下方法...
```

#### 输出 Chunks

```python
[
  {
    "content_with_weight": "第一章 引言\n\n本文档介绍了...",
    "title_kwd": "第一章 引言",
    "page_num_int": [1],
    ...
  },
  {
    "content_with_weight": "1.1 背景\n\n在过去的几年里...",
    "title_kwd": "1.1 背景",
    "page_num_int": [1, 2],
    ...
  },
  {
    "content_with_weight": "第二章 方法\n\n我们采用了以下方法...",
    "title_kwd": "第二章 方法",
    "page_num_int": [3],
    ...
  }
]
```

### 与其他解析器的对比

| 特性 | Title Parser | Naive Parser | 其他 Parser |
|------|-------------|--------------|------------|
| 标题识别 | ✅ 自动识别 | ❌ 无 | ❌ 无 |
| 结构保留 | ✅ 完整保留 | ⚠️ 部分 | ⚠️ 部分 |
| 语义完整 | ✅ 高 | ⚠️ 中 | ⚠️ 中 |
| 布局识别 | ✅ MinerU | ⚠️ 基础 | ✅ DeepDOC |
| 适用场景 | 结构化文档 | 通用 | 特定类型 |

### 最佳实践

#### 1. 选择合适的语言设置

```python
# 中文文档
chunks = title.chunk(..., lang="Chinese")

# 英文文档
chunks = title.chunk(..., lang="English")
```

#### 2. 调整块大小

```python
# 长文档，使用大块
config = {"chunk_token_num": 16096}

# 短文档或需要细粒度检索
config = {"chunk_token_num": 4096}
```

#### 3. 处理特殊文档

```python
# 没有明显标题的文档
# 解析器会自动降级为段落分块

# 多栏布局文档
# MinerU 会自动处理布局识别
```

### 故障排查

#### 问题 1: MinerU 未安装

```
RuntimeError: MinerU not installed
```

**解决方案：**
```bash
pip install -U 'mineru[core]'
mineru --version  # 验证安装
```

#### 问题 2: 没有识别到标题

**原因：**
- 文档没有明显的标题格式
- 标题识别规则不匹配

**解决方案：**
- 检查文档格式
- 调整标题识别规则（修改 `_is_title` 函数）
- 使用降级的段落分块（自动）

#### 问题 3: 块太大或太小

**解决方案：**
```python
# 调整 chunk_token_num
config = {
    "chunk_token_num": 8192  # 减小块大小
}
```

### 扩展

如果需要自定义标题识别规则，可以修改 `powerrag/app/title.py` 中的 `_is_title` 函数：

```python
def _is_title(text: str, pattern: re.Pattern) -> bool:
    # 添加自定义规则
    if text.startswith("Chapter "):
        return True
    
    # 其他规则...
    return False
```

## 许可证

Apache License 2.0

