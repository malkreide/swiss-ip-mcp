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
        assert "Configuration error" in msg
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
            assert "not found" in result["error"].lower()

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
