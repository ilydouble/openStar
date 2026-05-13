#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

required_env_files=(
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

for env_file in "${required_env_files[@]}"; do
  if [[ ! -f "$env_file" ]]; then
    echo "Missing $env_file. Copy $env_file.example and fill local values." >&2
    exit 1
  fi
done

exec docker compose \
  --env-file dotenv/.env.app \
  --env-file dotenv/.env.database \
  --env-file dotenv/.env.llm \
  --env-file dotenv/.env.sequential \
  --env-file dotenv/.env.memory \
  --env-file dotenv/.env.auth \
  --env-file dotenv/.env.rag \
  --env-file dotenv/.env.tools \
  --env-file dotenv/.env.media \
  -f docker-compose.yml \
  "$@"
