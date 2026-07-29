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
        assert result.count == 2
        assert result.total == "42"
        assert result.next_page_token is None

    def test_parse_result_page_empty(self):
        root = _make_root(SAMPLE_EMPTY_XML)
        result = _parse_result_page(root)
        assert result.count == 0
        assert result.total == "0"


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
            result = (await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))).model_dump(exclude_none=True)
        assert result["source"]["name"].startswith("Swissreg")
        assert "license" in result["source"]
        assert isinstance(result["results"], list)
        assert result["count"] == len(result["results"])

    @pytest.mark.asyncio
    async def test_match_type_exact_on_hits(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            result = (await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))).model_dump(exclude_none=True)
        assert result["match_type"] == "exact"
        assert "suggestion" not in result

    @pytest.mark.asyncio
    async def test_match_type_none_with_suggestion_on_empty(self):
        # ARCH-003: empty search yields match_type=none + actionable suggestion.
        root = _make_root(SAMPLE_EMPTY_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentSearchInput
            result = (await swiss_ip_search_patents(PatentSearchInput(query="zzzznomatch"))).model_dump(exclude_none=True)
        assert result["match_type"] == "none"
        assert result["count"] == 0
        assert "Wildcard" in result["suggestion"]

    @pytest.mark.asyncio
    async def test_quota_has_source(self):
        root = _make_root(SAMPLE_QUOTA_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result = (await swiss_ip_get_quota()).model_dump(exclude_none=True)
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
            result = result_str.model_dump(exclude_none=True)
            assert result["count"] == 2
            assert result["total"] == "42"

    @pytest.mark.asyncio
    async def test_search_trademarks_api_error_raises(self):
        # OBS-001: execution errors raise → MCPServer returns isError=true.
        import httpx
        from mcp.server.mcpserver.exceptions import ToolError
        err = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock(status_code=401)
        )
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(side_effect=err)):
            from swiss_ip_mcp.server import TrademarkSearchInput
            params = TrademarkSearchInput(query="test")
            with pytest.raises(ToolError) as ei:
                await swiss_ip_search_trademarks(params)
            assert "401" in str(ei.value)

    @pytest.mark.asyncio
    async def test_get_trademark_not_found(self):
        root = _make_root(SAMPLE_EMPTY_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkNumberInput
            params = TrademarkNumberInput(trademark_number="P-000000")
            result_str = await swiss_ip_get_trademark(params)
            result = result_str.model_dump(exclude_none=True)
            # not-found is a valid empty result (isError=false), not an error
            assert result["match_type"] == "none"
            assert result["count"] == 0
            assert "nicht gefunden" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_search_by_owner(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkOwnerSearchInput
            params = TrademarkOwnerSearchInput(owner_name="Mustermann AG")
            result_str = await swiss_ip_search_trademarks_by_owner(params)
            result = result_str.model_dump(exclude_none=True)
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_search_by_class(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import TrademarkClassInput
            params = TrademarkClassInput(nice_class=41)
            result_str = await swiss_ip_search_trademarks_by_class(params)
            result = result_str.model_dump(exclude_none=True)
            assert result["nice_class_searched"] == 41


class TestPatentTools:
    @pytest.mark.asyncio
    async def test_search_patents(self):
        root = _make_root(SAMPLE_TM_XML)  # structure same
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentSearchInput
            params = PatentSearchInput(query="solar*")
            result_str = await swiss_ip_search_patents(params)
            result = result_str.model_dump(exclude_none=True)
            assert "count" in result

    @pytest.mark.asyncio
    async def test_get_patent_not_found(self):
        root = _make_root(SAMPLE_EMPTY_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentNumberInput
            params = PatentNumberInput(patent_number="CH000000")
            result_str = await swiss_ip_get_patent(params)
            result = result_str.model_dump(exclude_none=True)
            assert result["match_type"] == "none"
            assert result["count"] == 0
            assert "nicht gefunden" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_search_by_applicant(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentApplicantInput
            params = PatentApplicantInput(applicant_name="ABB*")
            result_str = await swiss_ip_search_patents_by_applicant(params)
            result = result_str.model_dump(exclude_none=True)
            assert "count" in result

    @pytest.mark.asyncio
    async def test_search_patent_publications(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import PatentSearchInput
            params = PatentSearchInput(query="battery*")
            result_str = await swiss_ip_search_patent_publications(params)
            result = result_str.model_dump(exclude_none=True)
            assert "count" in result


class TestSpcTools:
    @pytest.mark.asyncio
    async def test_search_spc(self):
        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            from swiss_ip_mcp.server import SpcSearchInput
            params = SpcSearchInput(query="Novartis")
            result_str = await swiss_ip_search_spc(params)
            result = result_str.model_dump(exclude_none=True)
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
            result = result_str.model_dump(exclude_none=True)
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
            result = result_str.model_dump(exclude_none=True)
            assert result["date_range"]["from"] == "2025-06-01"

    @pytest.mark.asyncio
    async def test_get_quota(self):
        root = _make_root(SAMPLE_QUOTA_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result_str = await swiss_ip_get_quota()
            result = result_str.model_dump(exclude_none=True)
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

        from mcp.server.mcpserver.exceptions import ToolError
        with structlog.testing.capture_logs() as logs:
            with patch(
                "swiss_ip_mcp.server._call_api",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                from swiss_ip_mcp.server import TrademarkSearchInput
                with pytest.raises(ToolError):
                    await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        errors = [e for e in logs if e["event"] == "unexpected_error"]
        assert errors and errors[0]["log_level"] == "error"
        # no raw exception value leaks into the structured event
        assert "boom" not in str(errors[0])


# ---------------------------------------------------------------------------
# Unit tests – MCP error semantics & primitives (OBS-001, ARCH-008)
# ---------------------------------------------------------------------------

class TestMcpErrorSemantics:
    """OBS-001 end-to-end via the public in-process client.

    These used to reach into ``mcp._mcp_server.request_handlers``. mcp 2.x
    dispatches through handlers passed at construction and the lowlevel
    ``Server`` exposes no ``request_handlers`` mapping, so the same behaviour
    is now asserted over a real client session — which is what actually
    matters, and does not depend on SDK internals.
    """

    @pytest.mark.asyncio
    async def test_served_execution_error_sets_is_error(self):
        import httpx
        from mcp.client import Client

        from swiss_ip_mcp.server import mcp

        err = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(status_code=500)
        )
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(side_effect=err)):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "swiss_ip_search_trademarks", {"params": {"query": "x"}}
                )
        assert result.is_error is True
        # masked: no stack trace / upstream body in the surfaced text
        text = result.content[0].text
        assert "Server-Log" in text
        assert "Traceback" not in text

    @pytest.mark.asyncio
    async def test_served_success_is_not_error(self):
        from mcp.client import Client

        from swiss_ip_mcp.server import mcp

        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "swiss_ip_search_trademarks", {"params": {"query": "x"}}
                )
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_protocol_error_on_invalid_args(self):
        """Schema-invalid arguments are rejected before the tool body runs."""
        from mcp.client import Client

        from swiss_ip_mcp.server import mcp

        async with Client(mcp) as client:
            result = await client.call_tool("swiss_ip_search_trademarks", {})
        assert result.is_error is True


class TestMcpPrimitives:
    @pytest.mark.asyncio
    async def test_resources_registered(self):
        from swiss_ip_mcp.server import mcp

        uris = {str(r.uri) for r in await mcp.list_resources()}
        assert {"swissip://about", "swissip://domains"} <= uris

    @pytest.mark.asyncio
    async def test_about_resource_carries_provenance(self):
        import json as _json

        from swiss_ip_mcp.server import mcp

        content = await mcp.read_resource("swissip://about")
        payload = _json.loads(list(content)[0].content)
        assert payload["source"]["name"].startswith("Swissreg")
        assert "trademarks" in payload["covered_domains"]

    @pytest.mark.asyncio
    async def test_prompts_registered(self):
        from swiss_ip_mcp.server import mcp

        names = {p.name for p in await mcp.list_prompts()}
        assert {
            "trademark_availability",
            "competitor_ip_report",
            "recent_ip_filings_report",
        } <= names

    @pytest.mark.asyncio
    async def test_prompt_renders_with_argument(self):
        from swiss_ip_mcp.server import mcp

        result = await mcp.get_prompt("trademark_availability", {"name": "ACME"})
        text = result.messages[0].content.text
        assert "ACME" in text


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
            from mcp.server.mcpserver.exceptions import ToolError
            with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(side_effect=err)):
                from swiss_ip_mcp.server import TrademarkSearchInput
                with pytest.raises(ToolError):
                    await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        finally:
            telemetry.tracer = original

        span = {s.name: s for s in exporter.get_finished_spans()}[
            "mcp.tool/swiss_ip_search_trademarks"
        ]
        assert span.attributes["mcp.tool.result.is_error"] is True


# ---------------------------------------------------------------------------
# Unit tests – typed response models (SDK-002)
# ---------------------------------------------------------------------------

class TestTypedReturns:
    @pytest.mark.asyncio
    async def test_search_returns_typed_envelope(self):
        from swiss_ip_mcp.server import SearchEnvelope, TrademarkSearchInput

        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result = await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        assert isinstance(result, SearchEnvelope)
        assert result.count == 2
        assert result.match_type == "exact"
        assert result.source.name.startswith("Swissreg")

    @pytest.mark.asyncio
    async def test_quota_returns_typed_envelope(self):
        from swiss_ip_mcp.server import QuotaEnvelope

        root = _make_root(SAMPLE_QUOTA_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result = await swiss_ip_get_quota()
        assert isinstance(result, QuotaEnvelope)
        assert result.source.provider.startswith("Swiss Federal Institute")

    @pytest.mark.asyncio
    async def test_tools_expose_output_schema(self):
        from swiss_ip_mcp.server import mcp

        tools = {t.name: t for t in await mcp.list_tools()}
        assert tools["swiss_ip_search_trademarks"].output_schema is not None
        assert tools["swiss_ip_get_quota"].output_schema is not None

    @pytest.mark.asyncio
    async def test_exclude_none_drops_optional_fields(self):
        from swiss_ip_mcp.server import TrademarkSearchInput

        root = _make_root(SAMPLE_TM_XML)
        with patch("swiss_ip_mcp.server._call_api", new=AsyncMock(return_value=root)):
            result = await swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        dumped = result.model_dump(exclude_none=True)
        assert "suggestion" not in dumped  # only present on empty results
        assert "message" not in dumped


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


# ---------------------------------------------------------------------------
# Unit tests – deployment: health endpoint, stateless flag, infra artifacts
# (SEC-007 / SCALE-002 / SCALE-003 / SCALE-004 / SCALE-006)
# ---------------------------------------------------------------------------

import pathlib  # noqa: E402

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestDeployment:
    @pytest.mark.asyncio
    async def test_health_route_present(self):
        import swiss_ip_mcp.server as srv

        app = srv._build_http_app("streamable-http")
        paths = {getattr(r, "path", None) for r in app.router.routes}
        assert "/health" in paths

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_ok(self):
        import swiss_ip_mcp.server as srv

        resp = await srv._health(None)
        assert resp.status_code == 200
        assert b'"status":"ok"' in resp.body

    def test_stateless_env_flag(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_STATELESS_HTTP", "1")
        assert srv._env_bool("MCP_STATELESS_HTTP") is True
        monkeypatch.delenv("MCP_STATELESS_HTTP", raising=False)
        assert srv._env_bool("MCP_STATELESS_HTTP") is False

    def test_dockerfile_is_hardened(self):
        text = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "USER 10001:10001" in text          # non-root UID >= 10000 (SEC-007)
        assert "HEALTHCHECK" in text                # SCALE-004
        assert text.count("FROM ") >= 2             # multi-stage
        assert "-slim" in text

    def test_compose_has_resource_limits(self):
        text = (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        for key in ("mem_limit:", "cpus:", "nofile:", "no-new-privileges", "read_only:"):
            assert key in text, key

    def test_k8s_security_context(self):
        text = (_REPO_ROOT / "deploy/kubernetes/deployment.yaml").read_text(encoding="utf-8")
        for key in (
            "runAsNonRoot: true",
            "runAsUser: 10001",
            "allowPrivilegeEscalation: false",
            "readOnlyRootFilesystem: true",
            'drop: ["ALL"]',
            "RuntimeDefault",
            "path: /health",
        ):
            assert key in text, key

    def test_haproxy_sticky_on_session_header(self):
        text = (_REPO_ROOT / "deploy/haproxy.cfg").read_text(encoding="utf-8")
        assert "stick on req.hdr(Mcp-Session-Id)" in text
        assert "stick-table" in text


# ---------------------------------------------------------------------------
# Unit tests – egress allow-list & tool manifest (SEC-021, SEC-022)
# ---------------------------------------------------------------------------

class TestCredentialsSecret:
    def test_credentials_are_secretstr_and_masked(self, monkeypatch):
        # ARCH-005: credentials held as SecretStr, never leaked via repr.
        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("IGE_USERNAME", "alice")
        monkeypatch.setenv("IGE_PASSWORD", "s3cr3t-pw")
        creds = srv._load_credentials()
        assert creds.username.get_secret_value() == "alice"
        assert creds.password.get_secret_value() == "s3cr3t-pw"
        assert "s3cr3t-pw" not in repr(creds)
        assert "s3cr3t-pw" not in str(creds)

    def test_missing_credentials_raise(self, monkeypatch):
        import swiss_ip_mcp.server as srv

        monkeypatch.delenv("IGE_USERNAME", raising=False)
        monkeypatch.delenv("IGE_PASSWORD", raising=False)
        with pytest.raises(ValueError, match="Zugangsdaten fehlen"):
            srv._load_credentials()


class TestProgressReporting:
    @pytest.mark.asyncio
    async def test_call_api_reports_progress_with_ctx(self, monkeypatch):
        # SDK-003: when a ctx is passed, progress is reported around the call.
        import httpx
        import respx

        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("IGE_USERNAME", "u")
        monkeypatch.setenv("IGE_PASSWORD", "p")
        srv._token_cache["token"] = None
        srv._token_cache["expires_at"] = 0.0
        srv._client = None
        ctx = AsyncMock()

        with respx.mock as mock:
            mock.post(srv.IDP_TOKEN_URL).mock(
                return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 300})
            )
            mock.post(srv.API_ENDPOINT).mock(
                return_value=httpx.Response(200, content=SAMPLE_TM_XML.encode("utf-8"))
            )
            await srv._call_api("<x/>", ctx)

        assert ctx.report_progress.await_count == 2
        srv._token_cache["token"] = None


class TestEgressAllowList:
    def test_allows_fixed_ige_hosts(self):
        import swiss_ip_mcp.server as srv

        srv._assert_host_allowed(srv.IDP_TOKEN_URL)   # no raise
        srv._assert_host_allowed(srv.API_ENDPOINT)    # no raise

    def test_blocks_other_hosts(self):
        import swiss_ip_mcp.server as srv

        for bad in (
            "http://169.254.169.254/latest/meta-data/",
            "https://evil.example/x",
            "https://idp.ipi.ch.evil.example/x",
        ):
            with pytest.raises(ValueError, match="nicht erlaubt"):
                srv._assert_host_allowed(bad)


class TestToolManifest:
    @pytest.mark.asyncio
    async def test_pinned_manifest_matches(self):
        # SEC-022: changing a tool definition must be intentional — regenerate
        # tool_manifest.json via scripts/update_tool_manifest.py and review.
        import json as _json

        from swiss_ip_mcp.integrity import compute_manifest
        from swiss_ip_mcp.server import mcp

        current = await compute_manifest(mcp)
        pinned = _json.loads(
            (_REPO_ROOT / "tool_manifest.json").read_text(encoding="utf-8")
        )
        assert current == pinned

    @pytest.mark.asyncio
    async def test_all_tools_namespaced(self):
        from swiss_ip_mcp.integrity import TOOL_NAMESPACE_PREFIX
        from swiss_ip_mcp.server import mcp

        for t in await mcp.list_tools():
            assert t.name.startswith(TOOL_NAMESPACE_PREFIX)


# ---------------------------------------------------------------------------
# Unit tests – real HTTP path via respx (OPS-001)
# ---------------------------------------------------------------------------

class TestRespxHttpPath:
    @pytest.mark.asyncio
    async def test_search_through_real_http_layer(self, monkeypatch):
        import httpx
        import respx

        import swiss_ip_mcp.server as srv

        # Exercise the real _get_token + _call_api + egress guard + parser,
        # mocking only the HTTP transport (not _call_api).
        monkeypatch.setenv("IGE_USERNAME", "u")
        monkeypatch.setenv("IGE_PASSWORD", "p")
        srv._token_cache["token"] = None
        srv._token_cache["expires_at"] = 0.0
        srv._client = None

        with respx.mock(assert_all_called=True) as mock:
            mock.post(srv.IDP_TOKEN_URL).mock(
                return_value=httpx.Response(
                    200, json={"access_token": "tok", "expires_in": 300}
                )
            )
            mock.post(srv.API_ENDPOINT).mock(
                return_value=httpx.Response(200, content=SAMPLE_TM_XML.encode("utf-8"))
            )
            from swiss_ip_mcp.server import TrademarkSearchInput
            result = (await srv.swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))).model_dump(exclude_none=True)

        assert result["count"] == 2
        assert result["source"]["name"].startswith("Swissreg")
        srv._token_cache["token"] = None  # avoid leaking the fake token

    @pytest.mark.asyncio
    async def test_http_401_surfaces_as_tool_error(self, monkeypatch):
        import httpx
        import respx
        from mcp.server.mcpserver.exceptions import ToolError

        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("IGE_USERNAME", "u")
        monkeypatch.setenv("IGE_PASSWORD", "p")
        srv._token_cache["token"] = None
        srv._token_cache["expires_at"] = 0.0
        srv._client = None

        with respx.mock as mock:
            mock.post(srv.IDP_TOKEN_URL).mock(
                return_value=httpx.Response(
                    200, json={"access_token": "tok", "expires_in": 300}
                )
            )
            mock.post(srv.API_ENDPOINT).mock(return_value=httpx.Response(401))
            from swiss_ip_mcp.server import TrademarkSearchInput
            with pytest.raises(ToolError) as ei:
                await srv.swiss_ip_search_trademarks(TrademarkSearchInput(query="x"))
        assert "401" in str(ei.value)
        srv._token_cache["token"] = None


@pytest.mark.live
@pytest.mark.skipif(not LIVE, reason="IGE_USERNAME not set – skipping live tests")
class TestLiveApi:
    @pytest.mark.asyncio
    async def test_live_trademark_search(self):
        from swiss_ip_mcp.server import TrademarkSearchInput
        params = TrademarkSearchInput(query="Zürich*", page_size=3)
        result_str = await swiss_ip_search_trademarks(params)
        result = result_str.model_dump(exclude_none=True)
        assert "error" not in result
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_live_patent_search(self):
        from swiss_ip_mcp.server import PatentSearchInput
        params = PatentSearchInput(query="Roche*", page_size=3)
        result_str = await swiss_ip_search_patents(params)
        result = result_str.model_dump(exclude_none=True)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_live_spc_search(self):
        from swiss_ip_mcp.server import SpcSearchInput
        params = SpcSearchInput(query="Novartis*", page_size=3)
        result_str = await swiss_ip_search_spc(params)
        result = result_str.model_dump(exclude_none=True)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_live_quota(self):
        result_str = await swiss_ip_get_quota()
        result = result_str.model_dump(exclude_none=True)
        assert "error" not in result
