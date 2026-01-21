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

All configurations use **Docker named volumes** for data persistence, ensuring cross-platform compatibility across Linux, Windows, and macOS. Configuration files are mounted as read-only from the repository.

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

### Platform-Specific Considerations

PowerRAG's Docker deployment has been designed to work across Linux, Windows, and macOS. The Docker Compose files use **named Docker volumes** for data persistence, which ensures cross-platform compatibility.

#### Windows

When running on Windows, ensure:
- **Docker Desktop** is installed and running with WSL 2 backend enabled (recommended)
- If you encounter issues with configuration files, check that configuration files (in `nginx/`, `oceanbase/init.d/`, etc.) use **LF line endings** instead of CRLF:
  ```bash
  git config core.autocrlf false
  git rm --cached -r .
  git reset --hard
  ```
- File paths in volume mounts are handled automatically by Docker Desktop

#### macOS

When running on macOS:
- **Docker Desktop** is installed and running
- Set the `MACOS` environment variable in your `.env` file:
  ```dotenv
  MACOS=1
  ```
- For Apple Silicon (M1/M2/M3), Docker will automatically handle platform emulation

#### Linux

Linux is the primary development platform and should work without additional configuration.

### Volume Management

PowerRAG uses Docker named volumes to store persistent data (logs, database files, history data). These volumes persist across container restarts and updates.

#### Multiple Deployments

Docker Compose automatically prefixes volume names with the project name (from `COMPOSE_PROJECT_NAME` in `.env`, default is `powerrag`). This allows multiple deployments on the same machine without conflicts:

**Example volume naming:**
- With `COMPOSE_PROJECT_NAME=powerrag`: volumes become `powerrag_powerrag_logs`, `powerrag_oceanbase_data`, etc.
- With `COMPOSE_PROJECT_NAME=powerrag-dev`: volumes become `powerrag-dev_powerrag_logs`, `powerrag-dev_oceanbase_data`, etc.

**To run multiple deployments:**
1. Create separate directories for each deployment
2. In each directory's `.env` file, set a unique `COMPOSE_PROJECT_NAME`:
   ```dotenv
   COMPOSE_PROJECT_NAME=powerrag-production
   # or
   COMPOSE_PROJECT_NAME=powerrag-dev
   ```
3. Each deployment will have its own isolated set of volumes

#### Listing Volumes

To see all PowerRAG-related volumes:
```bash
docker volume ls | grep powerrag
```

#### Backing Up Volumes

Before cleaning up or upgrading, you may want to back up your data:

```bash
# Back up all PowerRAG volumes
docker run --rm -v powerrag_powerrag_logs:/data -v $(pwd)/backup:/backup alpine tar czf /backup/powerrag_logs.tar.gz -C /data .
docker run --rm -v powerrag_oceanbase_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/oceanbase_data.tar.gz -C /data .
docker run --rm -v powerrag_powerrag_history_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/history_data.tar.gz -C /data .
```

#### Cleaning Up Volumes

> [!WARNING]
> Removing volumes will permanently delete all data including logs, database contents, and history. Make sure to back up any important data first.

**To remove all PowerRAG volumes and data:**

```bash
# Stop and remove all containers
docker compose down

# Remove all PowerRAG volumes
docker compose down -v

# Or manually remove specific volumes
docker volume rm powerrag_powerrag_logs powerrag_oceanbase_data powerrag_powerrag_history_data
```

**To start fresh after cleanup:**

```bash
docker compose up -d
```

#### Viewing Logs and Data

**To view logs from running containers:**

```bash
# View PowerRAG service logs
docker compose logs -f powerrag

# View OceanBase database logs
docker compose logs -f oceanbase

# View all service logs
docker compose logs -f
```

**To access logs and data in volumes:**

```bash
# View log files in the volume
docker run --rm -v powerrag_powerrag_logs:/data alpine ls -la /data

# Read specific log file
docker run --rm -v powerrag_powerrag_logs:/data alpine cat /data/ragflow.log

# Access volume data interactively
docker run --rm -it -v powerrag_oceanbase_data:/data alpine sh
```

**To copy files from volumes to your host:**

```bash
# Copy logs from volume to current directory
docker run --rm -v powerrag_powerrag_logs:/data -v $(pwd):/backup alpine cp -r /data /backup/logs

# Copy database data
docker run --rm -v powerrag_oceanbase_data:/data -v $(pwd):/backup alpine cp -r /data /backup/db_data
```

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