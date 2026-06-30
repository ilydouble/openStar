#!/bin/sh
set -eu

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_ADMIN_USER="${POSTGRES_ADMIN_USER:-icore_agent}"
POSTGRES_ADMIN_PASSWORD="${POSTGRES_ADMIN_PASSWORD:-change-me}"
POSTGRES_ADMIN_DB="${POSTGRES_ADMIN_DB:-icore_agent_db}"

PAYMENT_DB_USER="${PAYMENT_DB_USER:-icore_payment}"
PAYMENT_DB_PASSWORD="${PAYMENT_DB_PASSWORD:-change-me}"
PAYMENT_DB_NAME="${PAYMENT_DB_NAME:-icore_payment_db}"
PAYMENT_DB_SCHEMA="${PAYMENT_DB_SCHEMA:-payment}"

PAYMENT_DATABASE_URL="${PAYMENT_DATABASE_URL:-postgres://${PAYMENT_DB_USER}:${PAYMENT_DB_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${PAYMENT_DB_NAME}?sslmode=disable&search_path=${PAYMENT_DB_SCHEMA}}"

export PGPASSWORD="$POSTGRES_ADMIN_PASSWORD"

until psql \
  -v ON_ERROR_STOP=1 \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_ADMIN_USER" \
  --dbname "$POSTGRES_ADMIN_DB" \
  --command "SELECT 1" >/dev/null 2>&1; do
  sleep 2
done

psql \
  -v ON_ERROR_STOP=1 \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_ADMIN_USER" \
  --dbname "$POSTGRES_ADMIN_DB" \
  --set=payment_db_user="$PAYMENT_DB_USER" \
  --set=payment_db_password="$PAYMENT_DB_PASSWORD" \
  --set=payment_db_name="$PAYMENT_DB_NAME" <<SQL
SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
  :'payment_db_user',
  :'payment_db_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = :'payment_db_user'
)\gexec

SELECT format(
  'ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
  :'payment_db_user',
  :'payment_db_password'
)\gexec

SELECT format(
  'CREATE DATABASE %I OWNER %I TEMPLATE template0 ENCODING %L',
  :'payment_db_name',
  :'payment_db_user',
  'UTF8'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_database WHERE datname = :'payment_db_name'
)\gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'payment_db_name')\gexec
SELECT format(
  'GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I',
  :'payment_db_name',
  :'payment_db_user'
)\gexec
SQL

psql \
  -v ON_ERROR_STOP=1 \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_ADMIN_USER" \
  --dbname "$PAYMENT_DB_NAME" \
  --set=payment_db_user="$PAYMENT_DB_USER" \
  --set=payment_db_name="$PAYMENT_DB_NAME" \
  --set=payment_db_schema="$PAYMENT_DB_SCHEMA" <<SQL
REVOKE ALL ON SCHEMA public FROM PUBLIC;

SELECT format(
  'CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION %I',
  :'payment_db_schema',
  :'payment_db_user'
)\gexec

SELECT format(
  'ALTER SCHEMA %I OWNER TO %I',
  :'payment_db_schema',
  :'payment_db_user'
)\gexec

SELECT format(
  'ALTER DATABASE %I SET search_path TO %I, public',
  :'payment_db_name',
  :'payment_db_schema'
)\gexec
SQL

migrate \
  -path /migrations \
  -database "$PAYMENT_DATABASE_URL" \
  up
