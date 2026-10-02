#!/usr/bin/env sh
set -eu

./scripts/wait-for-postgres.sh
alembic upgrade head
