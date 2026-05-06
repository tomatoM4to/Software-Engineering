#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: ./server.sh <command>

Commands:
  dev     FastAPI 개발 서버 시작 (스케줄러 비활성화)
EOF
}

cmd="${1:-}"

case "$cmd" in
  dev)
    echo "🚀 Starting FastAPI development server..."
    DISABLE_SCHEDULER=true uv run fastapi dev
    ;;
  *)
    usage
    exit 1
    ;;
esac