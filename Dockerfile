FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GUARDIAN_PERSIST=1 \
    GUARDIAN_DB_PATH=/app/data/traces.db

WORKDIR /app

# 先装依赖，利用层缓存
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "pydantic>=2.6" \
    "jsonschema>=4.21" \
    "rapidfuzz>=3.6" \
    "structlog>=24.1" \
    "prometheus-client>=0.20" \
    "httpx>=0.27" \
    "pyyaml>=6.0"

COPY app ./app

RUN mkdir -p /app/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
