#!/usr/bin/env bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
SELECT 'CREATE DATABASE icore_agent_test_db'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'icore_agent_test_db'
)\gexec
SQL
