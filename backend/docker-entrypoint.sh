#!/bin/sh
set -e

# Apply database migrations, then run the given command (uvicorn/celery).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running alembic upgrade head..."
  alembic upgrade head
fi

exec "$@"
