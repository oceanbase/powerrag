#!/usr/bin/env bash

set -euo pipefail

# -----------------------------------------------------------------------------
# RAGFlow 服务部署脚本（运维相关）
#
# 目标：参考 docker/entrypoint.sh 的“组件开关 + 多实例 + 端口参数”模式重构。
#
# - 默认：启动 webserver(ragflow_server + 可选 nginx)、taskexecutor
# - 可选：MCP / Admin / PowerRAG
# - 支持：多 ragflow_server（通过 RAGFLOW_SERVICE_CONF 指向不同 conf 文件）
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_FOLDER="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON="${PYTHON:-${WORKSPACE_FOLDER}/.venv/bin/python}"

RAGFLOW_SERVER_PY="${WORKSPACE_FOLDER}/api/ragflow_server.py"
TASK_EXECUTOR_PY="${WORKSPACE_FOLDER}/rag/svr/task_executor.py"
DATASYNC_PY="${WORKSPACE_FOLDER}/rag/svr/sync_data_source.py"
ADMIN_SERVER_PY="${WORKSPACE_FOLDER}/admin/server/admin_server.py"
MCP_SERVER_PY="${WORKSPACE_FOLDER}/mcp/server/server.py"
POWERRAG_SERVER_PY="${WORKSPACE_FOLDER}/powerrag/server/powerrag_server.py"

CONF_DIR="${WORKSPACE_FOLDER}/conf"
GLOBAL_SERVICE_CONF="${GLOBAL_SERVICE_CONF:-local.service_conf.yaml}"

WEB_DIR="${WORKSPACE_FOLDER}/web"
NGINX_CONF_DIR="${WORKSPACE_FOLDER}/nginx_conf"

LOG_DIR="${WORKSPACE_FOLDER}/logs"
PID_DIR="${WORKSPACE_FOLDER}/pids"
mkdir -p "${LOG_DIR}" "${PID_DIR}" "${NGINX_CONF_DIR}"

# -----------------------------------------------------------------------------
# Stable SECRET_KEY for auth token signing across multiple ragflow_server instances
#
# Why:
# - Login returns a signed token in `Authorization` header.
# - If multiple ragflow_server processes use different SECRET_KEY, nginx/clients
#   will hit different instances and get "Signature ... does not match" -> 401,
#   causing frontend to jump back to login.
#
# Strategy:
# - Prefer externally provided env RAGFLOW_SECRET_KEY (>= 32 chars).
# - Otherwise generate ONE and persist to conf/.ragflow_secret_key, then export it
#   so all child processes started by this script share it.
# -----------------------------------------------------------------------------
function ensure_ragflow_secret_key() {
  local key_file="${CONF_DIR}/.ragflow_secret_key"

  if [[ -n "${RAGFLOW_SECRET_KEY:-}" && ${#RAGFLOW_SECRET_KEY} -ge 32 ]]; then
    export RAGFLOW_SECRET_KEY
    return 0
  fi

  if [[ -f "${key_file}" ]]; then
    RAGFLOW_SECRET_KEY="$(cat "${key_file}")"
  else
    _require_python
    RAGFLOW_SECRET_KEY="$("${PYTHON}" -c 'import secrets; print(secrets.token_hex(32))')"
    echo -n "${RAGFLOW_SECRET_KEY}" > "${key_file}"
    chmod 600 "${key_file}" 2>/dev/null || true
  fi

  if [[ ${#RAGFLOW_SECRET_KEY} -lt 32 ]]; then
    echo "ERROR: failed to initialize a strong RAGFLOW_SECRET_KEY" >&2
    return 1
  fi

  export RAGFLOW_SECRET_KEY
}

# -----------------------------------------------------------------------------
# Defaults (aligned with docker/entrypoint.sh)
# -----------------------------------------------------------------------------
ENABLE_WEBSERVER="${ENABLE_WEBSERVER:-1}"
ENABLE_TASKEXECUTOR="${ENABLE_TASKEXECUTOR:-1}"
ENABLE_DATASYNC="${ENABLE_DATASYNC:-0}"
ENABLE_MCP_SERVER="${ENABLE_MCP_SERVER:-0}"
ENABLE_ADMIN_SERVER="${ENABLE_ADMIN_SERVER:-0}"
ENABLE_POWERRAG_SERVER="${ENABLE_POWERRAG_SERVER:-0}"

CONSUMER_NO_BEG="${CONSUMER_NO_BEG:-0}"
CONSUMER_NO_END="${CONSUMER_NO_END:-0}"
WORKERS="${WORKERS:-1}"

#
# Env vars:
# - SVR_COUNT
# - SVR_HTTP_PORT
# - SVR_EXTRA_BASE_HTTP_PORT
# - ADMIN_SVR_HTTP_PORT
SVR_COUNT="${SVR_COUNT:-1}"
SVR_HTTP_PORT="${SVR_HTTP_PORT:-9380}"
SVR_EXTRA_BASE_HTTP_PORT="${SVR_EXTRA_BASE_HTTP_PORT:-9400}"
ADMIN_SVR_HTTP_PORT="${ADMIN_SVR_HTTP_PORT:-9381}"

MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-9382}"
MCP_BASE_URL="${MCP_BASE_URL:-http://127.0.0.1:${SVR_HTTP_PORT}}"
MCP_MODE="${MCP_MODE:-self-host}"
MCP_HOST_API_KEY="${MCP_HOST_API_KEY:-}"
MCP_TRANSPORT_SSE_FLAG="${MCP_TRANSPORT_SSE_FLAG:---transport-sse-enabled}"
MCP_TRANSPORT_STREAMABLE_HTTP_FLAG="${MCP_TRANSPORT_STREAMABLE_HTTP_FLAG:---transport-streamable-http-enabled}"
MCP_JSON_RESPONSE_FLAG="${MCP_JSON_RESPONSE_FLAG:---json-response}"

POWERRAG_PORT="${POWERRAG_PORT:-6000}"

# Web frontend (nginx) optional
WEB_PORT="${WEB_PORT:-9222}"
SERVER_HOST_FOR_WEB="${SERVER_HOST_FOR_WEB:-127.0.0.1}"
ADMIN_HOST_FOR_WEB="${ADMIN_HOST_FOR_WEB:-127.0.0.1}"

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
function usage() {
  cat <<'EOF'
用法:
  ./scripts/deploy.sh [start|stop|restart|status|force-stop|clear|help] [options]

说明:
  - start: 启动组件
      - 默认模式：不带任何 --enable-* 时，启动 webserver + taskexecutor（datasync 默认不启动）
      - enable-only 模式：只要带了任意 --enable-*，则只启动被 enable 的组件，其它全部不启动
  - stop: 停止本脚本启动的组件（基于 pids/）
  - restart: stop + start
  - status: 查看状态
  - force-stop: 强制杀进程（不依赖 pid 文件，谨慎使用）
  - clear: 停止并清理运行时生成文件（logs/、pids/、nginx_conf/、conf/service_conf_ragflow_*.yaml）

核心 options（参考 docker/entrypoint.sh）:
  --enable-webserver
  --disable-webserver
  --enable-taskexecutor
  --disable-taskexecutor
  --enable-datasync
  --disable-datasync
  --enable-mcpserver
  --enable-adminserver
  --enable-powerragserver

Task executor options:
  --consumer-no-beg=<num>
  --consumer-no-end=<num>   # 半开区间 [beg, end)
  --workers=<num>           # 如果未指定 range，则启动 workers 个
  --host-id=<string>        # 默认：hostname(<=32) 否则 md5(hostname)

Multi ragflow_server:
  --svr-count=<num>                       # SVR_COUNT
  --svr-http-port=<num>                   # SVR_HTTP_PORT (idx=0 端口)
  --svr-extra-base-http-port=<num>        # SVR_EXTRA_BASE_HTTP_PORT (idx>=1: base+(idx-1))
  --admin-svr-http-port=<num>             # ADMIN_SVR_HTTP_PORT (写入 per-instance conf 里的 admin.http_port)
  --service-conf=<filename>               # 基础 conf 文件（默认: service_conf.yaml）

MCP options:
  --mcp-host=<ip>
  --mcp-port=<num>
  --mcp-base-url=<url>
  --mcp-mode=<self-host|hosted>
  --mcp-host-api-key=<string>
  --no-transport-sse-enabled
  --no-transport-streamable-http-enabled
  --no-json-response

PowerRAG options:
  --powerrag-port=<num>

说明:
  - webserver 组件会尝试启动 ragflow_server + nginx(前端静态 + API 反代)（若存在 web/ 目录）。
EOF
}

function is_process_running() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] && ps -p "${pid}" >/dev/null 2>&1
}

function _default_host_id() {
  local hn
  hn="$(hostname)"
  if [[ ${#hn} -le 32 ]]; then
    echo "${hn}"
    return 0
  fi
  if command -v md5sum >/dev/null 2>&1; then
    echo -n "${hn}" | md5sum | awk '{print $1}'
    return 0
  fi
  "${PYTHON}" - <<PY
import hashlib, socket
print(hashlib.md5(socket.gethostname().encode("utf-8")).hexdigest())
PY
}

HOST_ID="${HOST_ID:-$(_default_host_id)}"

function _require_python() {
  if [[ ! -x "${PYTHON}" ]]; then
    echo "ERROR: python not found/executable: ${PYTHON}" >&2
    echo "Hint: run ./scripts/setup_venv.sh or set PYTHON=/path/to/python" >&2
    exit 1
  fi
}

function _jemalloc_preload_env() {
  # best-effort: return "LD_PRELOAD=..." if available
  if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists jemalloc >/dev/null 2>&1; then
    local libdir
    libdir="$(pkg-config --variable=libdir jemalloc 2>/dev/null || true)"
    if [[ -n "${libdir}" && -f "${libdir}/libjemalloc.so" ]]; then
      echo "LD_PRELOAD=${libdir}/libjemalloc.so"
      return 0
    fi
  fi
  if [[ -f "/usr/lib64/libjemalloc.so" ]]; then
    echo "LD_PRELOAD=/usr/lib64/libjemalloc.so"
    return 0
  fi
  echo ""
}

function _common_env_kv() {
  # keep previous local defaults; can be overridden externally
  local jemalloc_kv
  jemalloc_kv="$(_jemalloc_preload_env)"

  # Ensure a stable secret key for all python processes started by this script.
  ensure_ragflow_secret_key
  echo "RAGFLOW_SECRET_KEY=${RAGFLOW_SECRET_KEY}"

  echo "PYTHONPATH=${WORKSPACE_FOLDER}"
  echo "DOC_ENGINE=${DOC_ENGINE:-oceanbase}"
  echo "CACHE_TYPE=${CACHE_TYPE:-redis}"
  echo "STORAGE_IMPL=${STORAGE_IMPL:-OPENDAL}"
  echo "NLTK_DATA=${WORKSPACE_FOLDER}/nltk_data"
  echo "CHROME_DIR=${WORKSPACE_FOLDER}/chrome-linux64"
  echo "CHROMEDRIVER_DIR=${WORKSPACE_FOLDER}/chromedriver-linux64"
  echo "TIKA_SERVER_JAR=${WORKSPACE_FOLDER}/tika-server-standard-3.0.0.jar"
  echo "HUGGINGFACE_DIR=${WORKSPACE_FOLDER}/huggingface.co"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-/usr/lib/x86_64-linux-gnu/:/usr/lib64/}"
  echo "TIKTOKEN_CACHE_DIR=${WORKSPACE_FOLDER}"
  echo "LIGHTEN=${LIGHTEN:-1}"
  echo "http_proxy="
  echo "https_proxy="
  echo "no_proxy="
  echo "HTTP_PROXY="
  echo "HTTPS_PROXY="
  echo "NO_PROXY="
  if [[ -n "${jemalloc_kv}" ]]; then
    echo "${jemalloc_kv}"
  fi
}

function _start_process() {
  local name="$1"; shift
  local pid_file="$1"; shift
  local workdir="$1"; shift
  local -a cmd=( "$@" )

  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      echo "[skip] ${name} already running (PID: ${pid})"
      return 0
    fi
  fi

  mkdir -p "$(dirname "${pid_file}")"

  # quote cmd for bash -c
  local cmd_quoted=""
  local arg
  for arg in "${cmd[@]}"; do
    cmd_quoted+="$(printf '%q ' "${arg}")"
  done

  # Run in background without restart loop.
  # Note: Most services manage their own logs via init_root_logger() (file + stream).
  # We discard stdout/stderr here to avoid duplicate logging (when stdout is redirected
  # to another file) and keep only the service-managed logs under logs/.
  nohup bash -c "
    set -euo pipefail
    cd $(printf '%q' "${workdir}")
    ${cmd_quoted}
  " >/dev/null 2>&1 &

  local bg_pid=$!
  echo "${bg_pid}" > "${pid_file}"
  echo "[ok] started ${name} (PID: ${bg_pid})"
}

function _stop_by_pidfile() {
  local name="$1"
  local pid_file="$2"
  if [[ ! -f "${pid_file}" ]]; then
    echo "[skip] ${name} not running (no pid file)"
    return 0
  fi
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if is_process_running "${pid}"; then
    echo "[stop] ${name} (PID: ${pid})"
    kill "${pid}" 2>/dev/null || true
    sleep 0.5
    if is_process_running "${pid}"; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  else
    echo "[skip] ${name} not running (stale pid: ${pid})"
  fi
  rm -f "${pid_file}"
}

function _validate_port() {
  local port="$1"
  [[ "${port}" =~ ^[0-9]+$ ]] && [[ "${port}" -ge 1 ]] && [[ "${port}" -le 65535 ]]
}

function _check_port_conflicts() {
  local -a reserved_ports=()
  local -a ragflow_ports=()
  local port idx

  # Collect reserved ports (admin, mcp, powerrag, web)
  reserved_ports+=("${ADMIN_SVR_HTTP_PORT}")
  reserved_ports+=("${MCP_PORT}")
  reserved_ports+=("${POWERRAG_PORT}")
  reserved_ports+=("${WEB_PORT}")

  # Collect ragflow_server ports
  ragflow_ports+=("${SVR_HTTP_PORT}")
  for (( idx=1; idx<${SVR_COUNT}; idx++ )); do
    port=$((SVR_EXTRA_BASE_HTTP_PORT + idx - 1))
    ragflow_ports+=("${port}")
  done

  # Check ragflow ports against reserved ports
  for port in "${ragflow_ports[@]}"; do
    for reserved in "${reserved_ports[@]}"; do
      if [[ "${port}" -eq "${reserved}" ]]; then
        echo "ERROR: Port conflict detected: ragflow_server port ${port} conflicts with reserved port ${reserved}" >&2
        if [[ "${port}" -eq "${ADMIN_SVR_HTTP_PORT}" ]]; then
          echo "  Hint: SVR_HTTP_PORT or SVR_EXTRA_BASE_HTTP_PORT should not equal ADMIN_SVR_HTTP_PORT (${ADMIN_SVR_HTTP_PORT})" >&2
        elif [[ "${port}" -eq "${MCP_PORT}" ]]; then
          echo "  Hint: ragflow_server port conflicts with MCP_PORT (${MCP_PORT})" >&2
        elif [[ "${port}" -eq "${POWERRAG_PORT}" ]]; then
          echo "  Hint: ragflow_server port conflicts with POWERRAG_PORT (${POWERRAG_PORT})" >&2
        elif [[ "${port}" -eq "${WEB_PORT}" ]]; then
          echo "  Hint: ragflow_server port conflicts with WEB_PORT (${WEB_PORT})" >&2
        fi
        return 1
      fi
    done
  done

  # Check for duplicates within ragflow ports
  local -a seen=()
  for port in "${ragflow_ports[@]}"; do
    for seen_port in "${seen[@]}"; do
      if [[ "${port}" -eq "${seen_port}" ]]; then
        echo "ERROR: Duplicate ragflow_server port detected: ${port}" >&2
        echo "  Hint: SVR_COUNT=${SVR_COUNT}, SVR_HTTP_PORT=${SVR_HTTP_PORT}, SVR_EXTRA_BASE_HTTP_PORT=${SVR_EXTRA_BASE_HTTP_PORT}" >&2
        return 1
      fi
    done
    seen+=("${port}")
  done

  return 0
}

# -----------------------------------------------------------------------------
# Config generation (per-instance service conf)
# -----------------------------------------------------------------------------
function _render_service_conf_copy() {
  local out_file="$1"
  local ragflow_port="$2"
  local admin_port="$3"
  local base_file="${CONF_DIR}/${GLOBAL_SERVICE_CONF}"

  if [[ ! -f "${base_file}" ]]; then
    echo "ERROR: base service conf not found: ${base_file}" >&2
    exit 1
  fi

  "${PYTHON}" - <<PY
import sys
import os
from ruamel.yaml import YAML

base_file = ${base_file@Q}
out_file = ${out_file@Q}
ragflow_port = int(${ragflow_port})
admin_port = int(${admin_port})
secret_key = os.environ.get("RAGFLOW_SECRET_KEY", "")

yaml = YAML()
with open(base_file, "r", encoding="utf-8") as f:
    data = yaml.load(f) or {}

data.setdefault("ragflow", {})
data["ragflow"]["http_port"] = ragflow_port
if secret_key:
    data["ragflow"]["secret_key"] = secret_key
data.setdefault("admin", {})
data["admin"]["http_port"] = admin_port

with open(out_file, "w", encoding="utf-8") as f:
    yaml.dump(data, f)
PY
}

function _prepare_multi_ragflow_confs() {
  local idx port conf_name conf_path
  for (( idx=0; idx<${SVR_COUNT}; idx++ )); do
    conf_name="service_conf_ragflow_${idx}.yaml"
    conf_path="${CONF_DIR}/${conf_name}"
    if [[ "${idx}" -eq 0 ]]; then
      port="${SVR_HTTP_PORT}"
    else
      port=$((SVR_EXTRA_BASE_HTTP_PORT + idx - 1))
    fi
    _render_service_conf_copy "${conf_path}" "${port}" "${ADMIN_SVR_HTTP_PORT}"
  done
}

# -----------------------------------------------------------------------------
# Components
# -----------------------------------------------------------------------------
function start_ragflow_servers() {
  _require_python
  ensure_ragflow_secret_key
  _prepare_multi_ragflow_confs

  local idx port conf_name pid_file
  for (( idx=0; idx<${SVR_COUNT}; idx++ )); do
    conf_name="service_conf_ragflow_${idx}.yaml"
    if [[ "${idx}" -eq 0 ]]; then
      port="${SVR_HTTP_PORT}"
    else
      port=$((SVR_EXTRA_BASE_HTTP_PORT + idx - 1))
    fi

    pid_file="${PID_DIR}/ragflow_server_${port}.pid"

    # Backward compatible pid for main instance
    if [[ "${idx}" -eq 0 ]]; then
      ln -sf "$(basename "${pid_file}")" "${PID_DIR}/ragflow_server.pid" 2>/dev/null || true
    fi

    # env args (newline-separated key=value)
    local -a env_args
    mapfile -t env_args < <(_common_env_kv)

    echo "[start] ragflow_server port=${port} conf=${conf_name}"
    _start_process \
      "ragflow_server:${port}" \
      "${pid_file}" \
      "${WORKSPACE_FOLDER}" \
      env "${env_args[@]}" "RAGFLOW_SERVICE_CONF=${conf_name}" "RAGFLOW_LOG_BASENAME=ragflow_server_${port}" \
      "${PYTHON}" "${RAGFLOW_SERVER_PY}"
  done
}

function start_datasync() {
  _require_python
  local pid_file="${PID_DIR}/datasync.pid"
  local -a env_args
  mapfile -t env_args < <(_common_env_kv)
  _start_process \
    "datasync" \
    "${pid_file}" \
    "${WORKSPACE_FOLDER}" \
    env "${env_args[@]}" "${PYTHON}" "${DATASYNC_PY}"
}

function start_admin_server() {
  _require_python
  local pid_file="${PID_DIR}/admin_server.pid"
  local -a env_args
  mapfile -t env_args < <(_common_env_kv)
  _start_process \
    "admin_server" \
    "${pid_file}" \
    "${WORKSPACE_FOLDER}" \
    env "${env_args[@]}" "${PYTHON}" "${ADMIN_SERVER_PY}"
}

function start_mcp_server() {
  _require_python
  local pid_file="${PID_DIR}/mcp_server.pid"
  local -a env_args
  mapfile -t env_args < <(_common_env_kv)
  _start_process \
    "mcp_server" \
    "${pid_file}" \
    "${WORKSPACE_FOLDER}" \
    env "${env_args[@]}" \
    "${PYTHON}" "${MCP_SERVER_PY}" \
      --host="${MCP_HOST}" \
      --port="${MCP_PORT}" \
      --base-url="${MCP_BASE_URL}" \
      --mode="${MCP_MODE}" \
      --api-key="${MCP_HOST_API_KEY}" \
      "${MCP_TRANSPORT_SSE_FLAG}" \
      "${MCP_TRANSPORT_STREAMABLE_HTTP_FLAG}" \
      "${MCP_JSON_RESPONSE_FLAG}"
}

function start_powerrag_server() {
  _require_python
  local pid_file="${PID_DIR}/powerrag_server.pid"
  local -a env_args
  mapfile -t env_args < <(_common_env_kv)
  _start_process \
    "powerrag_server" \
    "${pid_file}" \
    "${WORKSPACE_FOLDER}" \
    env "${env_args[@]}" "${PYTHON}" "${POWERRAG_SERVER_PY}" --port="${POWERRAG_PORT}"
}

function start_task_executor() {
  _require_python
  local consumer_id="$1"
  local pid_file="${PID_DIR}/task_executor_${consumer_id}.pid"
  local -a env_args
  mapfile -t env_args < <(_common_env_kv)
  _start_process \
    "task_executor[${consumer_id}]" \
    "${pid_file}" \
    "${WORKSPACE_FOLDER}" \
    env "${env_args[@]}" "${PYTHON}" "${TASK_EXECUTOR_PY}" "${consumer_id}"
}

function start_task_executors() {
  if [[ "${CONSUMER_NO_END}" -gt "${CONSUMER_NO_BEG}" ]]; then
    echo "[start] task executors range=[${CONSUMER_NO_BEG},${CONSUMER_NO_END})"
    local i
    for (( i=CONSUMER_NO_BEG; i<CONSUMER_NO_END; i++ )); do
      start_task_executor "${i}"
    done
  else
    echo "[start] task executors workers=${WORKERS}"
    local i
    for (( i=0; i<WORKERS; i++ )); do
      start_task_executor "${i}"
    done
  fi
}

# -----------------------------------------------------------------------------
# Web frontend nginx (static + API proxy). Managed as part of webserver.
# -----------------------------------------------------------------------------
function start_web() {
  local pid_file="${PID_DIR}/web_frontend.pid"

  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      echo "[skip] web frontend already running (PID: ${pid}, PORT: ${WEB_PORT})"
      return 0
    fi
  fi

  if [[ ! -d "${WEB_DIR}" ]]; then
    echo "[warn] web dir not found: ${WEB_DIR}; skip nginx frontend/proxy" >&2
    return 0
  fi
  if ! _validate_port "${WEB_PORT}"; then
    echo "ERROR: invalid WEB_PORT=${WEB_PORT}" >&2
    return 1
  fi
  if ! command -v nginx >/dev/null 2>&1; then
    echo "[warn] nginx not found in PATH; skip nginx frontend/proxy" >&2
    return 0
  fi

  # If dist missing, try build (best-effort)
  if [[ ! -d "${WEB_DIR}/dist" ]]; then
    if command -v npm >/dev/null 2>&1; then
      echo "[web] dist missing, running build..."
      if ! (cd "${WEB_DIR}" && npm install && npm run build); then
        echo "[warn] web build failed; skip nginx frontend/proxy" >&2
        return 0
      fi
    else
      echo "[warn] ${WEB_DIR}/dist not found and npm not available; skip nginx frontend/proxy" >&2
      return 0
    fi
  fi

  local server_port_for_web="${SVR_HTTP_PORT}"
  local admin_port_for_web="${ADMIN_SVR_HTTP_PORT}"

  # nginx temp dirs (must be writable for non-root runs)
  local nginx_tmp_dir="${NGINX_CONF_DIR}/tmp"
  mkdir -p "${nginx_tmp_dir}/client_body" "${nginx_tmp_dir}/proxy" "${nginx_tmp_dir}/fastcgi" "${nginx_tmp_dir}/uwsgi" "${nginx_tmp_dir}/scgi"

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
        proxy_pass http://${ADMIN_HOST_FOR_WEB}:${admin_port_for_web};
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
        proxy_pass http://${SERVER_HOST_FOR_WEB}:${server_port_for_web};
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

    location ~ ^/static/(css|js|media)/ {
        expires 10y;
        access_log off;
    }
}
EOF

  cat > "${NGINX_CONF_DIR}/nginx.conf" <<EOF
worker_processes  auto;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # temp dirs (avoid /var/lib/nginx/tmp/* which requires root)
    client_body_temp_path ${nginx_tmp_dir}/client_body;
    proxy_temp_path       ${nginx_tmp_dir}/proxy;
    fastcgi_temp_path     ${nginx_tmp_dir}/fastcgi;
    uwsgi_temp_path       ${nginx_tmp_dir}/uwsgi;
    scgi_temp_path        ${nginx_tmp_dir}/scgi;

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

  # NOTE: nginx may try to open the built-in default error log path (often /var/log/nginx/error.log)
  # before parsing config. Use -e to force a writable error log for non-root runs.
  if ! nginx -t -c "${NGINX_CONF_DIR}/nginx.conf" -e "${LOG_DIR}/nginx_error.log" -g "pid ${PID_DIR}/nginx.pid;" >/dev/null 2>&1; then
    echo "[warn] nginx config invalid; skip nginx frontend/proxy" >&2
    nginx -t -c "${NGINX_CONF_DIR}/nginx.conf" -e "${LOG_DIR}/nginx_error.log" -g "pid ${PID_DIR}/nginx.pid;" >&2 || true
    return 0
  fi

  echo "[start] web frontend nginx (PORT: ${WEB_PORT})"
  nginx -c "${NGINX_CONF_DIR}/nginx.conf" -e "${LOG_DIR}/nginx_error.log" -g "pid ${PID_DIR}/nginx.pid;" > "${LOG_DIR}/web_frontend.log" 2>&1

  if [[ -f "${PID_DIR}/nginx.pid" ]]; then
    local web_pid
    web_pid="$(cat "${PID_DIR}/nginx.pid")"
    echo "${web_pid}" > "${pid_file}"
    echo "[ok] web frontend started (PID: ${web_pid})"
  else
    echo "[warn] nginx.pid not found; check ${LOG_DIR}/web_frontend.log" >&2
    return 0
  fi
}

function stop_web() {
  _stop_by_pidfile "web_frontend" "${PID_DIR}/web_frontend.pid"
  # also cleanup nginx pid if present
  if [[ -f "${PID_DIR}/nginx.pid" ]]; then
    local pid
    pid="$(cat "${PID_DIR}/nginx.pid" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      nginx -s quit -c "${NGINX_CONF_DIR}/nginx.conf" 2>/dev/null || kill "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_DIR}/nginx.pid"
  fi
}

# -----------------------------------------------------------------------------
# Stop/Status/Force-stop
# -----------------------------------------------------------------------------
function stop_all() {
  # reverse-ish order
  _stop_by_pidfile "powerrag_server" "${PID_DIR}/powerrag_server.pid"
  _stop_by_pidfile "mcp_server" "${PID_DIR}/mcp_server.pid"
  _stop_by_pidfile "admin_server" "${PID_DIR}/admin_server.pid"
  _stop_by_pidfile "datasync" "${PID_DIR}/datasync.pid"

  # task executors
  local f
  for f in "${PID_DIR}"/task_executor_*.pid; do
    [[ -f "${f}" ]] || continue
    _stop_by_pidfile "task_executor" "${f}"
  done

  # ragflow servers
  for f in "${PID_DIR}"/ragflow_server_*.pid; do
    [[ -f "${f}" ]] || continue
    _stop_by_pidfile "ragflow_server" "${f}"
  done
  rm -f "${PID_DIR}/ragflow_server.pid" 2>/dev/null || true

  # optional web frontend nginx
  stop_web || true
}

function force_stop_all() {
  echo "=== force-stop: killing related processes (best-effort) ==="
  pkill -f "${RAGFLOW_SERVER_PY}" 2>/dev/null || true
  pkill -f "${TASK_EXECUTOR_PY}" 2>/dev/null || true
  pkill -f "${DATASYNC_PY}" 2>/dev/null || true
  pkill -f "${ADMIN_SERVER_PY}" 2>/dev/null || true
  pkill -f "${MCP_SERVER_PY}" 2>/dev/null || true
  pkill -f "${POWERRAG_SERVER_PY}" 2>/dev/null || true
  pkill -f "${NGINX_CONF_DIR}/ragflow.conf" 2>/dev/null || true
  rm -f "${PID_DIR}"/*.pid 2>/dev/null || true
}

function clear_runtime_files() {
  echo "=== clear: stop services and remove generated logs/configs/pids (best-effort) ==="

  # stop services started by this script (based on pids/)
  stop_all || true

  # generated per-instance service confs
  rm -f "${CONF_DIR}"/service_conf_ragflow_*.yaml 2>/dev/null || true

  # remove runtime dirs entirely (user expectation for clear)
  rm -rf "${NGINX_CONF_DIR}" 2>/dev/null || true
  rm -rf "${PID_DIR}" 2>/dev/null || true
  rm -rf "${LOG_DIR}" 2>/dev/null || true

  echo "[ok] cleared: logs/, pids/, nginx_conf/, conf/service_conf_ragflow_*.yaml"
}

function status() {
  echo "=== status ==="

  echo "config:"
  echo "  - service_conf(base) = conf/${GLOBAL_SERVICE_CONF}"
  echo "  - ragflow main port  = ${SVR_HTTP_PORT}"
  echo "  - ragflow extra base = ${SVR_EXTRA_BASE_HTTP_PORT}"
  echo "  - admin port         = ${ADMIN_SVR_HTTP_PORT}"
  echo "  - mcp port           = ${MCP_PORT}"
  echo "  - web port           = ${WEB_PORT}"

  # ragflow
  echo "ragflow_server:"
  local any=0
  local f pid port idx conf_name conf_path log_path
  for f in "${PID_DIR}"/ragflow_server_*.pid; do
    [[ -f "${f}" ]] || continue
    port="$(basename "${f}" | sed 's/ragflow_server_\(.*\)\.pid/\1/')"
    pid="$(cat "${f}" 2>/dev/null || true)"

    # best-effort infer conf name from port
    conf_name="(unknown)"
    if [[ "${port}" == "${SVR_HTTP_PORT}" ]]; then
      conf_name="service_conf_ragflow_0.yaml"
    elif [[ "${port}" =~ ^[0-9]+$ ]]; then
      idx=$(( port - SVR_EXTRA_BASE_HTTP_PORT + 1 ))
      if [[ "${idx}" -ge 1 ]]; then
        conf_name="service_conf_ragflow_${idx}.yaml"
      fi
    fi
    conf_path="conf/${conf_name}"
    log_path="logs/ragflow_server_${port}.log"

    if is_process_running "${pid}"; then
      any=1
      echo "  - [ok] port=${port} pid=${pid} conf=${conf_path} log=${log_path}"
    else
      echo "  - [down] port=${port} pid=${pid} conf=${conf_path} log=${log_path}"
    fi
  done
  if [[ "${any}" -eq 0 ]]; then
    echo "  - (none)"
  fi

  # web frontend (nginx)
  echo "web_frontend:"
  local web_pf="${PID_DIR}/web_frontend.pid"
  if [[ -f "${web_pf}" ]]; then
    pid="$(cat "${web_pf}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      echo "  - [ok] pid=${pid} port=${WEB_PORT} conf=nginx_conf/nginx.conf access_log=logs/nginx_access.log error_log=logs/nginx_error.log"
    else
      echo "  - [down] pid=${pid} port=${WEB_PORT} conf=nginx_conf/nginx.conf access_log=logs/nginx_access.log error_log=logs/nginx_error.log"
    fi
  else
    echo "  - (disabled/not started)"
  fi

  # task executors
  echo "task_executor:"
  any=0
  local args consumer_arg logf
  for f in "${PID_DIR}"/task_executor_*.pid; do
    [[ -f "${f}" ]] || continue
    pid="$(cat "${f}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      any=1
      args="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
      consumer_arg="$(echo "${args}" | awk '{print $NF}')"
      # If no consumer arg provided, fallback to pid-file id.
      if [[ -z "${consumer_arg}" || "${consumer_arg}" == *".py" ]]; then
        consumer_arg="$(basename "${f}" | sed 's/task_executor_\(.*\)\.pid/\1/')"
      fi
      logf="logs/task_executor_${consumer_arg}.log"
      echo "  - [ok] id=$(basename "${f}") pid=${pid} log=${logf}"
    else
      echo "  - [down] id=$(basename "${f}") pid=${pid}"
    fi
  done
  if [[ "${any}" -eq 0 ]]; then
    echo "  - (none)"
  fi

  # datasync
  echo "datasync:"
  local ds_pf="${PID_DIR}/datasync.pid"
  if [[ -f "${ds_pf}" ]]; then
    pid="$(cat "${ds_pf}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      args="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
      consumer_arg="$(echo "${args}" | awk '{print $NF}')"
      if [[ -z "${consumer_arg}" || "${consumer_arg}" == *".py" ]]; then
        consumer_arg="0"
      fi
      logf="logs/data_sync_${consumer_arg}.log"
      echo "  - [ok] pid=${pid} log=${logf}"
    else
      echo "  - [down] pid=${pid}"
    fi
  else
    echo "  - (disabled/not started)"
  fi

  # admin
  echo "admin_server:"
  local ad_pf="${PID_DIR}/admin_server.pid"
  if [[ -f "${ad_pf}" ]]; then
    pid="$(cat "${ad_pf}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      echo "  - [ok] pid=${pid} port=${ADMIN_SVR_HTTP_PORT} log=logs/admin_service.log"
    else
      echo "  - [down] pid=${pid} port=${ADMIN_SVR_HTTP_PORT} log=logs/admin_service.log"
    fi
  else
    echo "  - (disabled/not started)"
  fi

  # mcp
  echo "mcp_server:"
  local mcp_pf="${PID_DIR}/mcp_server.pid"
  if [[ -f "${mcp_pf}" ]]; then
    pid="$(cat "${mcp_pf}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      # port is from script args by default
      echo "  - [ok] pid=${pid} port=${MCP_PORT} log=logs/mcp_server_${MCP_PORT}.log"
    else
      echo "  - [down] pid=${pid} port=${MCP_PORT} log=logs/mcp_server_${MCP_PORT}.log"
    fi
  else
    echo "  - (disabled/not started)"
  fi

  # powerrag
  echo "powerrag_server:"
  local pr_pf="${PID_DIR}/powerrag_server.pid"
  if [[ -f "${pr_pf}" ]]; then
    pid="$(cat "${pr_pf}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
      echo "  - [ok] pid=${pid} port=${POWERRAG_PORT} log=logs/powerrag_server.log"
    else
      echo "  - [down] pid=${pid} port=${POWERRAG_PORT} log=logs/powerrag_server.log"
    fi
  else
    echo "  - (disabled/not started)"
  fi
}

# -----------------------------------------------------------------------------
# Arg parsing (entrypoint-like)
# -----------------------------------------------------------------------------
ACTION="${1:-start}"
shift || true

case "${ACTION}" in
  start|stop|restart|status|force-stop|clear|help) ;;
  *)
    # allow calling with only options: ./deploy.sh --disable-taskexecutor ...
    if [[ "${ACTION}" == --* ]]; then
      set -- "${ACTION}" "$@"
      ACTION="start"
    else
      echo "Unknown action: ${ACTION}" >&2
      usage
      exit 1
    fi
    ;;
esac

# If any --enable-* option is provided, switch to "enable-only" mode:
# only explicitly enabled components will be started.
HAS_ENABLE_FLAGS=0
for arg in "$@"; do
  if [[ "${arg}" == --enable-* ]]; then
    HAS_ENABLE_FLAGS=1
    break
  fi
done
if [[ "${HAS_ENABLE_FLAGS}" -eq 1 ]]; then
  ENABLE_WEBSERVER=0
  ENABLE_TASKEXECUTOR=0
  ENABLE_DATASYNC=0
  ENABLE_MCP_SERVER=0
  ENABLE_ADMIN_SERVER=0
  ENABLE_POWERRAG_SERVER=0
fi

for arg in "$@"; do
  case "${arg}" in
    --enable-webserver) ENABLE_WEBSERVER=1 ;;
    --disable-webserver) ENABLE_WEBSERVER=0 ;;
    --enable-taskexecutor) ENABLE_TASKEXECUTOR=1 ;;
    --disable-taskexecutor) ENABLE_TASKEXECUTOR=0 ;;
    --disable-datasync) ENABLE_DATASYNC=0 ;;
    --enable-datasync) ENABLE_DATASYNC=1 ;;
    --enable-mcpserver) ENABLE_MCP_SERVER=1 ;;
    --enable-adminserver) ENABLE_ADMIN_SERVER=1 ;;
    --enable-powerragserver) ENABLE_POWERRAG_SERVER=1 ;;
    --consumer-no-beg=*) CONSUMER_NO_BEG="${arg#*=}" ;;
    --consumer-no-end=*) CONSUMER_NO_END="${arg#*=}" ;;
    --workers=*) WORKERS="${arg#*=}" ;;
    --host-id=*) HOST_ID="${arg#*=}" ;;
    --svr-count=*) SVR_COUNT="${arg#*=}" ;;
    --svr-http-port=*) SVR_HTTP_PORT="${arg#*=}" ;;
    --svr-extra-base-http-port=*) SVR_EXTRA_BASE_HTTP_PORT="${arg#*=}" ;;
    --admin-svr-http-port=*) ADMIN_SVR_HTTP_PORT="${arg#*=}" ;;

    --service-conf=*) GLOBAL_SERVICE_CONF="${arg#*=}" ;;
    --mcp-host=*) MCP_HOST="${arg#*=}" ;;
    --mcp-port=*) MCP_PORT="${arg#*=}" ;;
    --mcp-base-url=*) MCP_BASE_URL="${arg#*=}" ;;
    --mcp-mode=*) MCP_MODE="${arg#*=}" ;;
    --mcp-host-api-key=*) MCP_HOST_API_KEY="${arg#*=}" ;;
    --no-transport-sse-enabled) MCP_TRANSPORT_SSE_FLAG="--no-transport-sse-enabled" ;;
    --no-transport-streamable-http-enabled) MCP_TRANSPORT_STREAMABLE_HTTP_FLAG="--no-transport-streamable-http-enabled" ;;
    --no-json-response) MCP_JSON_RESPONSE_FLAG="--no-json-response" ;;
    --powerrag-port=*) POWERRAG_PORT="${arg#*=}" ;;
    *) echo "Unknown option: ${arg}" >&2; usage; exit 1 ;;
  esac
done

# Validate ports early (best-effort)
for p in "${SVR_HTTP_PORT}" "${SVR_EXTRA_BASE_HTTP_PORT}" "${ADMIN_SVR_HTTP_PORT}" "${MCP_PORT}" "${POWERRAG_PORT}" "${WEB_PORT}"; do
  if ! _validate_port "${p}"; then
    echo "ERROR: invalid port: ${p}" >&2
    exit 1
  fi
done

# Check for port conflicts
if ! _check_port_conflicts; then
  exit 1
fi

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
case "${ACTION}" in
  help)
    usage
    ;;

  start)
    if [[ "${ENABLE_WEBSERVER}" -eq 1 ]]; then
      echo "[component] webserver enabled (ragflow_server + nginx frontend/proxy)"
      start_ragflow_servers
      # start nginx frontend/proxy when web/ exists (build dist if needed)
      if [[ -d "${WEB_DIR}" ]]; then
        start_web
      else
        echo "[warn] ${WEB_DIR} not found; skip nginx frontend/proxy"
      fi
    else
      echo "[component] webserver disabled"
    fi

    if [[ "${ENABLE_DATASYNC}" -eq 1 ]]; then
      echo "[component] datasync enabled"
      start_datasync
    else
      echo "[component] datasync disabled"
    fi

    if [[ "${ENABLE_ADMIN_SERVER}" -eq 1 ]]; then
      echo "[component] admin_server enabled"
      start_admin_server
    fi

    if [[ "${ENABLE_MCP_SERVER}" -eq 1 ]]; then
      echo "[component] mcp_server enabled"
      start_mcp_server
    fi

    if [[ "${ENABLE_POWERRAG_SERVER}" -eq 1 ]]; then
      echo "[component] powerrag_server enabled"
      start_powerrag_server
    fi

    if [[ "${ENABLE_TASKEXECUTOR}" -eq 1 ]]; then
      echo "[component] taskexecutor enabled"
      start_task_executors
    else
      echo "[component] taskexecutor disabled"
    fi
    ;;

  stop)
    stop_all
    ;;

  restart)
    stop_all
    sleep 1
    "${SCRIPT_DIR}/deploy.sh" start "$@"
    ;;

  force-stop)
    force_stop_all
    ;;

  clear)
    clear_runtime_files
    ;;

  status)
    status
    ;;
esac
