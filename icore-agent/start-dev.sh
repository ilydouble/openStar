#!/usr/bin/env bash
# 本地开发启动脚本，自动加载所有 dotenv 环境变量

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载所有环境变量文件
env_files=(
  "dotenv/.env.app"
  "dotenv/.env.database"
  "dotenv/.env.llm"
  "dotenv/.env.sequential"
  "dotenv/.env.memory"
  "dotenv/.env.auth"
  "dotenv/.env.rag"
  "dotenv/.env.tools"
  "dotenv/.env.media"
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
