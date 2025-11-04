<p align="center">
    <a href="https://github.com/oceanbase/powerrag">
        <img alt="PowerRAG Logo" src="https://img.shields.io/badge/PowerRAG-blue" width="50%" />
    </a>
</p>

<p align="center">
  <a href="https://github.com/oceanbase/powerrag">GitHub</a>
  ·
  <a href="https://github.com/oceanbase/powerrag/issues">Report Bug</a>
  ·
  <a href="https://github.com/oceanbase/powerrag/discussions">Discussions</a>
</p>

<p align="center">
    <a href="https://github.com/oceanbase/powerrag">
        <img src="https://img.shields.io/github/commit-activity/m/oceanbase/powerrag?style=flat-square" alt="GitHub commit activity">
    </a>
    <a href="https://github.com/oceanbase/powerrag/blob/master/LICENSE">
        <img alt="license" src="https://img.shields.io/badge/license-Apache%202.0-green.svg" />
    </a>
    <a href="https://img.shields.io/badge/python%20-3.10.0%2B-blue.svg">
        <img alt="pyversions" src="https://img.shields.io/badge/python%20-3.10.0%2B-blue.svg" />
    </a>
</p>

[English](README.md) | [中文](README_zh.md)

# PowerRAG

## Introduction

PowerRAG Community Edition is an open-source project based on [RAGFlow](https://github.com/infiniflow/ragflow), licensed under Apache License 2.0. While preserving RAGFlow's core capabilities and interface compatibility, this project extends functionality in document processing, structured information extraction, effectiveness evaluation, and feedback mechanisms, aiming to provide a more comprehensive integrated data service engine for Large Language Model (LLM) applications.

PowerRAG Community Edition targets developers and research teams building RAG (Retrieval-Augmented Generation) applications. Through atomic API design, it can be flexibly embedded into various intelligent applications, supporting rapid construction, monitoring, and optimization of LLM-based Q&A, knowledge extraction, and generation systems.

## Highlights

### Document Service

PowerRAG extends RAGFlow's document processing capabilities with multi-engine and multi-mode support, suitable for more complex document scenarios:

- **Multi-Engine OCR Support**: Integrates MinerU and Dots.OCR for complex document recognition and text extraction
- **Multiple Chunking Strategies**: Supports title-based, regex-based, and intelligent chunking algorithms to improve content organization and retrieval efficiency
- **Structured Information Extraction**: Implements structured information recognition and extraction based on [LangExtract](https://github.com/langextract/langextract), supporting extraction of tables, fields, entities, and other structured content from documents, providing data foundation for knowledge graphs and semantic retrieval

### Hybrid Retrieval

PowerRAG application platform is built on OceanBase's multi-modal integrated database architecture (SQL + NoSQL), fully leveraging OceanBase's high performance, scalability, and hybrid storage capabilities to provide high-performance underlying support for intelligent retrieval and knowledge services.

- **Hybrid Index Retrieval**: With OceanBase 4.4.1 capabilities, implements joint queries of vector indexes and full-text indexes, combining semantic relevance with keyword matching to improve the comprehensiveness and accuracy of information recall
- **Multi-Modal Data Retrieval**: Introduces scalar conditions on top of vector retrieval, enabling further filtering based on numerical, temporal, or categorical attributes in semantic results, achieving precise control of result ranking and filtering
- **Unified Data Access Layer**: Through OceanBase's multi-modal integrated interface, uniformly manages text, vector, and structured data, enabling efficient cross-modal and cross-type queries

This capability enables PowerRAG to provide more flexible knowledge access patterns in multi-type knowledge sources and complex retrieval scenarios, providing efficient and scalable underlying data support for LLM applications.

### Evaluation and Feedback

PowerRAG Community Edition introduces an evaluation and feedback module, which is built on [Langfuse](https://github.com/oceanbase/langfuse), to help developers systematically measure and optimize LLM application effectiveness, forming an observable, analyzable, and improvable closed-loop system. When introducing this component, PowerRAG Community Edition has added localization adaptations, Qwen model integration, and implemented a compatibility bridge adapter with PowerRAG to ensure seamless integration into the PowerRAG ecosystem. This module includes the following core capabilities:

- **Observability**: Provides end-to-end call chain tracing and performance analysis. Developers can fully understand the entire model inference process, including input/output, tool calls, retry processes, latency, and call costs, supporting model performance optimization and cost control
- **Prompt Management**: Supports storage, version management, and retrieval of prompts, facilitating team prompt tuning, sharing, and reuse, achieving standardization and traceability of prompt design
- **Evaluation Capabilities**: Provides multiple evaluation methods, supporting effectiveness verification and quality comparison of model outputs at different stages, helping teams achieve continuous optimization and automated testing

Through this module, PowerRAG can achieve a complete feedback loop from data input, prompt design to effect evaluation in the model development and application process, helping teams improve model interpretability and application quality.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 8GB of available memory

### Installation and Startup

1. **Clone the repository**
   ```bash
   git clone https://github.com/oceanbase/powerrag.git
   cd powerrag
   ```

2. **Configure environment variables**
   
   Navigate to the `docker` directory and copy/edit the environment file:
   ```bash
   cd docker
   cp .env.example .env  # if .env.example exists
   # Edit .env file as needed
   ```

3. **Start services**
   
   Start all services using Docker Compose:
   ```bash
   docker-compose up -d
   ```

   This will start PowerRAG and all its dependent services (including database, storage, etc.).

4. **Check service status**
   ```bash
   docker-compose ps
   ```

   After successful startup, you can access the service at `http://localhost:80` (or the configured port).

For more detailed configuration and usage instructions, see the [Docker Deployment Documentation](docker/README.md).

## Relationship with RAGFlow

PowerRAG Community Edition natively maintains compatibility with RAGFlow's access interfaces and can directly reuse its APIs, SDKs, and documentation system. In the overall architecture, RAGFlow remains the underlying foundational service framework, while PowerRAG Community Edition provides extended capabilities and enhanced components on top of it.

💡 **Note**

PowerRAG Community Edition documentation only covers the new independent capabilities added by PowerRAG Community Edition. For other features and usage methods shared with RAGFlow, please refer to the [RAGFlow official documentation](https://ragflow.io/).

### Architecture

PowerRAG runs as an independent backend service that:

- Shares RAGFlow's database and data models
- Operates on port 6000 (configurable)
- Can run alongside RAGFlow service (port 9380)
- Uses RAGFlow's task executor for asynchronous processing

```
        ┌──────────────┐
        │   Frontend   │
        └──────┬───────┘
               │
        ┌──────┴───────┐
        │              │
        ▼              ▼
┌──────────────┐  ┌──────────────┐
│ RAGFlow      │  │ PowerRAG     │
│ Server       │  │ Server       │
│ (Port 9380)  │  │ (Port 6000)  │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
                ▼
        ┌──────────────┐
        │  OceanBase   │
        │  Database    │
        └──────────────┘
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Development Guide

> **TODO**: Development guide content to be added

---

## Documentation

- **[PowerRAG Community Edition Documentation](https://github.com/oceanbase/powerrag-docs)**: PowerRAG Community Edition product documentation repository

## Support

- **Issue Reporting**: [GitHub Issues](https://github.com/oceanbase/powerrag/issues)
- **Discussions**: [GitHub Discussions](https://github.com/oceanbase/powerrag/discussions)
