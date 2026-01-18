# README

<details open>
<summary></b>📗 Table of Contents</b></summary>

- 🐳 [Docker Compose](#-docker-compose)
- 🐬 [Docker environment variables](#-docker-environment-variables)
- 🐋 [Service configuration](#-service-configuration)
- 📋 [Setup Examples](#-setup-examples)
- 🔧 [Troubleshooting](#-troubleshooting)

</details>

## 🐳 Docker Compose

This project provides the following docker compose configurations:

- **docker-compose.yml**  
  Sets up environment for PowerRAG and its dependencies, using SeekDB as the database.
- **docker-compose-oceanbase.yml**  
  Sets up environment for PowerRAG and its dependencies, using OceanBase as the database.
- **docker-compose-self-hosted-ob.yml**  
  Sets up environment for PowerRAG and its dependencies, using self-hosted OceanBase or SeekDB as the database.

The program uses docker-compose.yml by default. You can specify a configuration file using `docker compose -f`. For example, when starting services with a self-hosted database, you can use the following command:

```shell
docker compose -f docker-compose-self-hosted-ob.yml up -d
```

## 🐬 Docker environment variables

The [.env](./.env) file contains important environment variables for Docker.

### Database configuration

When using **docker-compose.yml** or **docker-compose-oceanbase.yml**, you can set `EXPOSE_OB_PORT` to expose the database's SQL port to the host machine's port, defaulting to `2881`.

#### Using SeekDB container (docker-compose.yml)

The SeekDB container supports the following environment variable configurations. For more details, please refer to [DockerHub](https://hub.docker.com/r/oceanbase/seekdb).

```.dotenv
ROOT_PASSWORD=powerrag
MEMORY_LIMIT=6G
LOG_DISK_SIZE=20G
DATAFILE_SIZE=20G
```

#### Using OceanBase container (docker-compose-oceanbase.yml)

The OceanBase container supports the following environment variable configurations. For more details, please refer to [DockerHub](https://hub.docker.com/r/oceanbase/oceanbase-ce).

```.dotenv
OB_TENANT_NAME=powerrag
OB_SYS_PASSWORD=powerrag
OB_TENANT_PASSWORD=powerrag
OB_MEMORY_LIMIT=10G
OB_SYSTEM_MEMORY=2G
OB_DATAFILE_SIZE=20G
OB_LOG_DISK_SIZE=20G
```

In addition to the container configurations above, you also need to modify the following configuration to allow PowerRAG services to connect to OceanBase:

```.dotenv
OCEANBASE_USER=root@${OB_TENANT_NAME}
OCEANBASE_PASSWORD=${OB_TENANT_PASSWORD}
```

#### Using self-hosted database (docker-compose-self-hosted-ob.yml)

When using self-hosted OceanBase or SeekDB, you do not need to set the database container variables above, but you need to modify the following connection configuration.

```.dotenv
OCEANBASE_USER=root
OCEANBASE_PASSWORD=${ROOT_PASSWORD}

OCEANBASE_HOST=oceanbase
OCEANBASE_PORT=2881
OCEANBASE_META_DBNAME=powerrag
OCEANBASE_DOC_DBNAME=powerrag_doc
```

### PowerRAG

- `SVR_WEB_HTTP_PORT` and `SVR_WEB_HTTPS_PORT`  
  The ports used to expose the PowerRAG's web service.

- `SVR_HTTP_PORT`  
  The port used to expose PowerRAG's HTTP API service to the host machine.

- `POWERRAG_SVR_HTTP_PORT`  
  The port used to expose PowerRAG server's HTTP API service to the host machine.

### Timezone

- `TIMEZONE`  
  The local time zone. Defaults to `'Asia/Shanghai'`.

### Hugging Face mirror site

- `HF_ENDPOINT`  
  The mirror site for huggingface.co. It is disabled by default. You can uncomment this line if you have limited access to the primary Hugging Face domain.

### MacOS

- `MACOS`  
  Optimizations for macOS. It is disabled by default. You can uncomment this line if your OS is macOS.

### Maximum file size

- `MAX_CONTENT_LENGTH`  
  The maximum file size for each uploaded file, in bytes. You can uncomment this line if you wish to change the 128M file size limit. After making the change, ensure you update `client_max_body_size` in nginx/nginx.conf correspondingly.

### Doc bulk size

- `DOC_BULK_SIZE`  
  The number of document chunks processed in a single batch during document parsing. Defaults to `4`.

### Embedding batch size

- `EMBEDDING_BATCH_SIZE`  
  The number of text chunks processed in a single batch during embedding vectorization. Defaults to `16`.

## 📋 Setup Examples

### 🔒 HTTPS Setup

#### Prerequisites

- A registered domain name pointing to your server
- Port 80 and 443 open on your server
- Docker and Docker Compose installed

#### Getting and configuring certificates (Let's Encrypt)

If you want your instance to be available under `https`, follow these steps:

1. **Install Certbot and obtain certificates**
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install certbot
   
   # CentOS/RHEL
   sudo yum install certbot
   
   # Obtain certificates (replace with your actual domain)
   sudo certbot certonly --standalone -d your-powerrag-domain.com
   ```

2. **Locate your certificates**  
   Once generated, your certificates will be located at:
   - Certificate: `/etc/letsencrypt/live/your-powerrag-domain.com/fullchain.pem`
   - Private key: `/etc/letsencrypt/live/your-powerrag-domain.com/privkey.pem`

3. **Update docker-compose.yml**  
   Add the certificate volumes to the `powerrag` service in your `docker-compose.yml`:
   ```yaml
   services:
     powerrag:
       # ...existing configuration...
       volumes:
         # SSL certificates
         - /etc/letsencrypt/live/your-powerrag-domain.com/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
         - /etc/letsencrypt/live/your-powerrag-domain.com/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
         # Switch to HTTPS nginx configuration
         - ./nginx/ragflow.https.conf:/etc/nginx/conf.d/ragflow.conf
         # ...other existing volumes...
  
   ```

4. **Update nginx configuration**  
   Edit `nginx/ragflow.https.conf` and replace `my_powerrag_domain.com` with your actual domain name.

5. **Restart the services**
   ```bash
   docker compose down
   docker compose up -d
   ```


> [!IMPORTANT]
> - Ensure your domain's DNS A record points to your server's IP address
> - Stop any services running on ports 80/443 before obtaining certificates with `--standalone`

> [!TIP]
> For development or testing, you can use self-signed certificates, but browsers will show security warnings.

#### Alternative: Using existing certificates

If you already have SSL certificates from another provider:

1. Place your certificates in a directory accessible to Docker
2. Update the volume paths in `docker-compose.yml` to point to your certificate files
3. Ensure the certificate file contains the full certificate chain
4. Follow steps 4-5 from the Let's Encrypt guide above

## 🔧 Troubleshooting

### Port Already Allocated Error

If you encounter an error like:
```
Error response from daemon: driver failed programming external connectivity on endpoint powerrag-oceanbase-1: Bind for 0.0.0.0:2881 failed: port is already allocated
```

This error occurs when Docker has stale port bindings from previous container runs, even if the port appears free when checked with `netstat` or `lsof`.

**Solution 1: Clean up Docker resources (Recommended)**

Run the following commands to clean up any orphaned containers and networks:

```bash
# Stop all containers from this project
docker compose down

# Remove orphaned containers
docker compose down --remove-orphans

# If the issue persists, prune Docker networks
docker network prune -f

# Restart the services
docker compose up -d
```

**Solution 2: Change the port**

If you need to use a different port, edit the `.env` file and change the `EXPOSE_OB_PORT` variable:

```dotenv
EXPOSE_OB_PORT=2882  # Change from default 2881 to another port
```

Then restart the services:

```bash
docker compose down
docker compose up -d
```

**Solution 3: Restart Docker daemon**

If the above solutions don't work, restart the Docker daemon:

```bash
# On Linux with systemd
sudo systemctl restart docker

# On macOS/Windows, restart Docker Desktop from the application
```

Then try starting the services again:

```bash
docker compose up -d
```