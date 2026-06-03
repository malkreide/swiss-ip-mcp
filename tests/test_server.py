"""
Tests for swiss-ip-mcp server.

Unit tests mock the IGE API; integration (smoke) tests require live credentials
and are skipped automatically if IGE_USERNAME is not set.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swiss_ip_mcp.server import (
    _build_patent_search,
    _build_spc_search,
    _build_trademark_search,
    _esc,
    _handle_error,
    _local,
    _parse_result_page,
    _quota_request,
    swiss_ip_get_patent,
    swiss_ip_get_quota,
    swiss_ip_get_trademark,
    swiss_ip_search_patent_publications,
    swiss_ip_search_patents,
    swiss_ip_search_patents_by_applicant,
    swiss_ip_search_recent_filings,
    swiss_ip_search_spc,
    swiss_ip_search_trademarks,
    swiss_ip_search_trademarks_by_class,
    swiss_ip_search_trademarks_by_owner,
)

LIVE = bool(os.getenv("IGE_USERNAME"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse xmlns="urn:ige:schema:xsd:datadeliverycore-1.0.0">
  <Result>
    <Meta><TotalCount>42</TotalCount></Meta>
    <Item>
      <ApplicationNumber>P-756001</ApplicationNumber>
      <MarkName>ZÜRITEST</MarkName>
      <Status>Registered</Status>
      <HolderName>Mustermann AG</HolderName>
    </Item>
    <Item>
      <ApplicationNumber>P-756002</ApplicationNumber>
      <MarkName>ZÜRITEST PRO</MarkName>
      <Status>Pending</Status>
      <HolderName>Mustermann AG</HolderName>
    </Item>
  </Result>
</ApiResponse>"""

SAMPLE_EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse xmlns="urn:ige:schema:xsd:datadeliverycore-1.0.0">
  <Result>
    <Meta><TotalCount>0</TotalCount></Meta>
  </Result>
</ApiResponse>"""

SAMPLE_QUOTA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse xmlns="urn:ige:schema:xsd:datadeliverycore-1.0.0">
  <Quota>
    <Used>1024</Used>
    <Limit>104857600</Limit>
    <Remaining>104856576</Remaining>
  </Quota>
</ApiResponse>"""


def _make_root(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


# ---------------------------------------------------------------------------
# Unit tests – XML helpers
# ---------------------------------------------------------------------------

class TestXmlHelpers:
    def test_esc_basic(self):
        assert _esc("a&b") == "a&amp;b"
        assert _esc("<tag>") == "&lt;tag&gt;"
        # Double quotes don't need escaping in element content (only attributes)

    def test_esc_clean(self):
        assert _esc("simple text") == "simple text"

    def test_local_with_ns(self):
        assert _local("{urn:some:ns}LocalName") == "LocalName"

    def test_local_without_ns(self):
        assert _local("PlainTag") == "PlainTag"

    def test_build_trademark_search_basic(self):
        xml = _build_trademark_search("<Any>test</Any>")
        assert "TrademarkSearch" in xml
        assert "<Any>test</Any>" in xml
        assert 'size="10"' in xml

    def test_build_trademark_search_pagination(self):
        xml = _build_trademark_search("<Any>test</Any>", page_token="abc123")
        assert 'token="abc123"' in xml

    def test_build_patent_search(self):
        xml = _build_patent_search("<Any>solar</Any>", page_size=5)
        assert "PatentSearch" in xml
        assert 'size="5"' in xml

    def test_build_spc_search(self):
        xml = _build_spc_search("<Any>Novartis</Any>")
        assert "SPCSearch" in xml

    def test_quota_request(self):
        xml = _quota_request()
        assert "UserQuota" in xml
        assert "UserQuotaRequest" in xml

    def test_parse_result_page_with_items(self):
        root = _make_root(SAMPLE_TM_XML)
        result = _parse_result_page(root)
        assert result["count"] == 2
        assert result["total"] == "42"
        assert result["next_page_token"] is None

    def test_parse_result_page_empty(self):
        root = _make_root(SAMPLE_EMPTY_XML)
        result = _parse_result_page(root)
        assert result["count"] == 0
        assert result["total"] == "0"


# ---------------------------------------------------------------------------
# Unit tests – error handler
# ---------------------------------------------------------------------------

class TestErrorHandler:
    def test_value_error(self):
        msg = _handle_error(ValueError("missing credentials"))
        assert "Konfigurationsfehler" in msg
        assert "missing credentials" in msg

    def test_timeout(self):
        import httpx
        msg = _handle_error(httpx.ReadTimeout("timed out"))
        assert "timed out" in msg.lower() or "timeout" in msg.lower()

    def test_generic_is_masked(self):
        # OBS-002: internal exception detail must NOT leak to the client.
        msg = _handle_error(RuntimeError("boom secret stacktrace"))
        assert "boom" not in msg
        assert "Server-Log" in msg

    def test_http_error_body_is_masked(self):
        import httpx

        resp = MagicMock(status_code=500)
        resp.text = "SECRET upstream body with internals"
        err = httpx.HTTPStatusError("500", request=MagicMock(), response=resp)
        msg = _handle_error(err)
        assert "SECRET" not in msg
        assert "500" in msg


# ---------------------------------------------------------------------------
# Unit tests – tools (mocked API)
# ---------------------------------------------------------------------------

class TestToolDescriptions:
    @pytest.mark.asyncio
    async def test_all_tools_have_use_case_tag(self):
        # ARCH-002: every tool description carries a <use_case> tag.
        from swiss_ip_mcp.server import mcp

        tools = await mcp.list_tools()
        assert len(tools) == 11
        missing = [t.name for t in tools if "<use_case>" not in (t.description or "")]
        assert not missing, f"tools missing <use_case>: {missing}"


class TestProvenance:
    @pytest.mark.asyncio
    async def test_search_envelope_has_source_and_results(self):
        # CH-004 / SDK-002: every response carries provenance + a results envelope.
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            result = json.loads(
                await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
            )
        assert result["source"]["name"].startswith("Swissreg")
        assert "license" in result["source"]
        assert isinstance(result["results"], list)
        assert result["count"] == len(result["results"])

    @pytest.mark.asyncio
    async def test_match_type_exact_on_hits(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            result = json.loads(
                await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
            )
        assert result["match_type"] == "exact"
        assert "suggestion" not in result

    @pytest.mark.asyncio
    async def test_match_type_none_with_suggestion_on_empty(self):
        # ARCH-003: empty search yields match_type=none + actionable suggestion.
        root = _make_root(SAMPLE_EMPTY_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentSearchInput
            result = json.loads(
                await swiss_ip_search_patents(PatentSearchInput(query="zzzznomatch"))
            )
        assert result["match_type"] == "none"
        assert result["count"] == 0
        assert "Wildcard" in result["suggestion"]

    @pytest.mark.asyncio
    async def test_quota_has_source(self):
        root = _make_root(SAMPLE_QUOTA_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result = json.loads(await swiss_ip_get_quota())
        assert result["source"]["provider"].startswith("Swiss Federal Institute")
        assert "quota" in result


class TestTrademarkTools:
    @pytest.mark.asyncio
    async def test_search_trademarks_success(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            params = TrademarkSearchInput(query="ZÜRITEST")
            result_str = await swiss_ip_search_trademarks(params)
            result = json.loads(result_str)
            assert result["count"] == 2
            assert result["total"] == "42"

    @pytest.mark.asyncio
    async def test_search_trademarks_api_error(self):
        import httpx
        err = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock(status_code=401)
        )
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(side_effect=err)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            params = TrademarkSearchInput(query="test")
            result_str = await swiss_ip_search_trademarks(params)
            result = json.loads(result_str)
            assert "error" in result
            assert "401" in result["error"] or "Authentication" in result["error"]

    @pytest.mark.asyncio
    async def test_get_trademark_not_found(self):
        root = _make_root(SAMPLE_EMPTY_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkNumberInput
            params = TrademarkNumberInput(trademark_number="P-000000")
            result_str = await swiss_ip_get_trademark(params)
            result = json.loads(result_str)
            assert "error" in result
            assert "nicht gefunden" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_search_by_owner(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkOwnerSearchInput
            params = TrademarkOwnerSearchInput(owner_name="Mustermann AG")
            result_str = await swiss_ip_search_trademarks_by_owner(params)
            result = json.loads(result_str)
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_search_by_class(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkClassInput
            params = TrademarkClassInput(nice_class=41)
            result_str = await swiss_ip_search_trademarks_by_class(params)
            result = json.loads(result_str)
            assert result["nice_class_searched"] == 41


class TestPatentTools:
    @pytest.mark.asyncio
    async def test_search_patents(self):
        root = _make_root(SAMPLE_TM_XML)  # structure same
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentSearchInput
            params = PatentSearchInput(query="solar*")
            result_str = await swiss_ip_search_patents(params)
            result = json.loads(result_str)
            assert "count" in result

    @pytest.mark.asyncio
    async def test_get_patent_not_found(self):
        root = _make_root(SAMPLE_EMPTY_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentNumberInput
            params = PatentNumberInput(patent_number="CH000000")
            result_str = await swiss_ip_get_patent(params)
            result = json.loads(result_str)
            assert "error" in result

    @pytest.mark.asyncio
    async def test_search_by_applicant(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentApplicantInput
            params = PatentApplicantInput(applicant_name="ABB*")
            result_str = await swiss_ip_search_patents_by_applicant(params)
            result = json.loads(result_str)
            assert "count" in result

    @pytest.mark.asyncio
    async def test_search_patent_publications(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentSearchInput
            params = PatentSearchInput(query="battery*")
            result_str = await swiss_ip_search_patent_publications(params)
            result = json.loads(result_str)
            assert "count" in result


class TestSpcTools:
    @pytest.mark.asyncio
    async def test_search_spc(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import SpcSearchInput
            params = SpcSearchInput(query="Novartis")
            result_str = await swiss_ip_search_spc(params)
            result = json.loads(result_str)
            assert "count" in result


class TestCrossDomainTools:
    @pytest.mark.asyncio
    async def test_search_recent_filings_trademark(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import DateRangeInput
            params = DateRangeInput(
                ip_type="trademark",
                date_from="2025-01-01",
                date_to="2025-02-01",
            )
            result_str = await swiss_ip_search_recent_filings(params)
            result = json.loads(result_str)
            assert result["date_range"]["ip_type"] == "trademark"

    @pytest.mark.asyncio
    async def test_search_recent_filings_patent(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import DateRangeInput
            params = DateRangeInput(
                ip_type="patent",
                date_from="2025-06-01",
                date_to="2025-07-01",
            )
            result_str = await swiss_ip_search_recent_filings(params)
            result = json.loads(result_str)
            assert result["date_range"]["from"] == "2025-06-01"

    @pytest.mark.asyncio
    async def test_get_quota(self):
        root = _make_root(SAMPLE_QUOTA_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result_str = await swiss_ip_get_quota()
            result = json.loads(result_str)
            assert result  # non-empty dict


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_trademark_search_empty_query(self):
        from pydantic import ValidationError

        from swiss_ip_mcp.server import TrademarkSearchInput
        with pytest.raises(ValidationError):
            TrademarkSearchInput(query="")

    def test_patent_page_size_out_of_range(self):
        from pydantic import ValidationError

        from swiss_ip_mcp.server import PatentSearchInput
        with pytest.raises(ValidationError):
            PatentSearchInput(query="test", page_size=0)
        with pytest.raises(ValidationError):
            PatentSearchInput(query="test", page_size=51)

    def test_nice_class_out_of_range(self):
        from pydantic import ValidationError

        from swiss_ip_mcp.server import TrademarkClassInput
        with pytest.raises(ValidationError):
            TrademarkClassInput(nice_class=0)
        with pytest.raises(ValidationError):
            TrademarkClassInput(nice_class=46)

    def test_date_range_invalid_type(self):
        from pydantic import ValidationError

        from swiss_ip_mcp.server import DateRangeInput
        with pytest.raises(ValidationError):
            DateRangeInput(
                ip_type="design",  # not supported
                date_from="2025-01-01",
                date_to="2025-02-01",
            )

    def test_date_format_validation(self):
        from pydantic import ValidationError

        from swiss_ip_mcp.server import DateRangeInput
        with pytest.raises(ValidationError):
            DateRangeInput(
                ip_type="trademark",
                date_from="01.01.2025",  # wrong format
                date_to="2025-02-01",
            )


# ---------------------------------------------------------------------------
# Unit tests – structured logging (OBS-003)
# ---------------------------------------------------------------------------

class TestStructuredLogging:
    def test_get_logger_configures(self):
        from swiss_ip_mcp import logging_config

        logging_config.setup_logging()
        assert logging_config._configured is True
        assert logging_config.get_logger("x") is not None

    @pytest.mark.asyncio
    async def test_tool_call_emits_start_event(self):
        import structlog

        root = _make_root(SAMPLE_TM_XML)
        with structlog.testing.capture_logs() as logs:
            with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
                from swiss_ip_mcp.server import TrademarkSearchInput
                await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        events = [e["event"] for e in logs]
        assert "tool.call.start" in events

    @pytest.mark.asyncio
    async def test_unexpected_error_logged_at_error_level(self):
        import structlog

        with structlog.testing.capture_logs() as logs:
            with patch(
                "swiss_ip_mcp.server._call_api",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                from swiss_ip_mcp.server import TrademarkSearchInput
                await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        errors = [e for e in logs if e["event"] == "unexpected_error"]
        assert errors and errors[0]["log_level"] == "error"
        # no raw exception value leaks into the structured event
        assert "boom" not in str(errors[0])


# ---------------------------------------------------------------------------
# Integration / smoke tests (live, skipped without credentials)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Unit tests – OpenTelemetry tracing (OBS-006)
# ---------------------------------------------------------------------------

class TestTelemetry:
    def test_disabled_by_default(self, monkeypatch):
        from swiss_ip_mcp import telemetry

        monkeypatch.delenv("MCP_OTEL_ENABLED", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        assert telemetry.telemetry_enabled() is False
        assert telemetry.setup_telemetry() is False

    def test_enabled_via_flag_and_endpoint(self, monkeypatch):
        from swiss_ip_mcp import telemetry

        monkeypatch.setenv("MCP_OTEL_ENABLED", "1")
        assert telemetry.telemetry_enabled() is True
        monkeypatch.delenv("MCP_OTEL_ENABLED", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
        assert telemetry.telemetry_enabled() is True

    def _capture(self):
        """Bind the telemetry tracer to an in-memory exporter; return it."""
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        from swiss_ip_mcp import telemetry

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        telemetry.tracer = provider.get_tracer("test")  # bypass global provider
        return exporter

    @pytest.mark.asyncio
    async def test_tool_call_emits_span_no_pii(self):
        from swiss_ip_mcp import telemetry

        original = telemetry.tracer
        exporter = self._capture()
        try:
            root = _make_root(SAMPLE_TM_XML)
            with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
                from swiss_ip_mcp.server import TrademarkSearchInput
                await swiss_ip_search_trademarks(
                    TrademarkSearchInput(query="SECRET-QUERY")
                )
        finally:
            telemetry.tracer = original

        spans = {s.name: s for s in exporter.get_finished_spans()}
        span = spans["mcp.tool/swiss_ip_search_trademarks"]
        assert span.attributes["mcp.tool.name"] == "swiss_ip_search_trademarks"
        assert span.attributes["mcp.tool.result.is_error"] is False
        # No query content leaks into span attributes (no PII).
        assert "SECRET-QUERY" not in str(dict(span.attributes))

    @pytest.mark.asyncio
    async def test_error_sets_is_error_attribute(self):
        import httpx

        from swiss_ip_mcp import telemetry

        original = telemetry.tracer
        exporter = self._capture()
        try:
            err = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock(status_code=500)
            )
            with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(side_effect=err)):
                from swiss_ip_mcp.server import TrademarkSearchInput
                await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        finally:
            telemetry.tracer = original

        span = {s.name: s for s in exporter.get_finished_spans()}[
            "mcp.tool/swiss_ip_search_trademarks"
        ]
        assert span.attributes["mcp.tool.result.is_error"] is True


# ---------------------------------------------------------------------------
# Unit tests – response_format rendering (SDK-003)
# ---------------------------------------------------------------------------

class TestResponseFormat:
    def test_render_json_is_parseable(self):
        from swiss_ip_mcp.server import ResponseFormat, _render

        out = _render({"count": 1, "results": [{"a": "b"}]}, ResponseFormat.JSON)
        assert json.loads(out)["count"] == 1

    def test_render_markdown_has_headers_fields_and_source(self):
        from swiss_ip_mcp.server import DATA_SOURCE, ResponseFormat, _render

        payload = {
            "source": DATA_SOURCE,
            "total": "42",
            "count": 1,
            "results": [{"MarkName": "ZÜRITEST", "Status": "Registered"}],
            "next_page_token": "tok123",
        }
        out = _render(payload, ResponseFormat.MARKDOWN)
        assert out.startswith("## Ergebnisse (1 von 42)")
        assert "**MarkName:** ZÜRITEST" in out
        assert "tok123" in out
        # source provenance footer, but the raw source dict is not dumped inline
        assert "_Quelle: Swissreg" in out
        assert "**source:**" not in out
        # not JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)

    def test_render_markdown_error(self):
        from swiss_ip_mcp.server import ResponseFormat, _render

        out = _render({"error": "kaputt"}, ResponseFormat.MARKDOWN)
        assert out == "**Fehler:** kaputt"

    @pytest.mark.asyncio
    async def test_tool_honours_markdown_format(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import ResponseFormat, TrademarkSearchInput
            params = TrademarkSearchInput(
                query="ZÜRITEST", response_format=ResponseFormat.MARKDOWN
            )
            out = await swiss_ip_search_trademarks(params)
            assert out.lstrip().startswith("## Ergebnisse")

    @pytest.mark.asyncio
    async def test_tool_default_format_is_json(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            params = TrademarkSearchInput(query="ZÜRITEST")  # no explicit format
            out = await swiss_ip_search_trademarks(params)
            assert json.loads(out)["count"] == 2  # still JSON by default


# ---------------------------------------------------------------------------
# Unit tests – pooled HTTP client & lifespan (SDK-001)
# ---------------------------------------------------------------------------

class TestPooledClient:
    def test_get_client_is_pooled(self):
        import swiss_ip_mcp.server as srv

        srv._client = None
        c1 = srv._get_client()
        c2 = srv._get_client()
        assert c1 is c2  # reused, not recreated per call

    def test_get_client_recreates_after_teardown(self):
        import swiss_ip_mcp.server as srv

        srv._client = None
        c1 = srv._get_client()
        srv._client = None  # simulate lifespan teardown
        c2 = srv._get_client()
        assert c1 is not c2

    @pytest.mark.asyncio
    async def test_lifespan_opens_and_closes_client(self):
        import swiss_ip_mcp.server as srv

        srv._client = None
        async with srv._lifespan(srv.mcp) as ctx:
            assert "client" in ctx
            assert ctx["client"] is srv._get_client()
            assert not ctx["client"].is_closed
        # after exit the module-level client is reset
        assert srv._client is None


# ---------------------------------------------------------------------------
# Unit tests – transport / network configuration (SCALE-001, SEC-016)
# ---------------------------------------------------------------------------

class TestTransportConfig:
    def test_default_transport_is_stdio(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        assert srv._resolve_transport() == "stdio"

    def test_sse_and_http_aliases(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_TRANSPORT", "sse")
        assert srv._resolve_transport() == "sse"
        for alias in ("http", "streamable-http", "streamable_http"):
            monkeypatch.setenv("MCP_TRANSPORT", alias)
            assert srv._resolve_transport() == "streamable-http"

    def test_unknown_transport_exits(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_TRANSPORT", "carrier-pigeon")
        with pytest.raises(SystemExit):
            srv._resolve_transport()

    def test_host_default_is_loopback(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.delenv("MCP_HOST", raising=False)
        assert srv._env_host() == "127.0.0.1"

    def test_port_prefers_paas_port(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("PORT", "9001")
        monkeypatch.setenv("MCP_PORT", "8002")
        assert srv._env_port() == 9001
        monkeypatch.delenv("PORT", raising=False)
        assert srv._env_port() == 8002

    def test_transport_security_off_without_allowlist(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)
        assert srv._transport_security() is None

    def test_transport_security_on_with_allowlist(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_ALLOWED_HOSTS", "swiss-ip.example.ch")
        sec = srv._transport_security()
        assert sec is not None
        assert sec.enable_dns_rebinding_protection is True
        assert "swiss-ip.example.ch" in sec.allowed_hosts


# ---------------------------------------------------------------------------
# Unit tests – HTTP serving wires CORS + binding warning (SDK-004, SEC-016)
# ---------------------------------------------------------------------------

class TestHttpServing:
    def test_run_http_configures_cors_and_binds_configured_host(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("PORT", "8123")
        monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://client.example")

        captured = {}

        def fake_uvicorn_run(app, host, port, log_level):
            captured["host"] = host
            captured["port"] = port
            captured["middlewares"] = [m.cls.__name__ for m in app.user_middleware]

        fake_uvicorn = MagicMock()
        fake_uvicorn.run = fake_uvicorn_run
        monkeypatch.setitem(__import__("sys").modules, "uvicorn", fake_uvicorn)

        srv._run_http("streamable-http")

        assert captured["host"] == "127.0.0.1"
        assert captured["port"] == 8123
        assert "CORSMiddleware" in captured["middlewares"]

    def test_run_http_warns_on_public_bind_outside_container(self, monkeypatch):
        import structlog

        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setattr(srv, "_in_container", lambda: False)
        monkeypatch.setitem(__import__("sys").modules, "uvicorn", MagicMock())

        with structlog.testing.capture_logs() as logs:
            srv._run_http("streamable-http")

        warnings = [e for e in logs if e["event"] == "bind_public_without_container"]
        assert warnings and warnings[0]["host"] == "0.0.0.0"


@pytest.mark.skipif(not LIVE, reason="IGE_USERNAME not set – skipping live tests")
class TestLiveApi:
    @pytest.mark.asyncio
    async def test_live_trademark_search(self):
        from swiss_ip_mcp.server import TrademarkSearchInput
        params = TrademarkSearchInput(query="Zürich*", page_size=3)
        result_str = await swiss_ip_search_trademarks(params)
        result = json.loads(result_str)
        assert "error" not in result
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_live_patent_search(self):
        from swiss_ip_mcp.server import PatentSearchInput
        params = PatentSearchInput(query="Roche*", page_size=3)
        result_str = await swiss_ip_search_patents(params)
        result = json.loads(result_str)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_live_spc_search(self):
        from swiss_ip_mcp.server import SpcSearchInput
        params = SpcSearchInput(query="Novartis*", page_size=3)
        result_str = await swiss_ip_search_spc(params)
        result = json.loads(result_str)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_live_quota(self):
        result_str = await swiss_ip_get_quota()
        result = json.loads(result_str)
        assert "error" not in result
