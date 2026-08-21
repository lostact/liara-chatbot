FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pre-install dependencies to utilize Docker layer cache
COPY services/shared/pyproject.toml /app/services/shared/
COPY services/chat_api/pyproject.toml /app/services/chat_api/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.2.0" \
    "sqlalchemy>=2.0.30" \
    "asyncpg>=0.29.0" \
    "pgvector>=0.2.5" \
    "redis>=5.0.4" \
    "httpx>=0.27.0" \
    "socksio>=1.0.0" \
    "langgraph>=0.0.60" \
    "langchain-core>=0.2.0" \
    "jinja2>=3.1.4" \
    "prometheus-client>=0.20.0"

# Copy application source code and built widget bundle
COPY services/shared /app/services/shared
COPY services/chat_api /app/services/chat_api
COPY widget/dist /app/widget/dist

# Install packages in editable mode without redownloading dependencies
RUN pip install --no-deps -e /app/services/shared -e /app/services/chat_api

WORKDIR /app/services/chat_api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
