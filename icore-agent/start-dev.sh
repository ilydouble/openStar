#!/usr/bin/env bash
# 本地开发启动脚本，自动加载所有 dotenv 环境变量

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载所有环境变量文件
env_files=(
  "dotenv/dev/.env.app"
  "dotenv/dev/.env.agent"
  "dotenv/dev/.env.database"
  "dotenv/dev/.env.llm"
  "dotenv/dev/.env.memory"
  "dotenv/dev/.env.auth"
  "dotenv/dev/.env.rag"
  "dotenv/dev/.env.tools"
  "dotenv/dev/.env.media"
  "dotenv/dev/.env.storage"
  "dotenv/dev/.env.logging"
)

echo "📦 加载环境变量..."
for env_file in "${env_files[@]}"; do
  if [[ -f "$env_file" ]]; then
    echo "   ✓ $env_file"
    set -a  # 自动导出所有变量
    source "$env_file"
    set +a
  else
    echo "   ⚠ $env_file 不存在，跳过"
  fi
done

# Redis 使用宿主机映射端口（Docker 映射到 127.0.0.1:16379）
export REDIS_URL=redis://localhost:16379/0

# Local uvicorn runs outside Docker, so Compose service DNS names are not
# resolvable here. Use the host-published helper-service ports by default.
if [[ "${STORAGE_SERVICE_URL:-}" == "" || "${STORAGE_SERVICE_URL:-}" == "http://storage-service:8090" ]]; then
  export STORAGE_SERVICE_URL=http://127.0.0.1:18090
fi
if [[ "${LOGGING_SERVICE_URL:-}" == "" || "${LOGGING_SERVICE_URL:-}" == "http://logging-service:8091" ]]; then
  export LOGGING_SERVICE_URL=http://127.0.0.1:18091
fi
export STORAGE_SERVICE_TOKEN="${STORAGE_SERVICE_TOKEN:-dev-storage-service-token}"
export LOGGING_SERVICE_TOKEN="${LOGGING_SERVICE_TOKEN:-dev-logging-service-token}"

# 设置 PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH:-}"

echo ""
echo "🚀 启动后端服务..."
echo "   后端地址: http://localhost:8080"
echo "   API 文档: http://localhost:8080/docs"
echo "   AUTH_ENABLED=$AUTH_ENABLED"
echo ""

# 启动 uvicorn
exec /opt/miniconda3/envs/dp/bin/python -m uvicorn icore_agent.main:app --reload --host 0.0.0.0 --port 8080
