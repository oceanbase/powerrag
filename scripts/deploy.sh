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

function _pids_listening_on_port() {
  local port="$1"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    # -t: pids only; LISTEN only
    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' | xargs echo 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    # fuser output format varies; best-effort
    pids="$(fuser -n tcp "${port}" 2>/dev/null | tr '\n' ' ' | xargs echo 2>/dev/null || true)"
  fi
  echo "${pids}"
}

function _pid_cwd_is_workspace() {
  local pid="$1"
  local cwd=""
  if [[ -r "/proc/${pid}/cwd" ]]; then
    cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
  fi
  [[ -n "${cwd}" ]] && [[ "${cwd}" == "${WORKSPACE_FOLDER}"* ]]
}

function _kill_port_if_matches_cmd() {
  local port="$1"
  local must_contain="$2"  # substring to match in cmdline
  local name="${3:-}"

  local pids
  pids="$(_pids_listening_on_port "${port}")"
  [[ -n "${pids}" ]] || return 0

  local pid args
  for pid in ${pids}; do
    args="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
    if [[ -z "${args}" ]]; then
      continue
    fi
    # Kill only when we're confident it's our workspace process.
    # Some environments may already have other ragflow_server processes running as root.
    local match=0
    if [[ "${args}" == *"${must_contain}"* ]]; then
      match=1
    elif _pid_cwd_is_workspace "${pid}" && [[ "${args}" == *"api/ragflow_server.py"* ]]; then
      match=1
    fi
    [[ "${match}" -eq 1 ]] || continue
    echo "[stop] ${name:-port ${port}}: killing listener pid=${pid} (matched: ${must_contain})"
    kill "${pid}" 2>/dev/null || true
    sleep 0.3
    if is_process_running "${pid}"; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  done
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

  # Enable HTTP access logs from Flask/Werkzeug by default.
  # - If LOG_LEVELS is empty: set root=INFO,werkzeug=INFO
  # - If LOG_LEVELS exists but has no werkzeug: append werkzeug=INFO
  # - If LOG_LEVELS exists but has no root: prepend root=INFO
  local _log_levels="${LOG_LEVELS:-}"
  if [[ -z "${_log_levels}" ]]; then
    _log_levels="root=INFO,werkzeug=INFO"
  else
    if [[ "${_log_levels}" != *"werkzeug="* ]]; then
      _log_levels="${_log_levels},werkzeug=INFO"
    fi
    if [[ "${_log_levels}" != *"root="* ]]; then
      _log_levels="root=INFO,${_log_levels}"
    fi
  fi
  echo "LOG_LEVELS=${_log_levels}"

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
  local port=""
  # Extract port from pidfile name for ragflow_server (e.g., ragflow_server_9390.pid -> 9390)
  if [[ "${name}" == "ragflow_server" ]] && [[ "${pid_file}" =~ ragflow_server_([0-9]+)\.pid ]]; then
    port="${BASH_REMATCH[1]}"
  fi
  
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
  
  # For ragflow_server, check if port is still listening (child process may have outlived parent)
  if [[ -n "${port}" ]] && _port_is_listening "${port}"; then
    local listening_pids
    listening_pids="$(_pids_listening_on_port "${port}")"
    if [[ -n "${listening_pids}" ]]; then
      local child_pid
      for child_pid in ${listening_pids}; do
        # Only kill processes from our workspace
        if _pid_cwd_is_workspace "${child_pid}"; then
          local args
          args="$(ps -p "${child_pid}" -o args= 2>/dev/null || true)"
          if [[ "${args}" == *"api/ragflow_server.py"* ]]; then
            echo "[stop] ${name} (child PID: ${child_pid} on port ${port})"
            kill "${child_pid}" 2>/dev/null || true
            sleep 0.5
            if is_process_running "${child_pid}"; then
              kill -9 "${child_pid}" 2>/dev/null || true
            fi
          fi
        fi
      done
    fi
  fi
  
  rm -f "${pid_file}"
}

function _validate_port() {
  local port="$1"
  [[ "${port}" =~ ^[0-9]+$ ]] && [[ "${port}" -ge 1 ]] && [[ "${port}" -le 65535 ]]
}

function _port_is_listening() {
  local port="$1"
  # ss without -p doesn't require extra privileges
  ss -ltn "( sport = :${port} )" 2>/dev/null | grep -q ":${port} "
}

function _pid_from_pidfile() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  cat "${pid_file}" 2>/dev/null | tr -d '[:space:]'
}

function _pidfile_is_running() {
  local pid_file="$1"
  local pid
  pid="$(_pid_from_pidfile "${pid_file}")"
  [[ -n "${pid}" ]] && is_process_running "${pid}"
}

function _preflight_port_or_running() {
  # If pidfile indicates the component is already running, treat as OK (will be skipped by start_*).
  # Otherwise, the port must be free; we do NOT stop/kill anything in start.
  local name="$1"
  local pid_file="$2"
  local port="$3"
  local hint="$4"

  if _pidfile_is_running "${pid_file}"; then
    return 0
  fi

  if _port_is_listening "${port}"; then
    echo "ERROR: ${name} port ${port} is already in use. start will not stop existing processes." >&2
    echo "Hint: inspect listener: ss -ltnp '( sport = :${port} )'  (or lsof -nP -iTCP:${port} -sTCP:LISTEN)" >&2
    [[ -n "${hint}" ]] && echo "Hint: ${hint}" >&2
    return 1
  fi
  return 0
}

function _preflight_start_all() {
  # Goal: if anything would fail to start due to port conflicts, fail BEFORE starting any new process.
  local fail=0

  # ragflow_server instances
  local idx port pid_file
  for (( idx=0; idx<${SVR_COUNT}; idx++ )); do
    if [[ "${idx}" -eq 0 ]]; then
      port="${SVR_HTTP_PORT}"
    else
      port=$((SVR_EXTRA_BASE_HTTP_PORT + idx - 1))
    fi
    pid_file="${PID_DIR}/ragflow_server_${port}.pid"
    if ! _preflight_port_or_running "ragflow_server" "${pid_file}" "${port}" "pick another port: --svr-http-port / --svr-extra-base-http-port (or stop/restart first)"; then
      fail=1
    fi
  done

  # nginx web frontend/proxy (if enabled)
  if [[ "${ENABLE_WEBSERVER}" -eq 1 ]]; then
    if ! _preflight_port_or_running "nginx(web)" "${PID_DIR}/web_frontend.pid" "${WEB_PORT}" "pick another port: --web-port=<free_port> (or stop/restart first)"; then
      fail=1
    fi
  fi

  # admin_server (if enabled)
  if [[ "${ENABLE_ADMIN_SERVER}" -eq 1 ]]; then
    if ! _preflight_port_or_running "admin_server" "${PID_DIR}/admin_server.pid" "${ADMIN_SVR_HTTP_PORT}" "pick another port: --admin-svr-http-port=<free_port> (or stop/restart first)"; then
      fail=1
    fi
  fi

  # mcp_server (if enabled)
  if [[ "${ENABLE_MCP_SERVER}" -eq 1 ]]; then
    if ! _preflight_port_or_running "mcp_server" "${PID_DIR}/mcp_server.pid" "${MCP_PORT}" "pick another port: --mcp-port=<free_port> (or disable mcp_server)"; then
      fail=1
    fi
  fi

  # powerrag_server (if enabled)
  if [[ "${ENABLE_POWERRAG_SERVER}" -eq 1 ]]; then
    if ! _preflight_port_or_running "powerrag_server" "${PID_DIR}/powerrag_server.pid" "${POWERRAG_PORT}" "pick another port: --powerrag-port=<free_port> (or disable powerrag_server)"; then
      fail=1
    fi
  fi

  [[ "${fail}" -eq 0 ]]
}

function _check_ports_available() {
  # Fail-fast if any target port is already in use by another service.
  # We consider it "available" only if nothing is listening.
  local -a ports=("$@")
  local port
  for port in "${ports[@]}"; do
    if ! _port_is_listening "${port}"; then
      continue
    fi

    echo "ERROR: port ${port} is already in use by another service." >&2
    echo "Hint: check with: ss -ltnp '( sport = :${port} )'  (or run as root to see process)" >&2
    if [[ "${port}" -eq "${ADMIN_SVR_HTTP_PORT}" ]]; then
      echo "Hint: ${port} is the admin_server default port (ADMIN_SVR_HTTP_PORT). Use: --admin-svr-http-port=<free_port>" >&2
    elif [[ "${port}" -eq "${WEB_PORT}" ]]; then
      echo "Hint: ${port} is the nginx web port (WEB_PORT). Use: --web-port=<free_port>" >&2
    elif [[ "${port}" -eq "${MCP_PORT}" ]]; then
      echo "Hint: ${port} is the mcp_server port (MCP_PORT). Use: --mcp-port=<free_port> or disable mcp_server" >&2
    elif [[ "${port}" -eq "${POWERRAG_PORT}" ]]; then
      echo "Hint: ${port} is the powerrag_server port (POWERRAG_PORT). Use: --powerrag-port=<free_port> or disable powerrag_server" >&2
    else
      echo "Hint: if you intend to run multiple ragflow instances, use different ports: --svr-http-port / --svr-extra-base-http-port (and also consider --admin-svr-http-port)" >&2
    fi
    return 1
  done
  return 0
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
    # Align with docker/entrypoint.sh: main instance uses base service conf directly;
    # extra instances use generated per-instance confs.
    if [[ "${idx}" -eq 0 ]]; then
      conf_name="${GLOBAL_SERVICE_CONF}"
    else
      conf_name="service_conf_ragflow_${idx}.yaml"
    fi
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
    if [[ "${idx}" -eq 0 ]]; then
      conf_name="${GLOBAL_SERVICE_CONF}"
    else
      conf_name="service_conf_ragflow_${idx}.yaml"
    fi
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

  local admin_port_for_web="${ADMIN_SVR_HTTP_PORT}"

  # nginx temp dirs (must be writable for non-root runs)
  local nginx_tmp_dir="${NGINX_CONF_DIR}/tmp"
  mkdir -p "${nginx_tmp_dir}/client_body" "${nginx_tmp_dir}/proxy" "${nginx_tmp_dir}/fastcgi" "${nginx_tmp_dir}/uwsgi" "${nginx_tmp_dir}/scgi"

  # Align with docker/entrypoint.sh nginx logic:
  # - generate upstream include files so nginx can proxy/load-balance to all instances
  # - generate proxy.conf snippet for consistent proxy headers/settings
  : > "${NGINX_CONF_DIR}/ragflow_upstream.conf"
  : > "${NGINX_CONF_DIR}/admin_upstream.conf"
  echo "server ${ADMIN_HOST_FOR_WEB}:${admin_port_for_web};" >> "${NGINX_CONF_DIR}/admin_upstream.conf"

  local idx port
  for (( idx=0; idx<${SVR_COUNT}; idx++ )); do
    if [[ "${idx}" -eq 0 ]]; then
      port="${SVR_HTTP_PORT}"
    else
      port=$((SVR_EXTRA_BASE_HTTP_PORT + idx - 1))
    fi
    echo "server ${SERVER_HOST_FOR_WEB}:${port};" >> "${NGINX_CONF_DIR}/ragflow_upstream.conf"
  done

  cat > "${NGINX_CONF_DIR}/proxy.conf" <<'EOF'
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_buffering off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
proxy_buffer_size 1024k;
proxy_buffers 16 1024k;
proxy_busy_buffers_size 2048k;
proxy_temp_file_write_size 2048k;
EOF

  cat > "${NGINX_CONF_DIR}/ragflow.conf" <<EOF
upstream ragflow_upstream {
    include ${NGINX_CONF_DIR}/ragflow_upstream.conf;
}

upstream admin_upstream {
    include ${NGINX_CONF_DIR}/admin_upstream.conf;
}

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
        proxy_pass http://admin_upstream;
        include ${NGINX_CONF_DIR}/proxy.conf;
    }

    location ~ ^/(v1|api) {
        proxy_pass http://ragflow_upstream;
        include ${NGINX_CONF_DIR}/proxy.conf;
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

  # If pidfiles were stale, best-effort kill listeners by port (only if cmd matches our scripts).
  local idx port
  for (( idx=0; idx<${SVR_COUNT}; idx++ )); do
    if [[ "${idx}" -eq 0 ]]; then
      port="${SVR_HTTP_PORT}"
    else
      port=$((SVR_EXTRA_BASE_HTTP_PORT + idx - 1))
    fi
    _kill_port_if_matches_cmd "${port}" "${RAGFLOW_SERVER_PY}" "ragflow_server:${port}"
  done
  _kill_port_if_matches_cmd "${ADMIN_SVR_HTTP_PORT}" "${ADMIN_SERVER_PY}" "admin_server"

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
  # Only processes with pidfiles in PID_DIR are managed by this deploy.sh instance.
  # Other ragflow_server processes on the same machine may be managed by other deploy.sh instances.
  stop_all || true

  # generated per-instance service confs
  rm -f "${CONF_DIR}"/service_conf_ragflow_*.yaml 2>/dev/null || true
  # generated secret key file (align with docker/entrypoint.sh)
  rm -f "${CONF_DIR}/.ragflow_secret_key" 2>/dev/null || true

  # remove runtime dirs entirely (user expectation for clear)
  rm -rf "${NGINX_CONF_DIR}" 2>/dev/null || true
  rm -rf "${PID_DIR}" 2>/dev/null || true
  rm -rf "${LOG_DIR}" 2>/dev/null || true

  echo "[ok] cleared: logs/, pids/, nginx_conf/, conf/service_conf_ragflow_*.yaml, conf/.ragflow_secret_key"
}

function status() {
  echo "=== status ==="

  echo "config:"
  echo "  - service_conf(base) = conf/${GLOBAL_SERVICE_CONF}"
  # Best-effort show ports from the base service conf (more accurate than defaults when status is run without flags).
  local base_ragflow_port="${SVR_HTTP_PORT}"
  local base_admin_port="${ADMIN_SVR_HTTP_PORT}"
  if [[ -f "${CONF_DIR}/${GLOBAL_SERVICE_CONF}" ]] && [[ -x "${PYTHON}" ]]; then
    local _ports
    _ports="$("${PYTHON}" - <<PY 2>/dev/null || true
import os
from ruamel.yaml import YAML
conf = os.path.join(${CONF_DIR@Q}, ${GLOBAL_SERVICE_CONF@Q})
yaml = YAML(typ="safe")
with open(conf, "r", encoding="utf-8") as f:
    data = yaml.load(f) or {}
rag = (data.get("ragflow") or {}).get("http_port")
adm = (data.get("admin") or {}).get("http_port")
print(f"{rag if rag is not None else ''}\\t{adm if adm is not None else ''}")
PY
)"
    if [[ -n "${_ports}" ]]; then
      base_ragflow_port="$(echo "${_ports}" | awk -F'\t' '{print $1}')"
      base_admin_port="$(echo "${_ports}" | awk -F'\t' '{print $2}')"
      [[ -n "${base_ragflow_port}" ]] || base_ragflow_port="${SVR_HTTP_PORT}"
      [[ -n "${base_admin_port}" ]] || base_admin_port="${ADMIN_SVR_HTTP_PORT}"
    fi
  fi

  echo "  - ragflow main port  = ${base_ragflow_port}"
  echo "  - ragflow extra base = ${SVR_EXTRA_BASE_HTTP_PORT}"
  echo "  - admin port         = ${base_admin_port}"
  echo "  - mcp port           = ${MCP_PORT}"
  echo "  - web port           = ${WEB_PORT}"

  # Build a port -> conf filename map from existing conf files (robust even when status is run with different flags).
  declare -A _ragflow_port_to_conf=()
  if [[ -x "${PYTHON}" ]]; then
    while IFS=$'\t' read -r _p _c; do
      [[ -n "${_p}" && -n "${_c}" ]] || continue
      _ragflow_port_to_conf["${_p}"]="${_c}"
    done < <("${PYTHON}" - <<PY 2>/dev/null || true
import glob, os
from ruamel.yaml import YAML

conf_dir = ${CONF_DIR@Q}
base = os.path.join(conf_dir, ${GLOBAL_SERVICE_CONF@Q})
files = []
if os.path.isfile(base):
    files.append(base)
files.extend(sorted(glob.glob(os.path.join(conf_dir, "service_conf_ragflow_*.yaml"))))

yaml = YAML(typ="safe")
for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.load(fh) or {}
        port = (data.get("ragflow") or {}).get("http_port")
        if port is None:
            continue
        print(f"{int(port)}\t{os.path.basename(f)}")
    except Exception:
        continue
PY
)
  fi

  # ragflow
  echo "ragflow_server:"
  local found=0
  local f pid port idx conf_name conf_path log_path
  for f in "${PID_DIR}"/ragflow_server_*.pid; do
    [[ -f "${f}" ]] || continue
    found=1
    port="$(basename "${f}" | sed 's/ragflow_server_\(.*\)\.pid/\1/')"
    pid="$(cat "${f}" 2>/dev/null || true)"

    # best-effort infer conf name from port
    conf_name="${_ragflow_port_to_conf[${port}]:-(unknown)}"
    # Backward compatible fallback when conf map isn't available
    if [[ "${conf_name}" == "(unknown)" ]]; then
      if [[ "${port}" == "${SVR_HTTP_PORT}" ]]; then
        conf_name="${GLOBAL_SERVICE_CONF}"
      elif [[ "${port}" =~ ^[0-9]+$ ]]; then
        idx=$(( port - SVR_EXTRA_BASE_HTTP_PORT + 1 ))
        if [[ "${idx}" -ge 1 ]]; then
          conf_name="service_conf_ragflow_${idx}.yaml"
        fi
      fi
    fi
    conf_path="conf/${conf_name}"
    log_path="logs/ragflow_server_${port}.log"

    # Try to get actual listening port from process's service conf file
    actual_port="${port}"
    if is_process_running "${pid}" && [[ -f "${CONF_DIR}/${conf_name}" ]] && [[ -x "${PYTHON}" ]]; then
      actual_port="$("${PYTHON}" - <<PY 2>/dev/null || echo "${port}"
import os
from ruamel.yaml import YAML
conf = os.path.join(${CONF_DIR@Q}, ${conf_name@Q})
yaml = YAML(typ="safe")
try:
    with open(conf, "r", encoding="utf-8") as f:
        data = yaml.load(f) or {}
    p = (data.get("ragflow") or {}).get("http_port")
    if p is not None:
        print(int(p))
except Exception:
    pass
PY
)"
      [[ -n "${actual_port}" ]] || actual_port="${port}"
    fi

    # Get actual process listening on the port (may be different from pidfile PID if it's a child process)
    local actual_pid="${pid}"
    local listening_pids
    listening_pids="$(_pids_listening_on_port "${actual_port}")"
    if [[ -n "${listening_pids}" ]]; then
      # Prefer the PID that matches our workspace and is a ragflow_server process
      local candidate_pid
      for candidate_pid in ${listening_pids}; do
        if _pid_cwd_is_workspace "${candidate_pid}"; then
          local args
          args="$(ps -p "${candidate_pid}" -o args= 2>/dev/null || true)"
          if [[ "${args}" == *"api/ragflow_server.py"* ]]; then
            actual_pid="${candidate_pid}"
            break
          fi
        fi
      done
      # If no match found, use first listening PID
      if [[ "${actual_pid}" == "${pid}" ]] && [[ -n "${listening_pids}" ]]; then
        actual_pid="$(echo "${listening_pids}" | awk '{print $1}')"
      fi
    fi

    # Check if pidfile process or actual listening process is running
    local pidfile_running=0
    local listening_running=0
    if is_process_running "${pid}"; then
      pidfile_running=1
    fi
    if [[ "${actual_pid}" != "${pid}" ]] && is_process_running "${actual_pid}"; then
      listening_running=1
    fi

    if [[ "${pidfile_running}" -eq 1 ]] || [[ "${listening_running}" -eq 1 ]]; then
      local port_info="${actual_port}"
      if [[ "${actual_port}" != "${port}" ]]; then
        port_info="${actual_port} (pidfile=${port})"
      fi
      local pid_info="${actual_pid}"
      if [[ "${actual_pid}" != "${pid}" ]]; then
        pid_info="${actual_pid} (pidfile=${pid})"
      fi
      echo "  - [ok] port=${port_info} pid=${pid_info} conf=${conf_path} log=${log_path}"
    else
      echo "  - [down] port=${port} pid=${pid} conf=${conf_path} log=${log_path}"
    fi
  done
  if [[ "${found}" -eq 0 ]]; then
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
  found=0
  local args consumer_arg logf
  for f in "${PID_DIR}"/task_executor_*.pid; do
    [[ -f "${f}" ]] || continue
    found=1
    pid="$(cat "${f}" 2>/dev/null || true)"
    if is_process_running "${pid}"; then
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
  if [[ "${found}" -eq 0 ]]; then
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

# Port validations / conflict checks / occupancy preflight should only block `start`.
# Other actions (stop/status/clear/help) must not fail just because some default ports are occupied by unrelated services.
if [[ "${ACTION}" == "start" ]]; then
  # Validate ports early (best-effort)
  for p in "${SVR_HTTP_PORT}" "${SVR_EXTRA_BASE_HTTP_PORT}" "${ADMIN_SVR_HTTP_PORT}" "${MCP_PORT}" "${POWERRAG_PORT}" "${WEB_PORT}"; do
    if ! _validate_port "${p}"; then
      echo "ERROR: invalid port: ${p}" >&2
      exit 1
    fi
  done

  # Check for duplicates/conflicts within our configured ports
  if ! _check_port_conflicts; then
    exit 1
  fi

  # Preflight all components (atomic start): if anything would fail, don't start anything new.
  if ! _preflight_start_all; then
    exit 1
  fi
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
