#!/bin/sh
set -eu

CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-clickhouse}"
CLICKHOUSE_NATIVE_PORT="${CLICKHOUSE_NATIVE_PORT:-9000}"
CLICKHOUSE_DATABASE="${CLICKHOUSE_DATABASE:-icore_logging_db}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-icore_logging}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-}"

password_arg=""
if [ -n "$CLICKHOUSE_PASSWORD" ]; then
  password_arg="--password=$CLICKHOUSE_PASSWORD"
fi

until clickhouse-client \
  --host "$CLICKHOUSE_HOST" \
  --port "$CLICKHOUSE_NATIVE_PORT" \
  --user "$CLICKHOUSE_USER" \
  $password_arg \
  --query "SELECT 1" >/dev/null 2>&1; do
  sleep 2
done

clickhouse-client \
  --host "$CLICKHOUSE_HOST" \
  --port "$CLICKHOUSE_NATIVE_PORT" \
  --user "$CLICKHOUSE_USER" \
  $password_arg \
  --query "CREATE DATABASE IF NOT EXISTS ${CLICKHOUSE_DATABASE}"

migrate \
  -path /migrations \
  -database "clickhouse://${CLICKHOUSE_HOST}:${CLICKHOUSE_NATIVE_PORT}?username=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASSWORD}&database=${CLICKHOUSE_DATABASE}&x-multi-statement=true" \
  up
