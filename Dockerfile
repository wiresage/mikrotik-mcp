FROM python:3.11-alpine AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Build the venv on this image's own interpreter and never fetch another one:
# the production stage copies the venv, and its python symlink has to resolve there too.
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_PYTHON_PREFERENCE=only-system

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    python3-dev

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/

RUN uv sync --frozen --no-dev --no-editable

FROM python:3.11-alpine AS production

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

RUN apk add --no-cache \
    libffi \
    openssl \
    && rm -rf /var/cache/apk/*

RUN addgroup -g 1000 mcpuser && adduser -D -u 1000 -G mcpuser mcpuser

WORKDIR /app

# --chown here instead of a recursive chown afterwards: that would copy the whole
# venv into a second layer.
COPY --chown=mcpuser:mcpuser --from=builder /app/.venv ./.venv

COPY --chown=mcpuser:mcpuser --from=builder /app/src ./src

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Mount point for a multi-device inventory, e.g.
#   -v "$PWD/inventory.yaml:/config/inventory.yaml:ro" -e MIKROTIK_INVENTORY_FILE=/config/inventory.yaml
# Keeping credentials in a mounted file keeps them out of `docker inspect`,
# unlike passing them through the environment.
RUN mkdir -p /config

RUN chown mcpuser:mcpuser /app /config
USER mcpuser

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
