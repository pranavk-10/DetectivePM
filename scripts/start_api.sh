#!/bin/sh
# Apply migrations and load the registry, then serve. Stops at the first failure.
set -e
python -m alembic upgrade head
python -m backend.sources.registry
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
