#!/usr/bin/env bash
# ============================================================
# 智护银伴 · API-only 本地启动脚本
# 适用场景：受限网络 / 无 GPU / 无 Ollama，走远程 LLM API
#
# 前提：
#   1. 已安装 requirements-api.txt 依赖
#   2. .env 已配好 LLM_PROVIDER=openai + OPENAI_API_BASE 等
#   3. 设 EMBEDDING_DISABLED=true（避免下载 embedding 模型）
#
# 用法：
#   chmod +x scripts/run-api-local.sh
#   ./scripts/run-api-local.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# 默认值（可通过 .env 覆盖）
export EMBEDDING_DISABLED="${EMBEDDING_DISABLED:-true}"
export EMBEDDING_ALLOW_DEGRADED="${EMBEDDING_ALLOW_DEGRADED:-true}"
export HOST="${HOST:-127.0.0.1}"
export PORT="${PORT:-8000}"
export WORKERS="${WORKERS:-1}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  智护银伴 · API-only 本地启动                           ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  EMBEDDING_DISABLED = $EMBEDDING_DISABLED"
echo "║  LLM_PROVIDER       = ${LLM_PROVIDER:-ollama}"
echo "║  HOST:PORT           = $HOST:$PORT"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

exec uvicorn main:app --host "$HOST" --port "$PORT" --workers "$WORKERS"
