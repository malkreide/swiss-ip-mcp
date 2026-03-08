"""
Swiss IP MCP Server – Model Context Protocol server for Swiss intellectual
property data via the IGE/IPI Swissreg Datadelivery API.

Covers: Trademarks (Marken), Patents, Patent Publications,
        SPC/ESZ (Supplementary Protection Certificates).

Authentication: OAuth2 via IDP (IGE_USERNAME / IGE_PASSWORD env vars).
Transport:      stdio (Claude Desktop) and Streamable HTTP / SSE (Render.com).
"""

from __future__ import annotations

import json
import logging
import os
import time
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("swiss_ip_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IDP_TOKEN_URL = (
    "https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token"
)
API_ENDPOINT = "https://www.swissreg.ch/public/api/v1"
CLIENT_ID = "datadelivery-api-client"

NS_CORE = "urn:ige:schema:xsd:datadeliverycore-1.0.0"
NS_COMMON = "urn:ige:schema:xsd:datadeliverycommon-1.0.0"
NS_TM = "urn:ige:schema:xsd:datadeliverytrademark-1.0.0"
NS_PAT = "urn:ige:schema:xsd:datadeliverypatent-1.0.0"
NS_SPC = "urn:ige:schema:xsd:datadeliveryspc-1.0.0"

DEFAULT_PAGE_SIZE = 10
REQUEST_TIMEOUT = 60.0

# ---------------------------------------------------------------------------
# Token cache (module-level singleton)
# ---------------------------------------------------------------------------
_token_cache: dict = {"token": None, "expires_at": 0.0}


async def _get_token(client: httpx.AsyncClient) -> str:
    """Obtain or refresh a Bearer token from the IGE IDP."""
    username = os.getenv("IGE_USERNAME", "")
    password = os.getenv("IGE_PASSWORD", "")

    if not username or not password:
        raise ValueError(
            "IGE credentials missing. "
            "Set IGE_USERNAME and IGE_PASSWORD environment variables. "
            "After signing the IGE usage terms (https://www.ige.ch/de/"
            "uebersicht-dienstleistungen/digitales-angebot/ip-daten/"
            "datenabgabe-api), you will receive login credentials."
        )

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["token"]  # type: ignore[return-value]

    resp = await client.post(
        IDP_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 300))
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expires_in
    logger.info("IGE token refreshed, valid for %ds", expires_in)
    return token


async def _call_api(xml_body: str) -> ET.Element:
    """Post an XML request to the Swissreg API and return the root element."""
    async with httpx.AsyncClient() as client:
        token = await _get_token(client)
        resp = await client.post(
            API_ENDPOINT,
            content=xml_body.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/xml",
                "Accept": "application/xml",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return ET.fromstring(resp.content)


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """XML-escape a string for safe inclusion in the request body."""
    return saxutils.escape(str(text))


def _build_trademark_search(
    query_xml: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_token: Optional[str] = None,
    sort: str = "LastUpdateSort",
    sort_dir: str = "Descending",
) -> str:
    page_el = f'<Page size="{page_size}"/>'
    if page_token:
        page_el = f'<Page size="{page_size}" token="{_esc(page_token)}"/>'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ApiRequest xmlns="{NS_CORE}" xmlns:tm="{NS_TM}">
  <Action type="TrademarkSearch">
    <tm:TrademarkSearchRequest xmlns="{NS_COMMON}">
      <Representation details="Maximal"/>
      {page_el}
      <Query>{query_xml}</Query>
      <Sort><{sort}>{sort_dir}</{sort}></Sort>
    </tm:TrademarkSearchRequest>
  </Action>
</ApiRequest>"""


def _build_patent_search(
    query_xml: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_token: Optional[str] = None,
    sort: str = "LastUpdateSort",
    sort_dir: str = "Descending",
) -> str:
    page_el = f'<Page size="{page_size}"/>'
    if page_token:
        page_el = f'<Page size="{page_size}" token="{_esc(page_token)}"/>'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ApiRequest xmlns="{NS_CORE}" xmlns:pat="{NS_PAT}">
  <Action type="PatentSearch">
    <pat:PatentSearchRequest xmlns="{NS_COMMON}">
      <Representation details="Maximal"/>
      {page_el}
      <Query>{query_xml}</Query>
      <Sort><{sort}>{sort_dir}</{sort}></Sort>
    </pat:PatentSearchRequest>
  </Action>
</ApiRequest>"""


def _build_patent_pub_search(
    query_xml: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_token: Optional[str] = None,
) -> str:
    page_el = f'<Page size="{page_size}"/>'
    if page_token:
        page_el = f'<Page size="{page_size}" token="{_esc(page_token)}"/>'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ApiRequest xmlns="{NS_CORE}" xmlns:pat="{NS_PAT}">
  <Action type="PatentPublicationSearch">
    <pat:PatentPublicationSearchRequest xmlns="{NS_COMMON}">
      <Representation details="Maximal"/>
      {page_el}
      <Query>{query_xml}</Query>
      <Sort><LastUpdateSort>Descending</LastUpdateSort></Sort>
    </pat:PatentPublicationSearchRequest>
  </Action>
</ApiRequest>"""


def _build_spc_search(
    query_xml: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_token: Optional[str] = None,
) -> str:
    page_el = f'<Page size="{page_size}"/>'
    if page_token:
        page_el = f'<Page size="{page_size}" token="{_esc(page_token)}"/>'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ApiRequest xmlns="{NS_CORE}" xmlns:spc="{NS_SPC}">
  <Action type="SPCSearch">
    <spc:SPCSearchRequest xmlns="{NS_COMMON}">
      <Representation details="Maximal"/>
      {page_el}
      <Query>{query_xml}</Query>
      <Sort><LastUpdateSort>Descending</LastUpdateSort></Sort>
    </spc:SPCSearchRequest>
  </Action>
</ApiRequest>"""


def _quota_request() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ApiRequest xmlns="{NS_CORE}">
  <Action type="UserQuota">
    <UserQuotaRequest xmlns="urn:ige:schema:xsd:datadeliveryquota-1.0.0"/>
  </Action>
</ApiRequest>"""


# ---------------------------------------------------------------------------
# Response parsers (generic namespace-aware helpers)
# ---------------------------------------------------------------------------

def _find_all(root: ET.Element, local: str) -> list[ET.Element]:
    """Find all elements with a given local name, ignoring namespace."""
    return [el for el in root.iter() if _local(el.tag) == local]


def _local(tag: str) -> str:
    """Strip namespace from a tag, e.g. {ns}LocalName → LocalName."""
    return tag.split("}")[-1] if "}" in tag else tag


def _text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _el_to_dict(el: ET.Element, depth: int = 0) -> dict | str:
    """Recursively convert an XML element to a plain dict."""
    if depth > 8:
        return _text(el)
    children = list(el)
    if not children:
        return _text(el)
    result: dict = {}
    for child in children:
        key = _local(child.tag)
        val = _el_to_dict(child, depth + 1)
        if key in result:
            existing = result[key]
            if not isinstance(existing, list):
                result[key] = [existing]
            result[key].append(val)  # type: ignore[union-attr]
        else:
            result[key] = val
    return result


def _parse_result_page(root: ET.Element) -> dict:
    """Extract items and pagination info from an API response."""
    items = []
    for item_el in _find_all(root, "Item"):
        items.append(_el_to_dict(item_el))

    # Continuation / next page token
    next_token = None
    for cont in _find_all(root, "Continuation"):
        # The continuation element typically holds child actions; extract token
        tok_el = cont.find(".//{*}Page")
        if tok_el is not None:
            next_token = tok_el.get("token")
        break

    # Meta element with total count
    total = None
    for meta in _find_all(root, "Meta"):
        total_el = meta.find(".//{*}TotalCount")
        if total_el is not None:
            total = _text(total_el)
        break

    return {
        "total": total,
        "count": len(items),
        "items": items,
        "next_page_token": next_token,
    }


def _handle_error(e: Exception) -> str:
    """Format API errors into actionable messages."""
    if isinstance(e, ValueError):
        return f"Configuration error: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return (
                "Authentication failed (401). "
                "Check IGE_USERNAME and IGE_PASSWORD. "
                "Credentials are provided after signing the IGE usage terms."
            )
        if status == 403:
            return (
                "Access denied (403). Your account may not have API access. "
                "Ensure the usage terms are signed and credentials are valid."
            )
        if status == 429:
            return (
                "Rate limit / quota exceeded (429). "
                "Use swiss_ip_get_quota to check remaining quota."
            )
        return f"API error {status}: {e.response.text[:500]}"
    if isinstance(e, httpx.TimeoutException):
        return "Request timed out. The Swissreg API can be slow; try again."
    return f"Unexpected error ({type(e).__name__}): {e}"


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "swiss_ip_mcp",
    instructions=(
        "Swiss IP MCP Server provides access to Swiss intellectual property "
        "data via the IGE/IPI Swissreg Datadelivery API. Covers trademarks "
        "(Marken), patents (Patente), patent publications, and supplementary "
        "protection certificates (SPC/ESZ). Requires IGE_USERNAME and "
        "IGE_PASSWORD environment variables (free after signing IGE usage terms)."
    ),
)

# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------

class TrademarkSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=(
            "Free-text search term. Wildcards (*) supported. "
            "Examples: 'Zürich*', 'apple', 'Bank*'. "
            "Special chars must be meaningful (not just *)."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(
        default=10,
        description="Number of results per page (1–50).",
        ge=1,
        le=50,
    )
    page_token: Optional[str] = Field(
        default=None,
        description="Pagination token from a previous response's next_page_token.",
    )
    sort_descending: bool = Field(
        default=True,
        description="Sort by last update descending (newest first) if True.",
    )


class TrademarkOwnerSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    owner_name: str = Field(
        ...,
        description=(
            "Name of the trademark owner / applicant. "
            "Wildcards (*) supported. Example: 'Nestlé*', 'Google*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)


class TrademarkNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trademark_number: str = Field(
        ...,
        description=(
            "Swiss trademark application or registration number. "
            "Examples: 'P-756123', '756123'."
        ),
        min_length=1,
        max_length=50,
    )


class TrademarkClassInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nice_class: int = Field(
        ...,
        description=(
            "Nice Classification class number (1–45). "
            "Example: 9 = computers/software, 35 = advertising/business, "
            "41 = education/training."
        ),
        ge=1,
        le=45,
    )
    query: Optional[str] = Field(
        default=None,
        description="Optional additional text filter within the class.",
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)


class PatentSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=(
            "Free-text search for Swiss patents. Wildcards (*) supported. "
            "Examples: 'solar energy*', 'Novartis', 'machine learning'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    sort_descending: bool = Field(default=True)


class PatentNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    patent_number: str = Field(
        ...,
        description=(
            "Swiss patent number. Examples: 'CH123456', '123456'."
        ),
        min_length=1,
        max_length=50,
    )


class PatentApplicantInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    applicant_name: str = Field(
        ...,
        description=(
            "Name of the patent applicant or inventor. "
            "Wildcards (*) supported. Examples: 'ABB*', 'ETH Zürich*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)


class DateRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ip_type: str = Field(
        ...,
        description=(
            "Type of IP right to search: 'trademark', 'patent', "
            "'patent_publication', or 'spc'."
        ),
        pattern="^(trademark|patent|patent_publication|spc)$",
    )
    date_from: str = Field(
        ...,
        description="Start date in ISO format YYYY-MM-DD (inclusive).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_to: str = Field(
        ...,
        description="End date in ISO format YYYY-MM-DD (exclusive).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)


class SpcSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=(
            "Search term for Supplementary Protection Certificates (SPC / ESZ). "
            "Wildcards (*) supported. Examples: 'Novartis', 'ibuprofen*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Tools – Trademarks
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_trademarks",
    annotations={
        "title": "Search Swiss Trademarks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_trademarks(params: TrademarkSearchInput) -> str:
    """Search the Swiss trademark register (Markenregister) by free text.

    Use this to find trademarks by name, brand term, or keyword. Supports
    wildcard (*) searches. Returns registration status, owner, filing dates,
    Nice classes, and more.

    Args:
        params (TrademarkSearchInput):
            - query (str): Search term, e.g. 'Zürich*', 'apple', 'Bank*'
            - page_size (int): Results per page (1–50, default 10)
            - page_token (str): Pagination token for subsequent pages
            - sort_descending (bool): Sort newest first (default True)

    Returns:
        str: JSON with keys:
            - total (str|None): Total matching records
            - count (int): Items in this page
            - items (list[dict]): Trademark records
            - next_page_token (str|None): Token for next page
    """
    sort_dir = "Descending" if params.sort_descending else "Ascending"
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_trademark_search(
        query_xml, params.page_size, params.page_token, sort_dir=sort_dir
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_search_trademarks_by_owner",
    annotations={
        "title": "Search Swiss Trademarks by Owner",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_trademarks_by_owner(
    params: TrademarkOwnerSearchInput,
) -> str:
    """Search Swiss trademarks filtered by owner / applicant name.

    Useful for IP monitoring: find all trademarks held by a company or
    individual. Supports wildcards (*).

    Args:
        params (TrademarkOwnerSearchInput):
            - owner_name (str): Owner name, e.g. 'Nestlé*', 'Stadt Zürich*'
            - page_size (int): Results per page (1–50)
            - page_token (str): Pagination token

    Returns:
        str: JSON with total, count, items, next_page_token
    """
    # Trademark owner fields are searched via Any (the API's full-text field
    # covers holder/applicant names in the index).
    query_xml = f"<Any>{_esc(params.owner_name)}</Any>"
    xml_body = _build_trademark_search(
        query_xml, params.page_size, params.page_token
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_get_trademark",
    annotations={
        "title": "Get Swiss Trademark by Number",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_get_trademark(params: TrademarkNumberInput) -> str:
    """Retrieve a specific Swiss trademark by its application/registration number.

    Returns detailed record including status, goods/services classes,
    opposition periods, and registration history.

    Args:
        params (TrademarkNumberInput):
            - trademark_number (str): Swiss trademark number, e.g. 'P-756123'

    Returns:
        str: JSON with total, count, items (single item), next_page_token
    """
    query_xml = f"<Id>{_esc(params.trademark_number)}</Id>"
    xml_body = _build_trademark_search(query_xml, page_size=1)
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        if result["count"] == 0:
            return json.dumps({
                "error": f"Trademark '{params.trademark_number}' not found. "
                         "Check the number format (e.g. 'P-756123')."
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_search_trademarks_by_class",
    annotations={
        "title": "Search Swiss Trademarks by Nice Class",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_trademarks_by_class(
    params: TrademarkClassInput,
) -> str:
    """Search Swiss trademarks by Nice Classification class number.

    Useful for competitive analysis within an industry sector.
    Key classes: 9=software/electronics, 35=advertising/business services,
    36=finance/insurance, 41=education/training, 42=technology services.

    Args:
        params (TrademarkClassInput):
            - nice_class (int): Nice class 1–45
            - query (str): Optional additional text filter
            - page_size (int): Results per page
            - page_token (str): Pagination token

    Returns:
        str: JSON with total, count, items, next_page_token
    """
    # Combine class filter with optional text query
    class_query = f"<Any>Klasse {params.nice_class}</Any>"
    if params.query:
        query_xml = (
            f"<And>{class_query}"
            f"<Any>{_esc(params.query)}</Any></And>"
        )
    else:
        query_xml = class_query

    xml_body = _build_trademark_search(
        query_xml, params.page_size, params.page_token
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        result["nice_class_searched"] = params.nice_class
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


# ---------------------------------------------------------------------------
# Tools – Patents
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_patents",
    annotations={
        "title": "Search Swiss Patents",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_patents(params: PatentSearchInput) -> str:
    """Search the Swiss patent register (Patentregister) by free text.

    Returns CH patent records including title, applicant, IPC classification,
    filing/grant dates, and legal status.

    Args:
        params (PatentSearchInput):
            - query (str): Search term, e.g. 'solar energy*', 'Novartis'
            - page_size (int): Results per page (1–50)
            - page_token (str): Pagination token
            - sort_descending (bool): Sort newest first

    Returns:
        str: JSON with total, count, items, next_page_token
    """
    sort_dir = "Descending" if params.sort_descending else "Ascending"
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_patent_search(
        query_xml, params.page_size, params.page_token, sort_dir=sort_dir
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_get_patent",
    annotations={
        "title": "Get Swiss Patent by Number",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_get_patent(params: PatentNumberInput) -> str:
    """Retrieve a specific Swiss patent by its number.

    Returns full record including claims summary, IPC codes, applicant,
    inventor, filing and grant dates, and current status.

    Args:
        params (PatentNumberInput):
            - patent_number (str): Swiss patent number, e.g. 'CH123456'

    Returns:
        str: JSON with total, count, items (single item), next_page_token
    """
    query_xml = f"<Id>{_esc(params.patent_number)}</Id>"
    xml_body = _build_patent_search(query_xml, page_size=1)
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        if result["count"] == 0:
            return json.dumps({
                "error": (
                    f"Patent '{params.patent_number}' not found. "
                    "Check the format (e.g. 'CH700123' or '700123')."
                )
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_search_patents_by_applicant",
    annotations={
        "title": "Search Swiss Patents by Applicant",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_patents_by_applicant(
    params: PatentApplicantInput,
) -> str:
    """Search Swiss patents by applicant or inventor name.

    Useful for competitive intelligence and innovation monitoring.
    Shows what organisations are patenting in Switzerland.

    Args:
        params (PatentApplicantInput):
            - applicant_name (str): Name, e.g. 'ABB*', 'ETH Zürich*', 'Roche*'
            - page_size (int): Results per page
            - page_token (str): Pagination token

    Returns:
        str: JSON with total, count, items, next_page_token
    """
    query_xml = f"<Any>{_esc(params.applicant_name)}</Any>"
    xml_body = _build_patent_search(
        query_xml, params.page_size, params.page_token
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_search_patent_publications",
    annotations={
        "title": "Search Swiss Patent Publications",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_patent_publications(
    params: PatentSearchInput,
) -> str:
    """Search Swiss patent publication records (Patentpublikationen).

    Patent publications are the official gazette entries for CH patent
    applications. Useful for prior-art searches and innovation monitoring.

    Args:
        params (PatentSearchInput):
            - query (str): Search term
            - page_size (int): Results per page
            - page_token (str): Pagination token

    Returns:
        str: JSON with total, count, items, next_page_token
    """
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_patent_pub_search(
        query_xml, params.page_size, params.page_token
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


# ---------------------------------------------------------------------------
# Tools – SPC / ESZ
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_spc",
    annotations={
        "title": "Search Swiss Supplementary Protection Certificates (SPC/ESZ)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_spc(params: SpcSearchInput) -> str:
    """Search Swiss Supplementary Protection Certificates (SPC, also ESZ).

    SPCs extend patent protection for medicinal or plant-protection products.
    Relevant for pharmaceutical research, health policy, and procurement.

    Args:
        params (SpcSearchInput):
            - query (str): Search term, e.g. 'Novartis', 'ibuprofen*'
            - page_size (int): Results per page
            - page_token (str): Pagination token

    Returns:
        str: JSON with total, count, items (SPC records), next_page_token
    """
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_spc_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


# ---------------------------------------------------------------------------
# Tools – Cross-domain
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_recent_filings",
    annotations={
        "title": "Search Swiss IP Filings by Date Range",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_recent_filings(params: DateRangeInput) -> str:
    """Search Swiss IP filings updated within a specific date range.

    Supports trademarks, patents, patent publications, and SPC records.
    Useful for monitoring recent IP activity, innovation dashboards, and
    KI-Fachgruppe demos showing what's being filed in Switzerland.

    Args:
        params (DateRangeInput):
            - ip_type (str): 'trademark', 'patent', 'patent_publication', 'spc'
            - date_from (str): Start date YYYY-MM-DD (inclusive)
            - date_to (str): End date YYYY-MM-DD (exclusive)
            - page_size (int): Results per page
            - page_token (str): Pagination token

    Returns:
        str: JSON with total, count, items, next_page_token, date_range_used
    """
    query_xml = (
        f'<LastUpdate from="{_esc(params.date_from)}" '
        f'to="{_esc(params.date_to)}"/>'
    )

    try:
        if params.ip_type == "trademark":
            xml_body = _build_trademark_search(
                query_xml, params.page_size, params.page_token
            )
        elif params.ip_type == "patent":
            xml_body = _build_patent_search(
                query_xml, params.page_size, params.page_token
            )
        elif params.ip_type == "patent_publication":
            xml_body = _build_patent_pub_search(
                query_xml, params.page_size, params.page_token
            )
        else:  # spc
            xml_body = _build_spc_search(
                query_xml, params.page_size, params.page_token
            )

        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        result["date_range"] = {
            "from": params.date_from,
            "to": params.date_to,
            "ip_type": params.ip_type,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_get_quota",
    annotations={
        "title": "Check IGE API Quota Usage",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def swiss_ip_get_quota() -> str:
    """Check the remaining data transfer quota for the IGE Swissreg API.

    The API has a monthly data transfer quota. Use this tool to monitor
    usage and avoid hitting limits.

    Returns:
        str: JSON with quota details including used and remaining transfer volume
    """
    try:
        root = await _call_api(_quota_request())
        quota_dict = _el_to_dict(root)
        return json.dumps(quota_dict, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        port = int(os.getenv("PORT", "8000"))
        logger.info("Starting Swiss IP MCP server on SSE transport, port %d", port)
        mcp.run(transport="sse", port=port)
    else:
        logger.info("Starting Swiss IP MCP server on stdio transport")
        mcp.run()


if __name__ == "__main__":
    main()
