#!/usr/bin/env sh
set -eu

HOST="${POSTGRES_HOST:-postgres}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-mvp0}"
DB="${POSTGRES_DB:-mvp0}"
MAX_RETRIES="${WAIT_MAX_RETRIES:-30}"

i=1
while [ "$i" -le "$MAX_RETRIES" ]; do
  if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" >/dev/null 2>&1; then
      echo "PostgreSQL is ready at ${HOST}:${PORT}"
      exit 0
    fi
  else
    if python3 -c "import socket; s = socket.create_connection(('$HOST', int('$PORT')), timeout=2); s.close()" >/dev/null 2>&1; then
      echo "PostgreSQL TCP socket is reachable at ${HOST}:${PORT}"
      exit 0
    fi
  fi
  echo "Waiting for PostgreSQL at ${HOST}:${PORT} (attempt ${i}/${MAX_RETRIES})..."
  sleep 1
  i=$((i + 1))
done

echo "ERROR: PostgreSQL at ${HOST}:${PORT} did not become ready in time." >&2
exit 1
