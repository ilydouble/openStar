#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_EXAMPLES="${ICORE_COMPOSE_USE_EXAMPLES:-0}"

MODE="dev"
if [[ "${1:-}" == "dev" ]]; then
  MODE="dev"
  shift
elif [[ "${1:-}" == "production" || "${1:-}" == "prod" ]]; then
  MODE="production"
  shift
fi

case "$MODE" in
  dev)
    COMPOSE_FILES=(
      "infrastructure/docker/compose/dev/base.yml"
      "infrastructure/docker/compose/dev/postgres.yml"
      "infrastructure/docker/compose/dev/payment-service.yml"
      "infrastructure/docker/compose/dev/redis.yml"
      "infrastructure/docker/compose/dev/minio.yml"
      "infrastructure/docker/compose/dev/kafka.yml"
      "infrastructure/docker/compose/dev/click-house.yml"
      "infrastructure/docker/compose/dev/storage-service.yml"
      "infrastructure/docker/compose/dev/logging-service.yml"
      "infrastructure/docker/compose/dev/backend.yml"
      "infrastructure/docker/compose/dev/gateway.yml"
    )
    ;;
  production)
    COMPOSE_FILES=(
      "infrastructure/docker/compose/production/base.yml"
      "infrastructure/docker/compose/production/minio.yml"
      "infrastructure/docker/compose/production/kafka.yml"
      "infrastructure/docker/compose/production/click-house.yml"
      "infrastructure/docker/compose/production/storage-service.yml"
      "infrastructure/docker/compose/production/logging-service.yml"
      "infrastructure/docker/compose/production/payment-service.yml"
      "infrastructure/docker/compose/production/backend.yml"
      "infrastructure/docker/compose/production/gateway.yml"
    )
    ;;
  *)
    echo "Unsupported compose mode: $MODE" >&2
    exit 1
    ;;
esac

ENV_FILES=(
  "dotenv/$MODE/.env.app"
  "dotenv/$MODE/.env.agent"
  "dotenv/$MODE/.env.build"
  "dotenv/$MODE/.env.database"
  "dotenv/$MODE/.env.payment"
  "dotenv/$MODE/.env.memory"
  "dotenv/$MODE/.env.minio"
  "dotenv/$MODE/.env.kafka"
  "dotenv/$MODE/.env.clickhouse"
  "dotenv/$MODE/.env.storage"
  "dotenv/$MODE/.env.logging"
  "dotenv/$MODE/.env.gateway"
  "dotenv/$MODE/.env.llm"
  "dotenv/$MODE/.env.auth"
  "dotenv/$MODE/.env.rag"
  "dotenv/$MODE/.env.tools"
  "dotenv/$MODE/.env.media"
)

export ICORE_COMPOSE_DOTENV_DIR="$PROJECT_DIR/dotenv/$MODE"
export ICORE_COMPOSE_ENV_SUFFIX=""
if [[ "$USE_EXAMPLES" == "1" ]]; then
  ICORE_COMPOSE_ENV_SUFFIX=".example"
fi

read_env_value() {
  local key="$1"
  local file="$2"
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$file"
}

normalize_proxy_url() {
  local value="$1"

  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  if [[ -z "$value" || "$value" == *"://"* ]]; then
    printf '%s' "$value"
    return
  fi

  case "$value" in
    http:*|https:*|socks4:*|socks5:*)
      printf '%s://%s' "${value%%:*}" "${value#*:}"
      ;;
    *)
      printf 'http://%s' "$value"
      ;;
  esac
}

# Return success when the compose command can create new production containers.
requires_external_network() {
  local arg

  for arg in "$@"; do
    case "$arg" in
      up|create|run)
        return 0
        ;;
    esac
  done

  return 1
}

BUILD_ENV_FILE="$PROJECT_DIR/dotenv/$MODE/.env.build"
BUILD_EXAMPLE_FILE="$BUILD_ENV_FILE.example"
http_proxy_value="${BUILD_HTTP_PROXY-}"
https_proxy_value="${BUILD_HTTPS_PROXY-}"

if [[ -z "$http_proxy_value" && -f "$BUILD_ENV_FILE" ]]; then
  http_proxy_value="$(read_env_value "BUILD_HTTP_PROXY" "$BUILD_ENV_FILE")"
elif [[ -z "$http_proxy_value" && "$USE_EXAMPLES" == "1" && -f "$BUILD_EXAMPLE_FILE" ]]; then
  http_proxy_value="$(read_env_value "BUILD_HTTP_PROXY" "$BUILD_EXAMPLE_FILE")"
fi
if [[ -z "$https_proxy_value" && -f "$BUILD_ENV_FILE" ]]; then
  https_proxy_value="$(read_env_value "BUILD_HTTPS_PROXY" "$BUILD_ENV_FILE")"
elif [[ -z "$https_proxy_value" && "$USE_EXAMPLES" == "1" && -f "$BUILD_EXAMPLE_FILE" ]]; then
  https_proxy_value="$(read_env_value "BUILD_HTTPS_PROXY" "$BUILD_EXAMPLE_FILE")"
fi

export BUILD_HTTP_PROXY
export BUILD_HTTPS_PROXY
BUILD_HTTP_PROXY="$(normalize_proxy_url "$http_proxy_value")"
BUILD_HTTPS_PROXY="$(normalize_proxy_url "$https_proxy_value")"

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
  full_path="$PROJECT_DIR/$compose_file"
  if [[ ! -f "$full_path" ]]; then
    echo "Missing compose file: $compose_file" >&2
    exit 1
  fi
  cmd+=(-f "$full_path")
done

if [[ "$MODE" == "production" ]] && requires_external_network "$@"; then
  app_env_file="$PROJECT_DIR/dotenv/production/.env.app$ICORE_COMPOSE_ENV_SUFFIX"
  infra_network_name="${ICORE_INFRA_ACCESS_NETWORK_NAME-}"
  if [[ -z "$infra_network_name" && -f "$app_env_file" ]]; then
    infra_network_name="$(read_env_value "ICORE_INFRA_ACCESS_NETWORK_NAME" "$app_env_file")"
  fi
  infra_network_name="${infra_network_name%\"}"
  infra_network_name="${infra_network_name#\"}"
  infra_network_name="${infra_network_name%\'}"
  infra_network_name="${infra_network_name#\'}"
  infra_network_name="${infra_network_name:-project-icore-agent-infra-access}"

  if ! docker network inspect "$infra_network_name" >/dev/null 2>&1; then
    echo "Missing production infrastructure network: $infra_network_name" >&2
    echo "Create and attach the required infrastructure services before starting production." >&2
    exit 1
  fi
fi

exec "${cmd[@]}" "$@"
