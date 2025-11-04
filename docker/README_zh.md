# README

<details open>
<summary></b>📗 目录</b></summary>

- 🐳 [Docker Compose](#-docker-compose)
- 🐬 [Docker 环境变量](#-docker-环境变量)
- 🐋 [服务配置](#-服务配置)
- 📋 [配置示例](#-配置示例)

</details>

## 🐳 Docker Compose

- **docker-compose.yml**  
  设置 PowerRAG 及其依赖项的环境。
- **docker-compose-self-hosted-ob.yml**  
  设置使用自托管 OceanBase 的 PowerRAG 环境。

## 🐬 Docker 环境变量

[.env](./.env) 文件包含 Docker 的重要环境变量。

### OceanBase

- `EXPOSE_OB_PORT`  
  用于将 OceanBase 容器服务暴露到主机的端口，允许**外部**访问 Docker 容器内运行的服务。默认为 `2881`。

- `OB_XXX`  
  这些以 `OB_` 开头的环境变量用于设置 OceanBase Docker 容器的启动参数。更多详细信息，请参考 [DockerHub](https://hub.docker.com/r/oceanbase/oceanbase-ce)。

请注意，如果您想使用自托管的 OceanBase，则无需关心上述变量，但应修改以下以 `OCEANBASE_` 开头的变量。

```.dotenv
OCEANBASE_HOST=oceanbase
OCEANBASE_PORT=2881
OCEANBASE_USER=root@${OB_TENANT_NAME}
OCEANBASE_PASSWORD=${OB_TENANT_PASSWORD}
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
   docker-compose down
   docker-compose up -d
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

