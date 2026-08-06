> [!IMPORTANT]
> **维护说明**
>
> PowerRAG 社区版已停止维护。OceanBase 相关功能及后续优化将统一在官方 [RAGFlow](https://github.com/infiniflow/ragflow) 项目中持续推进。**请迁移至 RAGFlow，以获取后续更新与支持。**

<p align="center">
    <a href="https://github.com/oceanbase/powerrag">
        <img alt="PowerRAG Logo" src="https://img.shields.io/badge/PowerRAG-blue" width="50%" />
    </a>
</p>

<p align="center">
  <a href="https://github.com/oceanbase/powerrag">GitHub</a>
  ·
  <a href="https://github.com/oceanbase/powerrag/issues">问题反馈</a>
  ·
  <a href="https://github.com/oceanbase/powerrag/discussions">讨论区</a>
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

## 简介

PowerRAG 社区版（PowerRAG Community Edition）是一款基于 [RAGFlow](https://github.com/infiniflow/ragflow) 二次开发的开源项目，采用 Apache License 2.0 协议。该项目在保留 RAGFlow 核心能力与接口兼容性的基础上，进一步扩展了文档处理、结构化信息提取，以及效果评估与反馈等功能，旨在为大模型（LLM）应用提供更完整的一体化数据服务引擎。

PowerRAG 社区版面向需要构建 RAG（Retrieval-Augmented Generation）应用的开发者与研究团队，通过原子化 API 设计，使其可灵活嵌入各类智能应用中，支持快速构建、监控与优化基于大模型的问答、知识抽取与生成系统。

## 功能亮点介绍

### 文档服务

PowerRAG 在 RAGFlow 的文档处理能力之上，新增多引擎与多模式支持，适用于更复杂的文档场景：

- **多引擎 OCR 支持**: 集成 MinerU 和 Dots.OCR，支持复杂文档的识别与文本抽取
- **多种切片策略**: 支持基于标题、正则表达式及智能切片算法的分片方式，提升内容组织与检索效率
- **结构化信息提取**: 基于 [LangExtract](https://github.com/google/langextract) 实现结构化信息识别与抽取，支持从文档中提取表格、字段、实体等结构化内容，为知识图谱与语义检索提供数据基础

### 混合检索

PowerRAG 应用平台构建于 OceanBase 多模一体化数据库架构（SQL + NoSQL）之上，充分利用 OceanBase 的高性能、可扩展性和混合存储能力，为智能检索与知识服务提供高性能的底层支撑。

- **混合索引检索**: 在 OceanBase 4.4.1 版本能力的支持下，实现向量索引与全文索引的联合查询，结合语义相关性与关键词匹配，提升信息召回的全面性与精准度
- **多模数据检索**: 在向量检索基础上引入标量条件，可在语义结果中进一步执行基于数值、时间或分类属性的过滤，实现精确控制的结果排序与筛选
- **统一数据访问层**: 通过 OceanBase 的多模一体化接口，统一管理文本、向量与结构化数据，实现跨模态、跨类型的高效查询

这一能力使 PowerRAG 能够在多类型知识源和复杂检索场景下提供更灵活的知识访问模式，为大模型应用提供高效、可扩展的底层数据支撑。

### 效果评估与反馈

PowerRAG 社区版引入了效果评估与反馈模块，该模块基于 [Langfuse](https://github.com/oceanbase/langfuse) 实现，用于帮助开发者系统化地衡量和优化 LLM 应用的效果，形成可观测、可分析、可改进的闭环体系。在引入该组件时，PowerRAG 社区版增加了本地化的适配、Qwen 模型对接等工作，并实现了与 PowerRAG 的适配度桥接器，确保组件能够无缝集成到 PowerRAG 生态系统中。该模块包括以下核心能力：

- **可观测性（Observability）**: 提供端到端调用链追踪与性能分析。开发者可以全面了解模型推理的全过程，包括输入输出、工具调用、重试过程、延迟情况及调用成本，从而支持模型性能优化与成本控制
- **提示词管理（Prompt Management）**: 支持提示词的存储、版本管理与检索，便于团队进行提示词调优、共享与复用，实现提示设计的标准化和可追踪性
- **评估能力（Evaluation）**: 提供多种评估方法，支持在不同阶段对模型输出进行效果验证和质量对比，帮助团队实现持续优化和自动化测试

通过该模块，PowerRAG 能够在模型开发与应用过程中实现从数据输入、提示设计到效果评估的完整反馈闭环，助力团队提升模型可解释性与应用质量。

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- 至少 8GB 可用内存

### 安装与启动

1. **克隆仓库**
   ```bash
   git clone https://github.com/oceanbase/powerrag.git
   cd powerrag
   ```

2. **配置环境变量**
   
   进入 `docker` 目录，复制并编辑环境变量文件：
   ```bash
   cd docker
   cp .env.example .env  # 如果存在 .env.example
   # 根据需要编辑 .env 文件
   ```

3. **启动服务**
   
   使用 Docker Compose 启动所有服务：
   ```bash
   docker-compose up -d
   ```

   这将启动 PowerRAG 及其所有依赖服务（包括数据库、存储等）。

4. **查看服务状态**
   ```bash
   docker-compose ps
   ```

   启动成功后，可以通过 `http://localhost:80` (或配置的端口) 来访问。

更多详细配置和使用说明，请参阅 [Docker 部署文档](docker/README_zh.md)。

## 与 RAGFlow 的关系

PowerRAG 社区版原生兼容 RAGFlow 的访问接口，可直接复用其 API、SDK 及文档体系。在整体架构中，RAGFlow 仍作为底层基础服务框架，而 PowerRAG 社区版在此基础上提供扩展能力与增强组件。

💡 **说明**

PowerRAG 社区版文档仅介绍 PowerRAG 社区版新增的独立能力。其他与 RAGFlow 通用的功能和使用方法，请参考 [RAGFlow 官方文档](https://ragflow.io/)。

### 架构说明

PowerRAG 作为独立的后端服务运行：

- 共享 RAGFlow 的数据库和数据模型
- 运行在端口 6000（可配置）
- 可与 RAGFlow 服务（端口 9380）同时运行
- 使用 RAGFlow 的任务执行器进行异步处理

```
        ┌──────────────┐
        │  前端界面     │
        └──────┬───────┘
               │
        ┌──────┴───────┐
        │              │
        ▼              ▼
┌──────────────┐  ┌──────────────┐
│ RAGFlow 服务 │  │ PowerRAG 服务│
│ (端口 9380)  │  │ (端口 6000)  │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
                ▼
        ┌──────────────┐
        │  OceanBase   │
        │   数据库     │
        └──────────────┘
```

## License

本项目采用 Apache License 2.0 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

## 开发手册

对于想要从源码构建和运行 PowerRAG 的开发者：

- **[开发者部署手册](docs/developer-setup-guide-zh.md)**: 从源码部署 PowerRAG 的完整指南


---

## 相关文档

- **[PowerRAG 社区版文档](https://github.com/oceanbase/powerrag-docs)**: PowerRAG 社区版产品文档仓库

## 支持

- **问题反馈**: [GitHub Issues](https://github.com/oceanbase/powerrag/issues)
- **讨论区**: [GitHub Discussions](https://github.com/oceanbase/powerrag/discussions)
