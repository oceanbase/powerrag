#!/bin/bash

# RAGFlow 服务部署脚本（运维相关）
# 使用方法: ./scripts/deploy.sh [start|stop|restart|status|start-ragflow-server|stop-ragflow-server|start-workers|stop-workers|start-web|stop-web]

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_FOLDER="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON="${WORKSPACE_FOLDER}/.venv/bin/python"
RAGFLOW_SERVER="${WORKSPACE_FOLDER}/api/ragflow_server.py"
TASK_EXECUTOR="${WORKSPACE_FOLDER}/rag/svr/task_executor.py"
WEB_DIR="${WORKSPACE_FOLDER}/web"

# 日志目录
LOG_DIR="${WORKSPACE_FOLDER}/logs"
mkdir -p "${LOG_DIR}"

# PID 文件目录
PID_DIR="${WORKSPACE_FOLDER}/pids"
mkdir -p "${PID_DIR}"

# Worker 数量（可以通过环境变量覆盖）
WORKER_COUNT=${WORKER_COUNT:-2}

# Ragflow Server 端口（可以通过环境变量覆盖）
SERVER_PORT_FOR_WEB=${SERVER_PORT_FOR_WEB:-9385}

# Web 前端端口（可以通过环境变量覆盖）
WEB_PORT=${WEB_PORT:-9222}

is_process_running() {
    local pid="$1"
    if [ -z "$pid" ]; then
        return 1
    fi
    ps -p "$pid" > /dev/null 2>&1
}

validate_port() {
    local port="$1"
    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        echo "WEB_PORT 非法: ${port} (应为 1-65535)"
        return 1
    fi
    return 0
}

# 启动 Web 前端（正式环境：build + 静态服务）
start_web() {
    local pid_file="${PID_DIR}/web_frontend.pid"

    if [ -f "${pid_file}" ]; then
        PID=$(cat "${pid_file}")
        if is_process_running "$PID"; then
            echo "Web 前端已经在运行 (PID: $PID, PORT: ${WEB_PORT})"
            return 1
        fi
    fi

    if [ ! -d "${WEB_DIR}" ]; then
        echo "Web 前端目录不存在: ${WEB_DIR}"
        return 1
    fi

    if ! command -v npm > /dev/null 2>&1; then
        echo "未找到 npm，请先安装 Node.js/npm（web/package.json 要求 node >= 18.20.4）"
        return 1
    fi

    if ! validate_port "${WEB_PORT}"; then
        return 1
    fi

    echo "启动 Web 前端（生产模式）..."
    echo "  - 目录: ${WEB_DIR}"
    echo "  - 端口: ${WEB_PORT}"

    # 检查并安装前端依赖
    if [ ! -d "${WEB_DIR}/node_modules" ]; then
        echo "检测到前端依赖未安装，正在安装..."
        cd "${WEB_DIR}" && npm install || {
            echo "前端依赖安装失败，请检查网络和 npm 配置"
            return 1
        }
    fi

    # 检查 nginx 是否已安装
    if ! command -v nginx > /dev/null 2>&1; then
        echo "错误: 未找到 nginx，请先安装 nginx"
        echo "安装方法:"
        echo "  Ubuntu/Debian: sudo apt-get install nginx"
        echo "  CentOS/RHEL: sudo yum install nginx"
        return 1
    fi

    # 构建生产版本
    echo "正在构建生产版本..."
    cd "${WEB_DIR}" && npm run build || {
        echo "构建失败，请检查构建日志"
        return 1
    }

    # 检查构建输出目录是否存在
    if [ ! -d "${WEB_DIR}/dist" ]; then
        echo "构建输出目录不存在: ${WEB_DIR}/dist"
        return 1
    fi

    # 创建 nginx 配置目录
    NGINX_CONF_DIR="${WORKSPACE_FOLDER}/nginx_conf"
    mkdir -p "${NGINX_CONF_DIR}"

    # 生成 nginx 配置文件
    SERVER_HOST=${SERVER_HOST_FOR_WEB:-127.0.0.1}
    SERVER_PORT=${SERVER_PORT_FOR_WEB:-9380}
    ADMIN_HOST=${ADMIN_HOST_FOR_WEB:-127.0.0.1}
    ADMIN_PORT=${ADMIN_PORT_FOR_WEB:-9381}

    cat > "${NGINX_CONF_DIR}/ragflow.conf" <<EOF
server {
    listen ${WEB_PORT};
    server_name _;
    root ${WEB_DIR}/dist;

    gzip on;
    gzip_min_length 1k;
    gzip_comp_level 9;
    gzip_types text/plain application/javascript application/x-javascript text/css application/xml text/javascript application/x-httpd-php image/jpeg image/gif image/png;
    gzip_vary on;
    gzip_disable "MSIE [1-6]\\.";

    location ~ ^/api/v1/admin {
        proxy_pass http://${ADMIN_HOST}:${ADMIN_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location ~ ^/(v1|api) {
        proxy_pass http://${SERVER_HOST}:${SERVER_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location / {
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # Cache-Control: max-age~@~AExpires
    location ~ ^/static/(css|js|media)/ {
        expires 10y;
        access_log off;
    }
}
EOF

    # 生成 nginx 主配置文件
    cat > "${NGINX_CONF_DIR}/nginx.conf" <<EOF
user  root;
worker_processes  auto;

error_log  ${LOG_DIR}/nginx_error.log notice;
pid        ${PID_DIR}/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log  ${LOG_DIR}/nginx_access.log  main;

    sendfile        on;
    keepalive_timeout  65;
    client_max_body_size 1024M;

    include ${NGINX_CONF_DIR}/ragflow.conf;
}
EOF

    # 检查 nginx 配置文件语法
    if ! nginx -t -c "${NGINX_CONF_DIR}/nginx.conf" > /dev/null 2>&1; then
        echo "nginx 配置文件语法错误，请检查配置"
        nginx -t -c "${NGINX_CONF_DIR}/nginx.conf"
        return 1
    fi

    # 启动 nginx
    echo "使用 nginx 启动（生产模式，支持 API 代理）..."
    nginx -c "${NGINX_CONF_DIR}/nginx.conf" -g "pid ${PID_DIR}/nginx.pid;" > "${LOG_DIR}/web_frontend.log" 2>&1

    # 获取 nginx 主进程 PID
    if [ -f "${PID_DIR}/nginx.pid" ]; then
        WEB_PID=$(cat "${PID_DIR}/nginx.pid")
        echo $WEB_PID > "${pid_file}"
        echo "Web 前端已启动（生产模式，nginx）(PID: ${WEB_PID}, PORT: ${WEB_PORT})"
    else
        echo "警告: 无法获取 nginx PID，请检查日志: ${LOG_DIR}/web_frontend.log"
        return 1
    fi
}

# 启动 Ragflow Server
start_ragflow_server() {
    if [ -f "${PID_DIR}/ragflow_server.pid" ]; then
        PID=$(cat "${PID_DIR}/ragflow_server.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Ragflow Server 已经在运行 (PID: $PID)"
            return 1
        fi
    fi
    
    echo "启动 Ragflow Server..."
    cd "${WORKSPACE_FOLDER}"
    nohup env \
        PYTHONPATH="${WORKSPACE_FOLDER}" \
        SERVER_PORT_FOR_WEB="${SERVER_PORT_FOR_WEB}" \
        DOC_ENGINE="oceanbase" \
        CACHE_TYPE="redis" \
        STORAGE_IMPL="OPENDAL" \
        NLTK_DATA="${WORKSPACE_FOLDER}/nltk_data" \
        CHROME_DIR="${WORKSPACE_FOLDER}/chrome-linux64" \
        CHROMEDRIVER_DIR="${WORKSPACE_FOLDER}/chromedriver-linux64" \
        TIKA_SERVER_JAR="${WORKSPACE_FOLDER}/tika-server-standard-3.0.0.jar" \
        HUGGINGFACE_DIR="${WORKSPACE_FOLDER}/huggingface.co" \
        LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu/:/usr/lib64/" \
        TIKTOKEN_CACHE_DIR="${WORKSPACE_FOLDER}" \
        http_proxy="" \
        https_proxy="" \
        no_proxy="" \
        HTTP_PROXY="" \
        HTTPS_PROXY="" \
        NO_PROXY="" \
        LIGHTEN="1" \
        "${PYTHON}" "${RAGFLOW_SERVER}" > "${LOG_DIR}/ragflow_server.log" 2>&1 &
    
    SERVER_PID=$!
    echo $SERVER_PID > "${PID_DIR}/ragflow_server.pid"
    echo "Ragflow Server 已启动 (PID: $SERVER_PID)"
}

# 启动 Worker
start_worker() {
    local worker_id=$1
    local pid_file="${PID_DIR}/worker_${worker_id}.pid"
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Worker $worker_id 已经在运行 (PID: $PID)"
            return 1
        fi
    fi
    
    echo "启动 Worker $worker_id..."
    cd "${WORKSPACE_FOLDER}"
    nohup env \
        TRACE_MALLOC_ENABLED="1" \
        DOC_ENGINE="oceanbase" \
        CACHE_TYPE="redis" \
        STORAGE_IMPL="OPENDAL" \
        PYTHONPATH="${WORKSPACE_FOLDER}" \
        NLTK_DATA="${WORKSPACE_FOLDER}/nltk_data" \
        CHROME_DIR="${WORKSPACE_FOLDER}/chrome-linux64" \
        CHROMEDRIVER_DIR="${WORKSPACE_FOLDER}/chromedriver-linux64" \
        TIKA_SERVER_JAR="${WORKSPACE_FOLDER}/tika-server-standard-3.0.0.jar" \
        HUGGINGFACE_DIR="${WORKSPACE_FOLDER}/huggingface.co" \
        LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu/:/usr/lib64/" \
        LD_PRELOAD="/usr/lib64/libjemalloc.so" \
        http_proxy="" \
        https_proxy="" \
        no_proxy="" \
        HTTP_PROXY="" \
        HTTPS_PROXY="" \
        NO_PROXY="" \
        EMBEDDING_BATCH_SIZE="32" \
        DOC_BULK_SIZE="16" \
        MAX_CONCURRENT_CHUNK_BUILDERS="8" \
        MAX_CONCURRENT_TASKS="8" \
        "${PYTHON}" "${TASK_EXECUTOR}" "${worker_id}" > "${LOG_DIR}/worker_${worker_id}.log" 2>&1 &
    
    WORKER_PID=$!
    echo $WORKER_PID > "$pid_file"
    echo "Worker $worker_id 已启动 (PID: $WORKER_PID)"
}

# 启动所有 Workers
start_workers() {
    echo "启动 $WORKER_COUNT 个 Workers..."
    for i in $(seq 0 $((WORKER_COUNT - 1))); do
        start_worker $i
        sleep 1
    done
}

# 停止 Ragflow Server
stop_ragflow_server() {
    if [ ! -f "${PID_DIR}/ragflow_server.pid" ]; then
        echo "Ragflow Server 未运行"
        return 1
    fi
    
    PID=$(cat "${PID_DIR}/ragflow_server.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo "停止 Ragflow Server (PID: $PID)..."
        kill $PID
        rm "${PID_DIR}/ragflow_server.pid"
        echo "Ragflow Server 已停止"
    else
        echo "Ragflow Server 未运行"
        rm "${PID_DIR}/ragflow_server.pid"
    fi
}

# 停止 Worker
stop_worker() {
    local worker_id=$1
    local pid_file="${PID_DIR}/worker_${worker_id}.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo "Worker $worker_id 未运行"
        return 1
    fi
    
    PID=$(cat "$pid_file")
    if ps -p $PID > /dev/null 2>&1; then
        echo "停止 Worker $worker_id (PID: $PID)..."
        kill $PID
        rm "$pid_file"
        echo "Worker $worker_id 已停止"
    else
        echo "Worker $worker_id 未运行"
        rm "$pid_file"
    fi
}

# 停止所有 Workers
stop_workers() {
    for pid_file in "${PID_DIR}"/worker_*.pid; do
        if [ -f "$pid_file" ]; then
            worker_id=$(basename "$pid_file" | sed 's/worker_\(.*\)\.pid/\1/')
            stop_worker "$worker_id"
        fi
    done
}

# 停止 Web 前端
stop_web() {
    local pid_file="${PID_DIR}/web_frontend.pid"

    if [ ! -f "${pid_file}" ]; then
        echo "Web 前端未运行"
        return 1
    fi

    PID=$(cat "${pid_file}")
    if is_process_running "$PID"; then
        echo "停止 Web 前端 (PID: $PID)..."
        kill "$PID"
        rm "${pid_file}"
        echo "Web 前端已停止"
    else
        echo "Web 前端未运行"
        rm "${pid_file}"
    fi
}

# 强制停止所有相关进程（不依赖 PID 文件）
force_stop_all() {
    echo "=== 强制停止所有相关进程 ==="
    
    # 停止当前用户的 ragflow_server 进程
    echo "查找并停止 ragflow_server 进程..."
    RAGFLOW_PIDS=$(ps -ef | grep "${RAGFLOW_SERVER}" | grep -v grep | awk '{print $2}')
    if [ -n "$RAGFLOW_PIDS" ]; then
        for pid in $RAGFLOW_PIDS; do
            echo "停止 Ragflow Server (PID: $pid)..."
            kill -9 $pid 2>/dev/null || true
        done
        echo "Ragflow Server 进程已停止"
    else
        echo "未找到 Ragflow Server 进程"
    fi
    
    # 停止当前用户的 task_executor 进程
    echo ""
    echo "查找并停止 task_executor 进程..."
    WORKER_PIDS=$(ps -ef | grep "${TASK_EXECUTOR}" | grep -v grep | awk '{print $2}')
    if [ -n "$WORKER_PIDS" ]; then
        for pid in $WORKER_PIDS; do
            echo "停止 Task Executor (PID: $pid)..."
            kill -9 $pid 2>/dev/null || true
        done
        echo "Task Executor 进程已停止"
    else
        echo "未找到 Task Executor 进程"
    fi

    # 停止 Web 前端（nginx）
    echo ""
    echo "查找并停止 Web 前端进程（nginx）..."
    if [ -f "${PID_DIR}/nginx.pid" ]; then
        NGINX_PID=$(cat "${PID_DIR}/nginx.pid")
        if ps -p $NGINX_PID > /dev/null 2>&1; then
            echo "停止 nginx (PID: $NGINX_PID)..."
            nginx -s quit -c "${WORKSPACE_FOLDER}/nginx_conf/nginx.conf" 2>/dev/null || kill $NGINX_PID 2>/dev/null || true
            sleep 1
            if ps -p $NGINX_PID > /dev/null 2>&1; then
                kill -9 $NGINX_PID 2>/dev/null || true
            fi
            rm -f "${PID_DIR}/nginx.pid"
            echo "nginx 已停止"
        else
            echo "nginx 未运行"
            rm -f "${PID_DIR}/nginx.pid"
        fi
    else
        # 查找所有 nginx 进程
        NGINX_PIDS=$(ps -ef | grep "nginx.*ragflow.conf" | grep -v grep | awk '{print $2}')
        if [ -n "$NGINX_PIDS" ]; then
            for pid in $NGINX_PIDS; do
                echo "停止 nginx (PID: $pid)..."
                kill -9 $pid 2>/dev/null || true
            done
            echo "nginx 进程已停止"
        else
            echo "未找到 nginx 进程"
        fi
    fi
    
    # 清理所有 PID 文件
    echo ""
    echo "清理 PID 文件..."
    rm -f "${PID_DIR}"/ragflow_server.pid "${PID_DIR}"/worker_*.pid "${PID_DIR}"/web_frontend.pid "${PID_DIR}"/nginx.pid
    echo "完成"
}

# 查看状态
status() {
    echo "=== 服务状态 ==="
    
    # Ragflow Server
    if [ -f "${PID_DIR}/ragflow_server.pid" ]; then
        PID=$(cat "${PID_DIR}/ragflow_server.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Ragflow Server: 运行中 (PID: $PID)"
        else
            echo "Ragflow Server: 未运行"
        fi
    else
        echo "Ragflow Server: 未运行"
    fi
    
    # Workers
    echo ""
    echo "Workers:"
    local running_count=0
    for pid_file in "${PID_DIR}"/worker_*.pid; do
        if [ -f "$pid_file" ]; then
            worker_id=$(basename "$pid_file" | sed 's/worker_\(.*\)\.pid/\1/')
            PID=$(cat "$pid_file")
            if ps -p $PID > /dev/null 2>&1; then
                echo "  Worker $worker_id: 运行中 (PID: $PID)"
                running_count=$((running_count + 1))
            else
                echo "  Worker $worker_id: 未运行"
            fi
        fi
    done
    
    if [ $running_count -eq 0 ]; then
        echo "  没有运行的 Worker"
    fi

    # Web Frontend (nginx)
    echo ""
    if [ -f "${PID_DIR}/web_frontend.pid" ]; then
        PID=$(cat "${PID_DIR}/web_frontend.pid")
        if is_process_running "$PID"; then
            echo "Web 前端 (nginx): 运行中 (PID: $PID, PORT: ${WEB_PORT})"
        else
            echo "Web 前端 (nginx): 未运行"
        fi
    elif [ -f "${PID_DIR}/nginx.pid" ]; then
        PID=$(cat "${PID_DIR}/nginx.pid")
        if is_process_running "$PID"; then
            echo "Web 前端 (nginx): 运行中 (PID: $PID, PORT: ${WEB_PORT})"
        else
            echo "Web 前端 (nginx): 未运行"
        fi
    else
        echo "Web 前端 (nginx): 未运行"
    fi
}

# 主函数
case "$1" in
    start)
        start_ragflow_server
        start_workers
        ;;
    stop)
        stop_ragflow_server
        stop_workers
        ;;
    force-stop)
        force_stop_all
        ;;
    restart)
        stop_ragflow_server
        stop_workers
        sleep 2
        start_ragflow_server
        start_workers
        ;;
    force-restart)
        force_stop_all
        sleep 2
        start_ragflow_server
        start_workers
        ;;
    status)
        status
        ;;
    start-ragflow-server)
        start_ragflow_server
        ;;
    stop-ragflow-server)
        stop_ragflow_server
        ;;
    start-workers)
        start_workers
        ;;
    stop-workers)
        stop_workers
        ;;
    start-web)
        start_web
        ;;
    stop-web)
        stop_web
        ;;
    *)
        echo "使用方法: $0 {start|stop|force-stop|restart|force-restart|status|start-ragflow-server|stop-ragflow-server|start-workers|stop-workers|start-web|stop-web}"
        echo ""
        echo "环境变量:"
        echo "  WORKER_COUNT - Worker 数量 (默认: 2)"
        echo "  SERVER_PORT_FOR_WEB - Ragflow Server 端口 (默认: 9385)"
        echo "  WEB_PORT - Web 前端端口 (默认: 9222)"
        echo ""
        echo "示例:"
        echo "  $0 start              # 启动所有服务"
        echo "  WORKER_COUNT=4 $0 start  # 启动 4 个 Workers"
        echo "  $0 stop               # 停止所有服务（基于 PID 文件）"
        echo "  $0 force-stop         # 强制停止所有相关进程（不依赖 PID 文件）"
        echo "  $0 restart            # 重启所有服务"
        echo "  $0 force-restart      # 强制重启所有服务"
        echo "  $0 status             # 查看服务状态"
        echo "  $0 start-ragflow-server  # 仅启动 Ragflow Server"
        echo "  $0 stop-ragflow-server   # 仅停止 Ragflow Server"
        echo "  $0 start-workers        # 仅启动 Workers"
        echo "  $0 stop-workers         # 仅停止 Workers"
        echo "  WEB_PORT=9222 $0 start-web   # 启动 Web 前端（正式环境）"
        echo "  $0 stop-web             # 停止 Web 前端"
        exit 1
        ;;
esac

