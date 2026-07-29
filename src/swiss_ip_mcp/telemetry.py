"""OpenTelemetry tracing for swiss-ip-mcp (audit finding OBS-006).

Design goals:

* **Zero-config local use.** Spans are created through the OpenTelemetry *API*
  only (`opentelemetry-api`, a transitive dependency). Without a configured
  TracerProvider these are cheap no-ops, so stdio users pay nothing and need no
  collector.
* **Opt-in export.** `setup_telemetry()` installs the SDK TracerProvider, an
  OTLP exporter and httpx auto-instrumentation — but only when telemetry is
  enabled via env and the optional `otel` extra is installed. Missing packages
  degrade to a logged no-op instead of crashing the server.
* **No sensitive data.** Span attributes carry only the tool name and an
  error flag — never query arguments, tokens or response bodies.

Enable with either:

* ``MCP_OTEL_ENABLED=1`` (uses the standard ``OTEL_EXPORTER_OTLP_ENDPOINT`` /
  ``OTEL_*`` env vars), or
* setting ``OTEL_EXPORTER_OTLP_ENDPOINT`` directly.
"""
from __future__ import annotations

import functools
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog
from opentelemetry import trace

from swiss_ip_mcp.logging_config import get_logger

logger = get_logger("swiss_ip_mcp")

SERVICE_NAME = "swiss-ip-mcp"

# API-level tracer: resolves to the active provider at span-creation time, or a
# no-op when none is configured.
tracer = trace.get_tracer(SERVICE_NAME)

_F = TypeVar("_F", bound=Callable[..., Awaitable[str]])


def telemetry_enabled() -> bool:
    """True when tracing export is requested via environment."""
    flag = os.getenv("MCP_OTEL_ENABLED", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def mark_error(is_error: bool) -> None:
    """Tag the current tool span with the execution-error flag (no PII)."""
    span = trace.get_current_span()
    if span is not None:
        span.set_attribute("mcp.tool.result.is_error", bool(is_error))


def traced_tool(func: _F) -> _F:
    """Wrap an MCP tool handler with a span and bound log context.

    Adds an OpenTelemetry span (`mcp.tool.name`, `mcp.tool.result.is_error`)
    and binds a per-call `tool` + `correlation_id` into the structlog context
    (OBS-003), so every log line emitted during the call is correlated. No
    arguments are logged (no PII).

    `functools.wraps` keeps the original signature so MCPServer's input-schema
    introspection is unaffected.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        correlation_id = uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(
            tool=func.__name__, correlation_id=correlation_id
        )
        with tracer.start_as_current_span(f"mcp.tool/{func.__name__}") as span:
            span.set_attribute("mcp.tool.name", func.__name__)
            span.set_attribute("mcp.tool.result.is_error", False)
            logger.info("tool.call.start")
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                # Tool raised → the client will receive isError=true (OBS-001).
                span.set_attribute("mcp.tool.result.is_error", True)
                span.record_exception(exc)
                logger.warning("tool.call.error", error_type=type(exc).__name__)
                raise
            finally:
                logger.debug("tool.call.end")
                structlog.contextvars.unbind_contextvars("tool", "correlation_id")

    return wrapper  # type: ignore[return-value]


def setup_telemetry() -> bool:
    """Install the SDK TracerProvider + OTLP exporter + httpx instrumentation.

    Returns True when tracing export was activated, False otherwise (disabled
    by env, or optional packages not installed — both are non-fatal).
    """
    if not telemetry_enabled():
        return False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("otel_extra_missing", hint="pip install 'swiss-ip-mcp[otel]'")
        return False

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "deployment.environment": os.getenv("MCP_ENV", "production"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    # Backend Swissreg/IDP calls become child spans automatically.
    HTTPXClientInstrumentor().instrument()

    logger.info("otel_tracing_enabled", service_name=SERVICE_NAME)
    return True
