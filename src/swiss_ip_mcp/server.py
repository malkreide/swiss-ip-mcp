"""
Swiss IP MCP Server – Model Context Protocol server for Swiss intellectual
property data via the IGE/IPI Swissreg Datadelivery API.

Covers: Trademarks (Marken), Patents, Patent Publications,
        SPC/ESZ (Supplementary Protection Certificates).

Authentication: OAuth2 via IDP (IGE_USERNAME / IGE_PASSWORD env vars).
Transport:      stdio (default, e.g. Claude Desktop) and Streamable HTTP / SSE
                (cloud, e.g. Render.com) — selected via the MCP_TRANSPORT env var.
"""

from __future__ import annotations

import json
import logging
import os
import time
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
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

# ---------------------------------------------------------------------------
# Pooled HTTP client (SDK-001)
#
# A single AsyncClient is reused across all tool calls so that TCP/TLS
# connections are pooled instead of re-established on every request. The
# client is created lazily on first use and torn down by the server lifespan
# (see `_lifespan`). Lazy creation keeps the helper usable in unit tests that
# never enter the lifespan context.
# ---------------------------------------------------------------------------
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, creating it once on first use."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    return _client


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[dict]:
    """Server lifespan: own the pooled HTTP client for the whole process.

    Shared by all transports (stdio + Streamable HTTP / SSE), so there is no
    transport-dependent setup branch (ARCH-004).
    """
    client = _get_client()
    logger.info("swiss_ip_mcp lifespan up — pooled HTTP client ready")
    try:
        yield {"client": client}
    finally:
        global _client
        await client.aclose()
        _client = None
        logger.info("swiss_ip_mcp lifespan down — HTTP client closed")


async def _get_token(client: httpx.AsyncClient) -> str:
    """Obtain or refresh a Bearer token from the IGE IDP."""
    username = os.getenv("IGE_USERNAME", "")
    password = os.getenv("IGE_PASSWORD", "")

    if not username or not password:
        raise ValueError(
            "IGE-Zugangsdaten fehlen. "
            "Bitte IGE_USERNAME und IGE_PASSWORD als Umgebungsvariablen setzen. "
            "Nach Unterzeichnung der IGE-Nutzungsbedingungen (https://www.ige.ch/de/"
            "uebersicht-dienstleistungen/digitales-angebot/ip-daten/"
            "datenabgabe-api) erhalten Sie die Zugangsdaten."
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
    client = _get_client()
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
    """Map an exception to a safe, user-facing message (OBS-002).

    Full exception detail — including upstream response bodies and exception
    reprs — is logged server-side only. The returned string never carries
    internals (stack traces, raw API bodies) to the client / LLM.
    """
    logger.warning("Tool error: %r", e, exc_info=True)
    if isinstance(e, ValueError):
        # Raised by our own config check with a deliberate, safe help text
        # (missing IGE credentials) — no internals, keep it verbatim.
        return f"Konfigurationsfehler: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return (
                "Fehler 401: Authentifizierung fehlgeschlagen. "
                "Bitte IGE_USERNAME und IGE_PASSWORD prüfen."
            )
        if status == 403:
            return (
                "Fehler 403: Zugriff verweigert. Möglicherweise fehlt der API-Zugang. "
                "Bitte Nutzungsbedingungen prüfen."
            )
        if status == 429:
            return (
                "Fehler 429: Rate-Limit / Kontingent überschritten. "
                "Mit swiss_ip_get_quota das verbleibende Kontingent prüfen."
            )
        return (
            f"API-Fehler {status}: Die Anfrage an die Swissreg-API ist "
            "fehlgeschlagen. Details stehen im Server-Log."
        )
    if isinstance(e, httpx.TimeoutException):
        return "Fehler: Anfrage hat das Timeout überschritten. Bitte erneut versuchen."
    return (
        "Unerwarteter Fehler bei der Verarbeitung der Anfrage. "
        "Details stehen im Server-Log."
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResponseFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"


# ---------------------------------------------------------------------------
# Response rendering (SDK-003 — honour the response_format parameter)
# ---------------------------------------------------------------------------

def _scalarize(value: object) -> str:
    """Render a value inline; nested structures fall back to compact JSON."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _to_markdown(payload: dict) -> str:
    """Render a result envelope as readable Markdown."""
    if "error" in payload:
        return f"**Fehler:** {payload['error']}"

    lines: list[str] = []
    total = payload.get("total")
    count = payload.get("count")
    header = "## Ergebnisse"
    if total is not None:
        header += f" ({count} von {total})"
    elif count is not None:
        header += f" ({count})"
    lines.append(header)

    # Top-level scalar metadata (e.g. nice_class_searched, date_range).
    skip = {"items", "total", "count", "next_page_token"}
    for key, value in payload.items():
        if key in skip:
            continue
        lines.append(f"- **{key}:** {_scalarize(value)}")

    items = payload.get("items") or []
    if not items:
        lines.extend(["", "_Keine Einträge gefunden._"])
    for idx, item in enumerate(items, 1):
        lines.extend(["", f"### {idx}."])
        if isinstance(item, dict):
            for key, value in item.items():
                lines.append(f"- **{key}:** {_scalarize(value)}")
        else:
            lines.append(f"- {_scalarize(item)}")

    token = payload.get("next_page_token")
    if token:
        lines.extend(["", f"_Weitere Ergebnisse: page_token=`{token}`_"])

    return "\n".join(lines)


def _render(payload: dict, fmt: ResponseFormat) -> str:
    """Serialise a tool result in the requested response format."""
    if fmt == ResponseFormat.MARKDOWN:
        return _to_markdown(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Transport / network configuration (SCALE-001, SEC-016)
# ---------------------------------------------------------------------------

def _env_host() -> str:
    """Bind host. Defaults to loopback; 0.0.0.0 must be opted into explicitly."""
    return os.getenv("MCP_HOST", "127.0.0.1")


def _env_port() -> int:
    """Bind port. `PORT` (PaaS convention, e.g. Render) wins over `MCP_PORT`."""
    return int(os.getenv("PORT") or os.getenv("MCP_PORT") or "8000")


def _csv_env(name: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, "").split(",") if v.strip()]


def _resolve_transport() -> str:
    """Normalise MCP_TRANSPORT to one of: stdio, sse, streamable-http."""
    raw = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if raw in ("", "stdio"):
        return "stdio"
    if raw == "sse":
        return "sse"
    if raw in ("http", "streamable-http", "streamable_http"):
        return "streamable-http"
    raise SystemExit(
        f"Ungültiger MCP_TRANSPORT={raw!r}. Erlaubt: stdio, sse, streamable-http."
    )


def _transport_security() -> Optional[TransportSecuritySettings]:
    """DNS-rebinding protection for HTTP transports (SEC-005).

    Active only when an allow-list is configured via env, so local stdio use
    stays zero-config. In cloud deployments set MCP_ALLOWED_HOSTS /
    MCP_ALLOWED_ORIGINS to your public host(s).
    """
    hosts = _csv_env("MCP_ALLOWED_HOSTS")
    origins = _csv_env("MCP_ALLOWED_ORIGINS")
    if not hosts and not origins:
        return None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


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
    lifespan=_lifespan,
    host=_env_host(),
    port=_env_port(),
    transport_security=_transport_security(),
)

# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------

class TrademarkSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=(
            "Freitext-Suchbegriff. Wildcards (*) möglich. "
            "Beispiele: 'Zürich*', 'apple', 'Bank*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(
        default=10,
        description="Anzahl Ergebnisse pro Seite (1–50).",
        ge=1,
        le=50,
    )
    page_token: Optional[str] = Field(
        default=None,
        description="Paginierungs-Token aus dem vorherigen next_page_token.",
    )
    sort_descending: bool = Field(
        default=True,
        description="Nach letzter Aktualisierung absteigend sortieren (neueste zuerst).",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class TrademarkOwnerSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    owner_name: str = Field(
        ...,
        description=(
            "Name des Markeninhabers / Anmelders. "
            "Wildcards (*) möglich. Beispiel: 'Nestlé*', 'Google*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class TrademarkNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trademark_number: str = Field(
        ...,
        description=(
            "Schweizer Marken-Anmelde- oder Registernummer. "
            "Beispiele: 'P-756123', '756123'."
        ),
        min_length=1,
        max_length=50,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class TrademarkClassInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nice_class: int = Field(
        ...,
        description=(
            "Nizza-Klassifikation Klassennummer (1–45). "
            "Beispiel: 9 = Computer/Software, 35 = Werbung/Geschäftswesen, "
            "41 = Erziehung/Ausbildung."
        ),
        ge=1,
        le=45,
    )
    query: Optional[str] = Field(
        default=None,
        description="Optionaler zusätzlicher Textfilter innerhalb der Klasse.",
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class PatentSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=(
            "Freitext-Suche für Schweizer Patente. Wildcards (*) möglich. "
            "Beispiele: 'solar energy*', 'Novartis', 'machine learning'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    sort_descending: bool = Field(default=True)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class PatentNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    patent_number: str = Field(
        ...,
        description=(
            "Schweizer Patentnummer. Beispiele: 'CH123456', '123456'."
        ),
        min_length=1,
        max_length=50,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class PatentApplicantInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    applicant_name: str = Field(
        ...,
        description=(
            "Name des Patentanmelders oder Erfinders. "
            "Wildcards (*) möglich. Beispiele: 'ABB*', 'ETH Zürich*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class DateRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ip_type: str = Field(
        ...,
        description=(
            "Art des Schutzrechts: 'trademark', 'patent', "
            "'patent_publication' oder 'spc'."
        ),
        pattern="^(trademark|patent|patent_publication|spc)$",
    )
    date_from: str = Field(
        ...,
        description="Startdatum im ISO-Format YYYY-MM-DD (inklusive).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_to: str = Field(
        ...,
        description="Enddatum im ISO-Format YYYY-MM-DD (exklusive).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


class SpcSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=(
            "Suchbegriff für Ergänzende Schutzzertifikate (ESZ / SPC). "
            "Wildcards (*) möglich. Beispiele: 'Novartis', 'ibuprofen*'."
        ),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Ausgabeformat: 'markdown' oder 'json' (Standard: json).",
    )


# ---------------------------------------------------------------------------
# Tools – Trademarks
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_trademarks",
    annotations={
        "title": "Schweizer Marken suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_trademarks(params: TrademarkSearchInput) -> str:
    """Durchsucht das Schweizer Markenregister nach Freitext.
    Findet Marken nach Name, Markenbegriff oder Stichwort. Wildcards (*) möglich.

    Args:
        params (TrademarkSearchInput): Enthält:
            - query (str): Suchbegriff, z.B. 'Zürich*', 'apple', 'Bank*'
            - page_size (int): Ergebnisse pro Seite (1–50, Standard 10)
            - page_token (str): Paginierungs-Token für Folgeseiten
            - sort_descending (bool): Neueste zuerst (Standard True)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token
    """
    sort_dir = "Descending" if params.sort_descending else "Ascending"
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_trademark_search(
        query_xml, params.page_size, params.page_token, sort_dir=sort_dir
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_search_trademarks_by_owner",
    annotations={
        "title": "Schweizer Marken nach Inhaber suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_trademarks_by_owner(
    params: TrademarkOwnerSearchInput,
) -> str:
    """Durchsucht Schweizer Marken gefiltert nach Inhaber / Anmelder.
    Nützlich für IP-Monitoring: alle Marken eines Unternehmens oder einer Person finden.

    Args:
        params (TrademarkOwnerSearchInput): Enthält:
            - owner_name (str): Inhabername, z.B. 'Nestlé*', 'Stadt Zürich*'
            - page_size (int): Ergebnisse pro Seite (1–50)
            - page_token (str): Paginierungs-Token
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token
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
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_get_trademark",
    annotations={
        "title": "Schweizer Marke nach Nummer abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_get_trademark(params: TrademarkNumberInput) -> str:
    """Ruft eine bestimmte Schweizer Marke anhand der Anmelde-/Registernummer ab.
    Gibt detaillierten Datensatz inkl. Status, Waren-/Dienstleistungsklassen und Registrierungshistorie zurück.

    Args:
        params (TrademarkNumberInput): Enthält:
            - trademark_number (str): Schweizer Markennummer, z.B. 'P-756123'
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items (einzelner Eintrag), next_page_token
    """
    query_xml = f"<Id>{_esc(params.trademark_number)}</Id>"
    xml_body = _build_trademark_search(query_xml, page_size=1)
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        if result["count"] == 0:
            return _render({
                "error": f"Marke '{params.trademark_number}' nicht gefunden. "
                         "Bitte Nummernformat prüfen (z.B. 'P-756123')."
            }, params.response_format)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_search_trademarks_by_class",
    annotations={
        "title": "Schweizer Marken nach Nizza-Klasse suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_trademarks_by_class(
    params: TrademarkClassInput,
) -> str:
    """Durchsucht Schweizer Marken nach Nizza-Klassifikation.
    Nützlich für Wettbewerbsanalysen innerhalb einer Branche.

    Args:
        params (TrademarkClassInput): Enthält:
            - nice_class (int): Nizza-Klasse 1–45
            - query (str): Optionaler zusätzlicher Textfilter
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token
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
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


# ---------------------------------------------------------------------------
# Tools – Patents
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_patents",
    annotations={
        "title": "Schweizer Patente suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_patents(params: PatentSearchInput) -> str:
    """Durchsucht das Schweizer Patentregister nach Freitext.
    Gibt CH-Patenteinträge inkl. Titel, Anmelder, IPC-Klassifikation, Daten und Rechtsstatus zurück.

    Args:
        params (PatentSearchInput): Enthält:
            - query (str): Suchbegriff, z.B. 'solar energy*', 'Novartis'
            - page_size (int): Ergebnisse pro Seite (1–50)
            - page_token (str): Paginierungs-Token
            - sort_descending (bool): Neueste zuerst
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token
    """
    sort_dir = "Descending" if params.sort_descending else "Ascending"
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_patent_search(
        query_xml, params.page_size, params.page_token, sort_dir=sort_dir
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_get_patent",
    annotations={
        "title": "Schweizer Patent nach Nummer abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_get_patent(params: PatentNumberInput) -> str:
    """Ruft ein bestimmtes Schweizer Patent anhand seiner Nummer ab.
    Gibt vollständigen Datensatz inkl. IPC-Codes, Anmelder, Erfinder und Status zurück.

    Args:
        params (PatentNumberInput): Enthält:
            - patent_number (str): Schweizer Patentnummer, z.B. 'CH123456'
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items (einzelner Eintrag), next_page_token
    """
    query_xml = f"<Id>{_esc(params.patent_number)}</Id>"
    xml_body = _build_patent_search(query_xml, page_size=1)
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        if result["count"] == 0:
            return _render({
                "error": (
                    f"Patent '{params.patent_number}' nicht gefunden. "
                    "Bitte Format prüfen (z.B. 'CH700123' oder '700123')."
                )
            }, params.response_format)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_search_patents_by_applicant",
    annotations={
        "title": "Schweizer Patente nach Anmelder suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_patents_by_applicant(
    params: PatentApplicantInput,
) -> str:
    """Durchsucht Schweizer Patente nach Anmelder oder Erfinder.
    Nützlich für Wettbewerbsanalyse und Innovationsmonitoring.

    Args:
        params (PatentApplicantInput): Enthält:
            - applicant_name (str): Name, z.B. 'ABB*', 'ETH Zürich*', 'Roche*'
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token
    """
    query_xml = f"<Any>{_esc(params.applicant_name)}</Any>"
    xml_body = _build_patent_search(
        query_xml, params.page_size, params.page_token
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_search_patent_publications",
    annotations={
        "title": "Schweizer Patentpublikationen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_patent_publications(
    params: PatentSearchInput,
) -> str:
    """Durchsucht Schweizer Patentpublikationen (offizielle Veröffentlichungen).
    Nützlich für Stand-der-Technik-Recherchen und Innovationsmonitoring.

    Args:
        params (PatentSearchInput): Enthält:
            - query (str): Suchbegriff
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token
    """
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_patent_pub_search(
        query_xml, params.page_size, params.page_token
    )
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


# ---------------------------------------------------------------------------
# Tools – SPC / ESZ
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_spc",
    annotations={
        "title": "Schweizer ESZ/SPC suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_spc(params: SpcSearchInput) -> str:
    """Durchsucht Schweizer Ergänzende Schutzzertifikate (ESZ / SPC).
    ESZ verlängern den Patentschutz für Arzneimittel und Pflanzenschutzmittel.

    Args:
        params (SpcSearchInput): Enthält:
            - query (str): Suchbegriff, z.B. 'Novartis', 'ibuprofen*'
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items (ESZ-Einträge), next_page_token
    """
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_spc_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body)
        result = _parse_result_page(root)
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


# ---------------------------------------------------------------------------
# Tools – Cross-domain
# ---------------------------------------------------------------------------

@mcp.tool(
    name="swiss_ip_search_recent_filings",
    annotations={
        "title": "Schweizer IP-Eintragungen nach Datumsbereich suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_search_recent_filings(params: DateRangeInput) -> str:
    """Durchsucht Schweizer IP-Eintragungen innerhalb eines Datumsbereichs.
    Unterstützt Marken, Patente, Patentpublikationen und ESZ.

    Args:
        params (DateRangeInput): Enthält:
            - ip_type (str): 'trademark', 'patent', 'patent_publication', 'spc'
            - date_from (str): Startdatum YYYY-MM-DD (inklusive)
            - date_to (str): Enddatum YYYY-MM-DD (exklusive)
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Ergebnis mit total, count, items, next_page_token, date_range
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
        return _render(result, params.response_format)
    except Exception as e:
        return _render({"error": _handle_error(e)}, params.response_format)


@mcp.tool(
    name="swiss_ip_get_quota",
    annotations={
        "title": "IGE API-Kontingent prüfen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swiss_ip_get_quota() -> str:
    """Prüft das verbleibende Datentransfer-Kontingent der IGE Swissreg API.
    Die API hat ein monatliches Kontingent. Damit lässt sich die Nutzung überwachen.

    Returns:
        str: JSON mit Kontingent-Details inkl. genutztem und verbleibendem Volumen
    """
    try:
        root = await _call_api(_quota_request())
        quota_dict = _el_to_dict(root)
        return json.dumps(quota_dict, ensure_ascii=False, indent=2)
    except Exception as e:  # quota has no response_format — always JSON
        return json.dumps({"error": _handle_error(e)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def _in_container() -> bool:
    """Best-effort detection of a container/orchestrator environment."""
    return (
        os.path.exists("/.dockerenv")
        or os.getenv("CONTAINER") == "1"
        or os.getenv("KUBERNETES_SERVICE_HOST") is not None
    )


def _run_http(transport: str) -> None:
    """Serve over Streamable HTTP or SSE with CORS configured (SDK-004).

    Builds the ASGI app from the FastMCP instance and runs it under uvicorn on
    the configured host/port, so binding is explicit and controllable (SEC-016).
    """
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    host, port = _env_host(), _env_port()
    if host == "0.0.0.0" and not _in_container():  # noqa: S104 — intentional, gated
        logger.warning(
            "Binding auf 0.0.0.0 ohne erkannte Container-Umgebung. Im lokalen "
            "Betrieb 127.0.0.1 verwenden; 0.0.0.0 nur hinter einem Reverse-Proxy "
            "/ in einem Container (SEC-016)."
        )

    app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()

    # CORS: explicit origin allow-list (no wildcard in production), and the
    # Mcp-Session-Id header must be both accepted and exposed so browser
    # clients can read it from the response and echo it on follow-up requests.
    origins = _csv_env("MCP_ALLOWED_ORIGINS")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=bool(origins),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Mcp-Session-Id", "Last-Event-ID"],
        expose_headers=["Mcp-Session-Id"],
    )

    logger.info("swiss_ip_mcp starting via %s on %s:%d", transport, host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    """Run the server. Transport is stdio by default; set MCP_TRANSPORT=sse or
    MCP_TRANSPORT=streamable-http for cloud deployments."""
    transport = _resolve_transport()
    if transport == "stdio":
        mcp.run()
    else:
        _run_http(transport)


if __name__ == "__main__":
    main()
