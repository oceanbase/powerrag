# RAGFlow 脚本使用指南

本目录包含 RAGFlow 的运维部署脚本和工具脚本，用于管理服务部署和数据处理任务。

## 脚本说明

### 1. `deploy.sh` - 运维部署脚本

用于管理 RAGFlow Server 和 Worker 的启动、停止、重启等运维操作。

**支持的命令：**
- `start` - 启动所有服务（Server + Workers）
- `stop` - 停止所有服务
- `restart` - 重启所有服务
- `force-stop` - 强制停止所有相关进程（不依赖 PID 文件）
- `force-restart` - 强制重启所有服务
- `status` - 查看服务状态
- `start-ragflow-server` - 仅启动 Ragflow Server
- `stop-ragflow-server` - 仅停止 Ragflow Server
- `start-web` - 启动 Web 前端（正式环境：build + 静态服务）
- `stop-web` - 停止 Web 前端

### 2. `tools.sh` - 工具脚本

用于执行数据上传和处理相关的工具任务。

**支持的命令：**
- `upload-wiki` - 上传 Wiki JSON 数据（后台运行，支持断点续传）
- `stop-upload-wiki` - 停止 Wiki JSON 上传任务
- `reparse-failed` - 重新解析指定数据集中失败的文档
- `stop-reparse-failed` - 停止重新解析失败文档任务
- `status` - 查看工具任务状态

## 快速开始

### 运维部署

```bash
# 从项目根目录运行
# 启动所有服务（默认 2 个 Workers）
./scripts/deploy.sh start

# 启动指定数量的 Workers
WORKER_COUNT=64 ./scripts/deploy.sh start

# 停止所有服务
./scripts/deploy.sh stop

# 重启所有服务
./scripts/deploy.sh restart

# 查看服务状态
./scripts/deploy.sh status

# 仅启动/停止 Ragflow Server
./scripts/deploy.sh start-ragflow-server
./scripts/deploy.sh stop-ragflow-server

# 启动/停止 Web 前端（正式环境）
WEB_PORT=9222 SERVER_PORT_FOR_WEB=9380 ./scripts/deploy.sh start-web
./scripts/deploy.sh stop-web
```

或者从 scripts 目录运行：

```bash
cd scripts
./deploy.sh start
```

### 工具脚本

```bash
# 上传 Wiki JSON 数据
./scripts/tools.sh upload-wiki

# 使用自定义参数上传
API_KEY=xxx HOST=xxx WIKI_DATA_DIR=xxx BATCH_SIZE=1000 ./scripts/tools.sh upload-wiki
WIKI_ENABLE_RESUME=false ./scripts/tools.sh upload-wiki

# 停止上传任务
./scripts/tools.sh stop-upload-wiki

# 重新解析失败的文档（需要设置数据集 ID）
API_KEY=xxx HOST=xxx DATASET_ID=xxx BATCH_SIZE=1000 ./scripts/tools.sh reparse-failed

# 停止重新解析任务
./scripts/tools.sh stop-reparse-failed

# 查看工具任务状态
./scripts/tools.sh status
```

## 环境变量配置

### 运维部署相关

- `WORKER_COUNT` - Worker 数量（默认: 2）
- `SERVER_PORT_FOR_WEB` - Ragflow Server 端口（默认: 9385）
- `WEB_PORT` - Web 前端端口（默认: 9222）

### Wiki 上传相关

- `API_KEY` - API Key（默认: ragflow-HeewVgbFXZ1xiebiiHEzhxmZAQb-kOLXBa5WxEVe0JU）
- `HOST` - 服务器地址（默认: http://6.13.51.232:9385）
- `WIKI_DATA_DIR` - 数据目录（默认: /data/keyang.lk/data/bailing/wiki_zh_20250901_json）
- `DATASET_ID` - 数据集 ID（可选）
- `BATCH_SIZE` - 批量大小（默认: 1000）
- `WIKI_SNAPSHOT_FILE` - 快照文件路径（默认: `${LOG_DIR}/upload_snapshot.json`）
- `WIKI_ENABLE_RESUME` - 是否启用断点续传（默认: true）

### 重新解析失败文档相关

- `API_KEY` - API Key（默认: ragflow-HeewVgbFXZ1xiebiiHEzhxmZAQb-kOLXBa5WxEVe0JU）
- `HOST` - 服务器地址（默认: http://6.13.51.232:9385）
- `DATASET_ID` - 数据集 ID（必需）
- `BATCH_SIZE` - 批量大小（默认: 50）

## 日志文件

### 服务日志

- Ragflow Server: `logs/ragflow_server.log`
- Worker N: `logs/worker_N.log`
- Web Frontend: `logs/web_frontend.log`

### 工具任务日志

- Wiki JSON 上传: `logs/upload_wiki_json.log`
- 重新解析失败文档: `logs/reparse_failed_docs.log`

## 查看日志

```bash
# 实时查看 Ragflow Server 日志
tail -f logs/ragflow_server.log

# 实时查看 Worker 0 日志
tail -f logs/worker_0.log

# 实时查看 Wiki 上传日志
tail -f logs/upload_wiki_json.log

# 实时查看重新解析日志
tail -f logs/reparse_failed_docs.log
```

## 停止服务

```bash
# 使用脚本停止（推荐）
./scripts/deploy.sh stop

# 强制停止（不依赖 PID 文件）
./scripts/deploy.sh force-stop

# 手动查找并停止进程
ps aux | grep ragflow_server.py
ps aux | grep task_executor.py
kill <PID>
```

## PID 文件

所有脚本使用 PID 文件来跟踪进程状态，PID 文件存储在 `pids/` 目录下：

- `pids/ragflow_server.pid` - Ragflow Server 进程 ID
- `pids/worker_N.pid` - Worker N 进程 ID
- `pids/web_frontend.pid` - Web 前端进程 ID
- `pids/upload_wiki_json.pid` - Wiki 上传任务进程 ID
- `pids/reparse_failed_docs.pid` - 重新解析任务进程 ID

## 注意事项

1. 所有脚本都需要从项目根目录运行，或确保 `WORKSPACE_FOLDER` 环境变量正确设置
2. 使用 `force-stop` 或 `force-restart` 会强制终止所有相关进程，请谨慎使用
3. Wiki 上传任务支持断点续传，默认启用。快照文件保存在 `${LOG_DIR}/upload_snapshot.json`
4. 重新解析失败文档任务需要设置 `DATASET_ID` 环境变量
5. 所有日志文件都保存在 `logs/` 目录下
