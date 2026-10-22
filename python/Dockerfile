# One image for the API, the worker and the migration job; App Platform sets the
# run command per component. Build context is the repository root.
FROM python:3.12-slim-bookworm

RUN pip install --no-cache-dir uv==0.11.32

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/python/.venv \
    AGORA_REPO_ROOT=/app \
    HOME=/tmp/agora \
    TIKTOKEN_CACHE_DIR=/tmp/agora/tiktoken \
    INSPECT_DISPLAY=none \
    PATH=/app/python/.venv/bin:$PATH

RUN groupadd --system agora && useradd --system --gid agora --home-dir /app agora

WORKDIR /app/python

# Dependencies first, so code changes do not reinstall them.
COPY python/pyproject.toml python/uv.lock python/.python-version ./
COPY python/core/pyproject.toml core/pyproject.toml
COPY python/api/pyproject.toml api/pyproject.toml
COPY python/worker/pyproject.toml worker/pyproject.toml
RUN uv sync --frozen --no-dev --all-packages --no-install-workspace --python /usr/local/bin/python3.12

COPY python/ ./
COPY agents/ /app/agents/
COPY seeds/ /app/seeds/
COPY config/ /app/config/
RUN uv sync --frozen --no-dev --all-packages --python /usr/local/bin/python3.12 \
    && mkdir -p /tmp/agora && chown agora:agora /tmp/agora

USER agora
EXPOSE 8000
CMD ["uvicorn", "agora_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
