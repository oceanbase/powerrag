#!/bin/bash

set -e
set -o pipefail

DEPS_IMAGE="infiniflow/ragflow_deps:latest"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_ROOT"

error_exit() {
    echo "Error: Command failed at line $BASH_LINENO" >&2
    exit 1
}

trap error_exit ERR

docker rm -f ragflow_deps_temp 2>/dev/null || true
docker create --name ragflow_deps_temp "$DEPS_IMAGE" true 2>/dev/null || docker create --name ragflow_deps_temp "$DEPS_IMAGE" /bin/true 2>/dev/null || docker create --name ragflow_deps_temp "$DEPS_IMAGE" /bin/sh -c "exit 0" 2>/dev/null

cleanup_container() {
    docker rm -f ragflow_deps_temp 2>/dev/null || true
}
trap "cleanup_container" EXIT

mkdir -p huggingface.co/InfiniFlow rag/res/deepdoc
docker cp ragflow_deps_temp:/huggingface.co/InfiniFlow/text_concat_xgb_v1.0 huggingface.co/InfiniFlow/text_concat_xgb_v1.0
docker cp ragflow_deps_temp:/huggingface.co/InfiniFlow/deepdoc huggingface.co/InfiniFlow/deepdoc
({ tar --exclude='.*' -cf - huggingface.co/InfiniFlow/text_concat_xgb_v1.0 huggingface.co/InfiniFlow/deepdoc 2>&3 | tar -xf - --strip-components=3 -C rag/res/deepdoc; } 3>&2)

docker cp ragflow_deps_temp:/nltk_data .
docker cp ragflow_deps_temp:/cl100k_base.tiktoken ./9b5ad71b2ce5302211f9c61530b329a4922fc6a4
