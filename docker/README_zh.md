# README

<details open>
<summary></b>📗 目录</b></summary>

- 🐳 [Docker Compose](#-docker-compose)
- 🐬 [Docker 环境变量](#-docker-环境变量)
- 🐋 [服务配置](#-服务配置)
- 📋 [配置示例](#-配置示例)
- 🔧 [故障排除](#-故障排除)

</details>

## 🐳 Docker Compose

本项目提供了以下 docker compose 配置：

- **docker-compose.yml**  
  设置 PowerRAG 及其依赖项的环境，数据库使用 SeekDB。
- **docker-compose-oceanbase.yml**  
  设置 PowerRAG 及其依赖项的环境，数据库使用 OceanBase。
- **docker-compose-self-hosted-ob.yml**  
  设置 PowerRAG 及其依赖项的环境，数据库使用自托管 OceanBase 或 SeekDB。

所有配置都使用 **Docker 命名卷** 来持久化数据，确保跨 Linux、Windows 和 macOS 平台的兼容性。配置文件以只读方式从仓库挂载。

程序默认使用 docker-compose.yml，您可以通过 `docker compose -f` 指定配置文件，例如使用自托管数据库启动服务时，可以使用如下命令：

```shell
docker compose -f docker-compose-self-hosted-ob.yml up -d
```

## 🐬 Docker 环境变量

[.env](./.env) 文件包含 Docker 的重要环境变量。

### 数据库配置

当使用 **docker-compose.yml** 或 **docker-compose-oceanbase.yml** 时，可以设置 `EXPOSE_OB_PORT` 将数据库的 SQL 端口暴露到主机的端口，默认为 `2881`。

#### 使用 SeekDB 容器（docker-compose.yml）

SeekDB 容器支持以下环境变量配置，更多详细信息，请参考 [DockerHub](https://hub.docker.com/r/oceanbase/seekdb)。

```.dotenv
ROOT_PASSWORD=powerrag
MEMORY_LIMIT=6G
LOG_DISK_SIZE=20G
DATAFILE_SIZE=20G
```

#### 使用 OceanBase 容器（docker-compose-oceanbase.yml）

OceanBase 容器支持以下环境变量配置，更多详细信息，请参考 [DockerHub](https://hub.docker.com/r/oceanbase/oceanbase-ce)。

```.dotenv
OB_TENANT_NAME=powerrag
OB_SYS_PASSWORD=powerrag
OB_TENANT_PASSWORD=powerrag
OB_MEMORY_LIMIT=10G
OB_SYSTEM_MEMORY=2G
OB_DATAFILE_SIZE=20G
OB_LOG_DISK_SIZE=20G
```

除了上述容器配置外，您还需要修改如下配置，使得 PowerRAG 服务能够连接到 OceanBase：

```.dotenv
OCEANBASE_USER=root@${OB_TENANT_NAME}
OCEANBASE_PASSWORD=${OB_TENANT_PASSWORD}
```

#### 使用自建数据库（docker-compose-self-hosted-ob.yml）

使用自托管的 OceanBase 或 SeekDB 时，无需设置上述的数据库容器变量，但需要修改以下连接配置。

```.dotenv
OCEANBASE_USER=root
OCEANBASE_PASSWORD=${ROOT_PASSWORD}

OCEANBASE_HOST=oceanbase
OCEANBASE_PORT=2881
OCEANBASE_META_DBNAME=powerrag
OCEANBASE_DOC_DBNAME=powerrag_doc
```

### PowerRAG

- `SVR_WEB_HTTP_PORT` 和 `SVR_WEB_HTTPS_PORT`  
  用于暴露 PowerRAG Web 服务的端口。

- `SVR_HTTP_PORT`  
  用于将 PowerRAG 的 HTTP API 服务暴露到主机的端口。

- `POWERRAG_SVR_HTTP_PORT`  
  用于将 PowerRAG 服务器的 HTTP API 服务暴露到主机的端口。

### 时区

- `TIMEZONE`  
  本地时区。默认为 `'Asia/Shanghai'`。

### Hugging Face 镜像站点

- `HF_ENDPOINT`  
  huggingface.co 的镜像站点。默认禁用。如果您对主要 Hugging Face 域名的访问受限，可以取消注释此行。

### MacOS

- `MACOS`  
  macOS 优化。默认禁用。如果您的操作系统是 macOS，可以取消注释此行。

### 最大文件大小

- `MAX_CONTENT_LENGTH`  
  每个上传文件的最大文件大小，以字节为单位。如果您希望更改 128M 的文件大小限制，可以取消注释此行。更改后，请确保相应地更新 nginx/nginx.conf 中的 `client_max_body_size`。

### 文档批量大小

- `DOC_BULK_SIZE`  
  文档解析期间单批处理的文档块数量。默认为 `4`。

### 嵌入批量大小

- `EMBEDDING_BATCH_SIZE`  
  嵌入向量化期间单批处理的文本块数量。默认为 `16`。

## 📋 配置示例

### 🔒 HTTPS 配置

#### 前置条件

- 指向您服务器的已注册域名
- 服务器上开放端口 80 和 443
- 已安装 Docker 和 Docker Compose

#### 获取和配置证书（Let's Encrypt）

如果您希望您的实例可通过 `https` 访问，请按照以下步骤操作：

1. **安装 Certbot 并获取证书**
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install certbot
   
   # CentOS/RHEL
   sudo yum install certbot
   
   # 获取证书（替换为您的实际域名）
   sudo certbot certonly --standalone -d your-powerrag-domain.com
   ```

2. **定位您的证书**  
   生成后，您的证书将位于：
   - 证书：`/etc/letsencrypt/live/your-powerrag-domain.com/fullchain.pem`
   - 私钥：`/etc/letsencrypt/live/your-powerrag-domain.com/privkey.pem`

3. **更新 docker-compose.yml**  
   在 `docker-compose.yml` 中为 `powerrag` 服务添加证书卷：
   ```yaml
   services:
     powerrag:
       # ...现有配置...
       volumes:
         # SSL 证书
         - /etc/letsencrypt/live/your-powerrag-domain.com/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
         - /etc/letsencrypt/live/your-powerrag-domain.com/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
         # 切换到 HTTPS nginx 配置
         - ./nginx/ragflow.https.conf:/etc/nginx/conf.d/ragflow.conf
         # ...其他现有卷...
  
   ```

4. **更新 nginx 配置**  
   编辑 `nginx/ragflow.https.conf` 并将 `my_powerrag_domain.com` 替换为您的实际域名。

5. **重启服务**
   ```bash
   docker compose down
   docker compose up -d
   ```


> [!IMPORTANT]
> - 确保您域名的 DNS A 记录指向您服务器的 IP 地址
> - 在使用 `--standalone` 获取证书之前，停止在端口 80/443 上运行的任何服务

> [!TIP]
> 对于开发或测试，您可以使用自签名证书，但浏览器会显示安全警告。

#### 替代方案：使用现有证书

如果您已有来自其他提供商的 SSL 证书：

1. 将您的证书放置在 Docker 可访问的目录中
2. 更新 `docker-compose.yml` 中的卷路径以指向您的证书文件
3. 确保证书文件包含完整的证书链
4. 按照上述 Let's Encrypt 指南中的步骤 4-5 操作

## 🔧 故障排除

### 平台特定注意事项

PowerRAG 的 Docker 部署已设计为可在 Linux、Windows 和 macOS 上无缝工作。Docker Compose 文件使用 **命名 Docker 卷** 进行数据持久化，确保跨平台兼容性。

#### Windows

在 Windows 上运行时，请确保：
- 安装并运行 **Docker Desktop**，并启用 WSL 2 后端（推荐）
- 如果遇到配置文件相关的问题，可以检查配置文件（在 `nginx/`、`oceanbase/init.d/` 等目录中）是否使用 **LF 行尾**而不是 CRLF：
  ```bash
  git config core.autocrlf false
  git rm --cached -r .
  git reset --hard
  ```
- 卷挂载中的文件路径由 Docker Desktop 自动处理

#### macOS

在 macOS 上运行时：
- 安装并运行 **Docker Desktop**
- 在您的 `.env` 文件中设置 `MACOS` 环境变量：
  ```dotenv
  MACOS=1
  ```
- 对于 Apple Silicon（M1/M2/M3），Docker 将自动处理平台仿真

#### Linux

Linux 是主要的开发平台，无需额外配置即可工作。

### 卷管理

PowerRAG 使用 Docker 命名卷存储持久化数据（日志、数据库文件、历史数据）。这些卷在容器重启和更新之间保持持久。

#### 多实例部署

Docker Compose 自动为卷名添加项目名称前缀（来自 `.env` 中的 `COMPOSE_PROJECT_NAME`，默认为 `powerrag`）。这允许在同一台机器上运行多个部署而不会发生冲突：

**卷命名示例：**
- 使用 `COMPOSE_PROJECT_NAME=powerrag`：卷名变为 `powerrag_powerrag_logs`、`powerrag_oceanbase_data` 等
- 使用 `COMPOSE_PROJECT_NAME=powerrag-dev`：卷名变为 `powerrag-dev_powerrag_logs`、`powerrag-dev_oceanbase_data` 等

**运行多个部署的方法：**
1. 为每个部署创建单独的目录
2. 在每个目录的 `.env` 文件中设置唯一的 `COMPOSE_PROJECT_NAME`：
   ```dotenv
   COMPOSE_PROJECT_NAME=powerrag-production
   # 或
   COMPOSE_PROJECT_NAME=powerrag-dev
   ```
3. 每个部署将拥有自己独立的卷集

#### 列出卷

查看所有 PowerRAG 相关的卷：
```bash
docker volume ls | grep powerrag
```

#### 备份卷

在清理或升级之前，您可能需要备份数据：

```bash
# 备份所有 PowerRAG 卷
docker run --rm -v powerrag_powerrag_logs:/data -v $(pwd)/backup:/backup alpine tar czf /backup/powerrag_logs.tar.gz -C /data .
docker run --rm -v powerrag_oceanbase_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/oceanbase_data.tar.gz -C /data .
docker run --rm -v powerrag_powerrag_history_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/history_data.tar.gz -C /data .
```

#### 清理卷

> [!WARNING]
> 删除卷将永久删除所有数据，包括日志、数据库内容和历史记录。请确保先备份重要数据。

**删除所有 PowerRAG 卷和数据：**

```bash
# 停止并删除所有容器
docker compose down

# 删除所有 PowerRAG 卷
docker compose down -v

# 或手动删除特定卷
docker volume rm powerrag_powerrag_logs powerrag_oceanbase_data powerrag_powerrag_history_data
```

**清理后重新启动：**

```bash
docker compose up -d
```

#### 查看日志和数据

**查看运行中容器的日志：**

```bash
# 查看 PowerRAG 服务日志
docker compose logs -f powerrag

# 查看 OceanBase 数据库日志
docker compose logs -f oceanbase

# 查看所有服务日志
docker compose logs -f
```

**访问卷中的日志和数据：**

```bash
# 查看卷中的日志文件
docker run --rm -v powerrag_powerrag_logs:/data alpine ls -la /data

# 读取特定日志文件
docker run --rm -v powerrag_powerrag_logs:/data alpine cat /data/ragflow.log

# 以交互方式访问卷数据
docker run --rm -it -v powerrag_oceanbase_data:/data alpine sh
```

**将文件从卷复制到主机：**

```bash
# 将日志从卷复制到当前目录
docker run --rm -v powerrag_powerrag_logs:/data -v $(pwd):/backup alpine cp -r /data /backup/logs

# 复制数据库数据
docker run --rm -v powerrag_oceanbase_data:/data -v $(pwd):/backup alpine cp -r /data /backup/db_data
```

### 端口已被占用错误

如果您遇到类似以下的错误：
```
Error response from daemon: driver failed programming external connectivity on endpoint powerrag-oceanbase-1: Bind for 0.0.0.0:2881 failed: port is already allocated
```

此错误发生在 Docker 保留了先前容器运行的过时端口绑定时，即使使用 `netstat` 或 `lsof` 检查时端口显示为空闲。

**解决方案 1：清理 Docker 资源（推荐）**

运行以下命令清理任何孤立的容器和网络：

```bash
# 停止此项目的所有容器
docker compose down

# 删除孤立的容器
docker compose down --remove-orphans

# 如果问题仍然存在，清理 Docker 网络
docker network prune -f

# 重启服务
docker compose up -d
```

**解决方案 2：更改端口**

如果您需要使用不同的端口，编辑 `.env` 文件并更改 `EXPOSE_OB_PORT` 变量：

```dotenv
EXPOSE_OB_PORT=2882  # 从默认的 2881 更改为其他端口
```

然后重启服务：

```bash
docker compose down
docker compose up -d
```

**解决方案 3：重启 Docker 守护进程**

如果上述解决方案都不起作用，重启 Docker 守护进程：

```bash
# 在使用 systemd 的 Linux 上
sudo systemctl restart docker

# 在 macOS/Windows 上，从应用程序重启 Docker Desktop
```

然后再次尝试启动服务：

```bash
docker compose up -d
```

