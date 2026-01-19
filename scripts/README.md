# RAGFlow 脚本使用指南

本目录包含 RAGFlow 的运维部署脚本，用于管理服务部署。

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

## 环境变量配置

### 运维部署相关

- `WORKER_COUNT` - Worker 数量（默认: 2）
- `SERVER_PORT_FOR_WEB` - Ragflow Server 端口（默认: 9380）
- `WEB_PORT` - Web 前端端口（默认: 9222）

## 日志文件

### 服务日志

- Ragflow Server: `logs/ragflow_server.log`
- Worker N: `logs/worker_N.log`
- Web Frontend: `logs/web_frontend.log`

## 查看日志

```bash
# 实时查看 Ragflow Server 日志
tail -f logs/ragflow_server.log

# 实时查看 Worker 0 日志
tail -f logs/worker_0.log
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

## 注意事项

1. 所有脚本都需要从项目根目录运行，或确保 `WORKSPACE_FOLDER` 环境变量正确设置
2. 使用 `force-stop` 或 `force-restart` 会强制终止所有相关进程，请谨慎使用
3. 所有日志文件都保存在 `logs/` 目录下
