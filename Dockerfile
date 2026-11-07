# Shared image for the API and the worker. The service's command picks the role.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY scripts ./scripts
COPY backend ./backend
RUN rm -rf backend/tests backend/*.db backend/*.csv

USER app
EXPOSE 8000

# Default role is the API. The worker overrides this with `python -m backend.worker`.
CMD ["sh", "scripts/start_api.sh"]
