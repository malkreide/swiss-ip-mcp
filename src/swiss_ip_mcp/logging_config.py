"""Structured logging for swiss-ip-mcp (audit finding OBS-003).

structlog is configured to emit JSON to **stderr** — never stdout, which is
reserved for the MCP/JSON-RPC protocol on the stdio transport (OBS-004). Each
tool call binds a `tool` name and a `correlation_id` via contextvars
(see `telemetry.traced_tool`), so every log line emitted during a call is
correlated.

Log level is taken from the ``LOG_LEVEL`` env var (default ``INFO``).
"""

from __future__ import annotations

import logging
import os
import sys

import structlog

_configured = False


def setup_logging() -> None:
    """Configure structlog → JSON on stderr. Idempotent."""
    global _configured
    if _configured:
        return

    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, configuring logging on first use."""
    if not _configured:
        setup_logging()
    return structlog.get_logger(name)
