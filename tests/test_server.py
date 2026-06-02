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

    def test_generic(self):
        msg = _handle_error(RuntimeError("boom"))
        assert "boom" in msg


# ---------------------------------------------------------------------------
# Unit tests – tools (mocked API)
# ---------------------------------------------------------------------------

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
# Integration / smoke tests (live, skipped without credentials)
# ---------------------------------------------------------------------------

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

    def test_run_http_warns_on_public_bind_outside_container(self, monkeypatch, caplog):
        import logging

        import swiss_ip_mcp.server as srv

        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setattr(srv, "_in_container", lambda: False)
        monkeypatch.setitem(__import__("sys").modules, "uvicorn", MagicMock())

        with caplog.at_level(logging.WARNING):
            srv._run_http("streamable-http")

        assert any("0.0.0.0" in r.message for r in caplog.records)


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
