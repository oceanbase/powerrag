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

