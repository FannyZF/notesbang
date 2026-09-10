FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps: LibreOffice (optional slide rendering) + fonts + libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-impress fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
