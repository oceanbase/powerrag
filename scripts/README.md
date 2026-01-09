# RAGFlow 脚本使用指南

本目录包含 RAGFlow 的运维部署脚本，用于管理服务部署。

## 脚本说明

### 1. `deploy.sh` - 运维部署脚本（已按 `docker/entrypoint.sh` 重构）

现在 `deploy.sh` 采用 **entrypoint 风格的组件开关参数**，用 `start/stop/status` 作为动作，用 `--enable/--disable/--xxx=` 作为配置。

**支持的动作：**
- `start` - 启动组件（默认启动 `webserver + taskexecutor`；datasync 默认不启动）
- `stop` - 停止本脚本启动的组件（基于 `pids/`）
- `restart` - stop + start
- `status` - 查看状态
- `force-stop` - 强制停止相关进程（不依赖 PID 文件，谨慎使用）
- `help` - 查看帮助

**主要组件开关（对齐 `docker/entrypoint.sh`）：**
- `--enable-webserver` - 启动 WebServer（`ragflow_server` + 可选 nginx 前端）
- `--disable-webserver` - 不启动 WebServer（`ragflow_server` + 可选 nginx 前端）
- `--enable-taskexecutor` - 启动 task executor
- `--disable-taskexecutor` - 不启动 task executor
- `--enable-datasync` - 启动 datasource sync（默认不启动）
- `--disable-datasync` - 不启动 datasource sync
- `--enable-mcpserver` - 启动 MCP Server
- `--enable-adminserver` - 启动 Admin Server
- `--enable-powerragserver` - 启动 PowerRAG Server

> 规则：如果 `start` 时带了任意 `--enable-*` 参数，则进入 **enable-only 模式**：只启动被 enable 的组件，其它组件都不会启动。  
> 不带任何 `--enable-*` 时，走默认模式：启动 `webserver + taskexecutor`。

**多 ragflow_server 支持（对齐 `docker/entrypoint.sh`）：**
- `--svr-count=<num>`：实例数（默认 1）
- `--svr-http-port=<num>`：实例 0 端口（默认 9380）
- `--svr-extra-base-http-port=<num>`：实例 1..N 端口基数（默认 9400，即 9400、9401...）

  **注意**：ragflow_server 端口不能与 admin-svr-http-port、mcp-port、powerrag-port、web-port 冲突。脚本会在启动前检查端口冲突并报错。
- `--admin-svr-http-port=<num>`：写入生成的配置 `admin.http_port`（默认 9381）
- `--service-conf=<filename>`：基础配置文件（默认 `conf/service_conf.yaml`）

> 说明：脚本会在 `conf/` 下生成 `service_conf_ragflow_<idx>.yaml`，并通过环境变量 `RAGFLOW_SERVICE_CONF` 启动对应实例。

**Task Executor（消费者）配置：**
- `--consumer-no-beg=<num>`
- `--consumer-no-end=<num>`：半开区间 `[beg, end)`
- `--workers=<num>`：如果未指定 range，则启动固定数量 worker（默认 1）
- `--host-id=<string>`：默认 `hostname`（长度 > 32 则 md5）

**MCP 配置：**
- `--mcp-host=<ip>`
- `--mcp-port=<num>`
- `--mcp-base-url=<url>`
- `--mcp-mode=<self-host|hosted>`
- `--mcp-host-api-key=<string>`
- `--no-transport-sse-enabled`
- `--no-transport-streamable-http-enabled`
- `--no-json-response`

**PowerRAG 配置：**
- `--powerrag-port=<num>`（默认 6000）

**兼容性：**
- 不再提供单独的 `start-web/stop-web` 命令；前端 nginx（静态 + 反代 API）随 `webserver` 一起启动。

## 快速开始

### 运维部署（deploy.sh）

```bash
# 启动默认组件：webserver + taskexecutor（datasync 默认不启动）
./scripts/deploy.sh start

# 查看状态
./scripts/deploy.sh status

# 停止
./scripts/deploy.sh stop

# 强制停止（不依赖 pid 文件，谨慎使用）
./scripts/deploy.sh force-stop

# 清理运行时生成文件（会先 stop，再删除 logs/、pids/、nginx_conf/、conf/service_conf_ragflow_*.yaml）
./scripts/deploy.sh clear
```

#### 启动多个 ragflow_server 和 多个 task executors
```bash
./scripts/deploy.sh start \
  --svr-count=2 \
  --svr-http-port=9380 \
  --svr-extra-base-http-port=9400 \
  --workers=2
```

#### 仅启动 ragflow_server（不启动 worker/datasync）

```bash
./scripts/deploy.sh start --enable-webserver
```

#### 启动多个 ragflow_server 实例（多端口）

```bash
./scripts/deploy.sh start \
  --enable-webserver
  --svr-count=3 \
  --svr-http-port=9380 \
  --svr-extra-base-http-port=9400 
```

#### 启动 task executors（固定数量）

```bash
./scripts/deploy.sh start --enable-taskexecutor --workers=2
```

#### 启动 task executors（range 模式）

```bash
./scripts/deploy.sh start --enable-taskexecutor\
  --consumer-no-beg=0 --consumer-no-end=5 \
  --host-id=myhost123
```

#### 启动 MCP / Admin / PowerRAG

```bash
./scripts/deploy.sh start --enable-mcpserver --enable-adminserver --enable-powerragserver
./scripts/deploy.sh start --enable-powerragserver --powerrag-port=6000
```

## 日志与 PID

### 服务日志（默认在 `logs/`）

**注意**：服务日志由各服务通过 `init_root_logger()` 自行管理，脚本不再重复记录日志。

- `logs/ragflow_server_{port}.log` - RAGFlow 服务日志（按端口号区分，例如：`logs/ragflow_server_9380.log`）
- `logs/task_executor_{id}.log` - Task executor 日志（例如：`logs/task_executor_0.log`）
- `logs/data_sync_{consumer_no}.log` - Data sync 日志
- `logs/admin_service.log` - Admin 服务日志
- `logs/powerrag_server.log` - PowerRAG 服务日志
- `logs/nginx_access.log` - Nginx 访问日志
- `logs/nginx_error.log` - Nginx 错误日志
- `logs/web_frontend.log` - Nginx 启动日志（仅启动时的输出）

### PID 文件（默认在 `pids/`）

- `pids/ragflow_server_<port>.pid`
- `pids/task_executor_<id>.pid`
- `pids/datasync.pid`
- `pids/admin_server.pid`
- `pids/mcp_server.pid`
- `pids/powerrag_server.pid`
- `pids/web_frontend.pid`

## 查看日志

```bash
# RAGFlow 服务（根据端口号）
tail -f logs/ragflow_server_9380.log
tail -f logs/ragflow_server_9400.log  # 如果有多个实例

# Task executor（根据实际的 host_id 和 consumer_id）
# Task executor（worker id）
tail -f logs/task_executor_0.log

# Data sync
tail -f logs/data_sync_0.log

# Admin 服务
tail -f logs/admin_service.log

# PowerRAG 服务
tail -f logs/powerrag_server.log

# Nginx 日志
tail -f logs/nginx_access.log
tail -f logs/nginx_error.log
```

## 注意事项

1. 推荐从项目根目录运行：`./scripts/deploy.sh ...`
2. `force-stop` 会强制 kill 相关进程，请谨慎使用
3. 多实例 `ragflow_server` 通过 `RAGFLOW_SERVICE_CONF` 启动，不再需要替换 `local.service_conf.yaml`
4. **端口配置**：设置 ragflow_server 端口时，需要预留 admin-svr-http-port（默认 9381）、mcp-port（默认 9382）等端口，避免冲突。脚本会在启动前检查并报错。
