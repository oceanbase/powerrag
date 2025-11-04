# README

<details open>
<summary></b>📗 Table of Contents</b></summary>

- 🐳 [Docker Compose](#-docker-compose)
- 🐬 [Docker environment variables](#-docker-environment-variables)
- 🐋 [Service configuration](#-service-configuration)
- 📋 [Setup Examples](#-setup-examples)

</details>

## 🐳 Docker Compose

- **docker-compose.yml**  
  Sets up environment for PowerRAG and its dependencies.
- **docker-compose-self-hosted-ob.yml**  
  Sets up environment for PowerRAG with self-hosted OceanBase.

## 🐬 Docker environment variables

The [.env](./.env) file contains important environment variables for Docker.

### OceanBase

- `EXPOSE_OB_PORT`  
  The port used to expose OceanBase container service to the host machine, allowing **external** access to the service running inside the Docker container. Defaults to `2881`.

- `OB_XXX`  
  These environment variables, which begin with `OB_`, are used to set the startup parameters for the OceanBase Docker container. For more details, please refer to [DockerHub](https://hub.docker.com/r/oceanbase/oceanbase-ce).

Note that if you want to use self-hosted OceanBase, you do not need to care about the variables above, but you should modify the following variables, which begin with `OCEANBASE_`.

```.dotenv
OCEANBASE_HOST=oceanbase
OCEANBASE_PORT=2881
OCEANBASE_USER=root@${OB_TENANT_NAME}
OCEANBASE_PASSWORD=${OB_TENANT_PASSWORD}
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
   docker-compose down
   docker-compose up -d
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