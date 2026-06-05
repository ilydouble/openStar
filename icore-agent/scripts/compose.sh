#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_EXAMPLES="${ICORE_COMPOSE_USE_EXAMPLES:-0}"

COMPOSE_FILES=(
  "infrastructure/docker/compose/base.yml"
  "infrastructure/docker/compose/postgres.yml"
  "infrastructure/docker/compose/redis.yml"
  "infrastructure/docker/compose/minio.yml"
  "infrastructure/docker/compose/kafka.yml"
  "infrastructure/docker/compose/click-house.yml"
  "infrastructure/docker/compose/storage-service.yml"
  "infrastructure/docker/compose/logging-service.yml"
  "infrastructure/docker/compose/pi-service.yml"
  "infrastructure/docker/compose/backend.yml"
  "infrastructure/docker/compose/gateway.yml"
)

ENV_FILES=(
  "dotenv/.env.app"
  "dotenv/.env.build"
  "dotenv/.env.database"
  "dotenv/.env.memory"
  "dotenv/.env.minio"
  "dotenv/.env.kafka"
  "dotenv/.env.clickhouse"
  "dotenv/.env.storage"
  "dotenv/.env.logging"
  "dotenv/.env.gateway"
  "dotenv/.env.llm"
  "dotenv/.env.sequential"
  "dotenv/.env.auth"
  "dotenv/.env.rag"
  "dotenv/.env.tools"
  "dotenv/.env.media"
  "dotenv/.env.pi"
)

cmd=(docker compose)

for env_file in "${ENV_FILES[@]}"; do
  full_path="$PROJECT_DIR/$env_file"
  example_path="$full_path.example"

  if [[ "$USE_EXAMPLES" == "1" && -f "$example_path" ]]; then
    cmd+=(--env-file "$example_path")
  elif [[ -f "$full_path" ]]; then
    cmd+=(--env-file "$full_path")
  else
    echo "Missing dotenv file: $env_file" >&2
    echo "Create it from $env_file.example or set ICORE_COMPOSE_USE_EXAMPLES=1 for config validation." >&2
    exit 1
  fi
done

for compose_file in "${COMPOSE_FILES[@]}"; do
  cmd+=(-f "$PROJECT_DIR/$compose_file")
done

exec "${cmd[@]}" "$@"
