# syntax=docker/dockerfile:1
# Multi-stage build (SCALE-004) producing a hardened, non-root runtime (SEC-007).

# --- Build stage: install the package into an isolated venv ------------------
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

# --- Runtime stage: slim, non-root, read-only-friendly -----------------------
FROM python:3.12-slim AS runtime

# Non-root user with a high UID/GID (SEC-007: UID >= 10000).
RUN groupadd -g 10001 app \
 && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONTAINER=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    PORT=8000 \
    MCP_STATELESS_HTTP=1

USER 10001:10001
EXPOSE 8000

# Liveness/readiness for orchestrators and load balancers.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else 1)"

ENTRYPOINT ["swiss-ip-mcp"]
