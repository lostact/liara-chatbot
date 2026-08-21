FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pre-install dependencies to utilize Docker layer cache
COPY services/shared/pyproject.toml /app/services/shared/
COPY services/indexer/pyproject.toml /app/services/indexer/

RUN pip install \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.2.0" \
    "sqlalchemy>=2.0.30" \
    "asyncpg>=0.29.0" \
    "pgvector>=0.2.5" \
    "alembic>=1.13.1" \
    "redis>=5.0.4" \
    "arq>=0.25.0" \
    "httpx>=0.27.0" \
    "socksio>=1.0.0" \
    "python-frontmatter>=1.1.0" \
    "pyyaml>=6.0.1" \
    "GitPython>=3.1.43" \
    "prometheus-client>=0.20.0" \
    "honcho>=1.1.0"

# Copy application source code
COPY services/shared /app/services/shared
COPY services/indexer /app/services/indexer

# Install packages in editable mode without redownloading dependencies
RUN pip install --no-deps -e /app/services/shared -e /app/services/indexer

WORKDIR /app/services/indexer

EXPOSE 8001

CMD ["sh", "-c", "alembic upgrade head && honcho start"]
