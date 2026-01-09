#!/bin/bash

# RAGFlow 工具脚本（数据上传和处理相关）
# 使用方法: ./scripts/tools.sh [upload-wiki|stop-upload-wiki|reparse-failed|stop-reparse-failed]

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_FOLDER="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON="${WORKSPACE_FOLDER}/.venv/bin/python"
UPLOAD_WIKI_JSON="${WORKSPACE_FOLDER}/scripts/upload_wiki_json.py"
REPARSE_FAILED_DOCS="${WORKSPACE_FOLDER}/scripts/reparse_failed_documents.py"

# 日志目录
LOG_DIR="${WORKSPACE_FOLDER}/logs"
mkdir -p "${LOG_DIR}"

# PID 文件目录
PID_DIR="${WORKSPACE_FOLDER}/pids"
mkdir -p "${PID_DIR}"

# Ensure runtime exists
if [ ! -x "${PYTHON}" ]; then
    echo "[tools][ERROR] Python venv not found: ${PYTHON}" >&2
    echo "[tools][ERROR] Please run: ${WORKSPACE_FOLDER}/scripts/setup_tools_venv.sh" >&2
    exit 1
fi

# 上传 Wiki JSON 数据
upload_wiki_json() {
    local pid_file="${PID_DIR}/upload_wiki_json.pid"
    
    # 检查是否已经在运行
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Wiki JSON 上传任务已经在运行 (PID: $PID)"
            return 1
        fi
    fi
    
    echo "启动 Wiki JSON 上传任务..."
    cd "${WORKSPACE_FOLDER}"
    
    # 默认参数（可通过环境变量覆盖）
    local api_key="${API_KEY:-}"
    local host="${HOST:-http://127.0.0.1:9380}"
    local data_dir="${WIKI_DATA_DIR:-}"
    local dataset_id="${DATASET_ID:-}"
    local batch_size="${BATCH_SIZE:-1000}"
    local snapshot_file="${WIKI_SNAPSHOT_FILE:-${LOG_DIR}/upload_snapshot.json}"
    local enable_resume="${WIKI_ENABLE_RESUME:-true}"
    
    # 构建命令参数
    local resume_args=""
    if [ "$enable_resume" = "true" ]; then
        resume_args="--resume -s ${snapshot_file}"
    fi
    
    nohup env \
        PYTHONPATH="${WORKSPACE_FOLDER}" \
        "${PYTHON}" "${UPLOAD_WIKI_JSON}" \
        -k "${api_key}" \
        -H "${host}" \
        -d "${data_dir}" \
        -i "${dataset_id}" \
        -b "${batch_size}" \
        ${resume_args} > "${LOG_DIR}/upload_wiki_json.log" 2>&1 &
    
    UPLOAD_PID=$!
    echo $UPLOAD_PID > "$pid_file"
    echo "Wiki JSON 上传任务已启动 (PID: $UPLOAD_PID)"
    echo "日志文件: ${LOG_DIR}/upload_wiki_json.log"
    if [ "$enable_resume" = "true" ]; then
        echo "快照文件: ${snapshot_file}"
        echo "任务支持断点续传"
    fi
}

# 停止 Wiki JSON 上传任务
stop_upload_wiki_json() {
    local pid_file="${PID_DIR}/upload_wiki_json.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo "Wiki JSON 上传任务未运行"
        return 1
    fi
    
    PID=$(cat "$pid_file")
    if ps -p $PID > /dev/null 2>&1; then
        echo "停止 Wiki JSON 上传任务 (PID: $PID)..."
        kill $PID
        rm "$pid_file"
        echo "Wiki JSON 上传任务已停止"
    else
        echo "Wiki JSON 上传任务未运行"
        rm "$pid_file"
    fi
}

# 重新解析失败的文档
reparse_failed_documents() {
    local pid_file="${PID_DIR}/reparse_failed_docs.pid"
    
    # 检查是否已经在运行
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "重新解析失败文档任务已经在运行 (PID: $PID)"
            return 1
        fi
    fi
    
    echo "启动重新解析失败文档任务..."
    cd "${WORKSPACE_FOLDER}"
    
    # 默认参数（可通过环境变量覆盖）
    local api_key="${API_KEY:-}"
    local host="${HOST:-http://127.0.0.1:9380}"
    local dataset_id="${DATASET_ID:-}"
    local batch_size="${BATCH_SIZE:-1000}"
    
    if [ -z "$dataset_id" ]; then
        echo "错误: 必须设置 DATASET_ID 环境变量"
        return 1
    fi
    
    nohup env \
        PYTHONPATH="${WORKSPACE_FOLDER}" \
        "${PYTHON}" "${REPARSE_FAILED_DOCS}" \
        -k "${api_key}" \
        -H "${host}" \
        -i "${dataset_id}" \
        -b "${batch_size}" > "${LOG_DIR}/reparse_failed_docs.log" 2>&1 &
    
    REPARSE_PID=$!
    echo $REPARSE_PID > "$pid_file"
    echo "重新解析失败文档任务已启动 (PID: $REPARSE_PID)"
    echo "日志文件: ${LOG_DIR}/reparse_failed_docs.log"
}

# 停止重新解析失败文档任务
stop_reparse_failed_documents() {
    local pid_file="${PID_DIR}/reparse_failed_docs.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo "重新解析失败文档任务未运行"
        return 1
    fi
    
    PID=$(cat "$pid_file")
    if ps -p $PID > /dev/null 2>&1; then
        echo "停止重新解析失败文档任务 (PID: $PID)..."
        kill $PID
        rm "$pid_file"
        echo "重新解析失败文档任务已停止"
    else
        echo "重新解析失败文档任务未运行"
        rm "$pid_file"
    fi
}

# 查看工具任务状态
status() {
    echo "=== 工具任务状态 ==="
    
    # Wiki JSON Upload
    local upload_pid_file="${PID_DIR}/upload_wiki_json.pid"
    if [ -f "$upload_pid_file" ]; then
        PID=$(cat "$upload_pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Wiki JSON Upload: 运行中 (PID: $PID)"
        else
            echo "Wiki JSON Upload: 未运行"
        fi
    else
        echo "Wiki JSON Upload: 未运行"
    fi
    
    # Reparse Failed Documents
    echo ""
    local reparse_pid_file="${PID_DIR}/reparse_failed_docs.pid"
    if [ -f "$reparse_pid_file" ]; then
        PID=$(cat "$reparse_pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Reparse Failed Documents: 运行中 (PID: $PID)"
        else
            echo "Reparse Failed Documents: 未运行"
        fi
    else
        echo "Reparse Failed Documents: 未运行"
    fi
}

# 主函数
case "$1" in
    upload-wiki)
        upload_wiki_json
        ;;
    stop-upload-wiki)
        stop_upload_wiki_json
        ;;
    reparse-failed)
        reparse_failed_documents
        ;;
    stop-reparse-failed)
        stop_reparse_failed_documents
        ;;
    status)
        status
        ;;
    *)
        echo "使用方法: $0 {upload-wiki|stop-upload-wiki|reparse-failed|stop-reparse-failed|status}"
        echo ""
        echo "环境变量:"
        echo ""
        echo "  Wiki 上传相关:"
        echo "    API_KEY        - API Key"
        echo "    HOST           - 服务器地址 (默认: http://127.0.0.1:9380)"
        echo "    WIKI_DATA_DIR       - 数据目录"
        echo "    DATASET_ID     - 数据集 ID (可选)"
        echo "    BATCH_SIZE     - 批量大小 (默认: 1000)"
        echo "    WIKI_SNAPSHOT_FILE  - 快照文件路径 (默认: \${LOG_DIR}/upload_snapshot.json)"
        echo "    WIKI_ENABLE_RESUME  - 是否启用断点续传 (默认: true)"
        echo ""
        echo "  重新解析失败文档相关:"
        echo "    API_KEY     - API Key"
        echo "    HOST        - 服务器地址 (默认: http://127.0.0.1:9380)"
        echo "    DATASET_ID  - 数据集 ID (必需)"
        echo "    BATCH_SIZE  - 批量大小 (默认: 1000)"
        echo ""
        echo "示例:"
        echo "  $0 upload-wiki        # 上传 Wiki JSON 数据（后台运行，支持断点续传）"
        echo "  $0 stop-upload-wiki   # 停止 Wiki JSON 上传任务"
        echo "  BATCH_SIZE=2000 $0 upload-wiki        # 使用自定义批量大小上传"
        echo "  WIKI_ENABLE_RESUME=false $0 upload-wiki    # 禁用断点续传"
        echo "  DATASET_ID=xxx $0 reparse-failed   # 重新解析指定数据集中失败的文档"
        echo "  $0 stop-reparse-failed # 停止重新解析失败文档任务"
        echo "  $0 status             # 查看工具任务状态"
        exit 1
        ;;
esac

