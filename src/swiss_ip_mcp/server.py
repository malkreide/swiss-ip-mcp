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
from enum import StrEnum
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
    """Formatiert API-Fehler in verständliche Meldungen."""
    if isinstance(e, ValueError):
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
        return f"API-Fehler {status}: {e.response.text[:500]}"
    if isinstance(e, httpx.TimeoutException):
        return "Fehler: Anfrage hat das Timeout überschritten. Bitte erneut versuchen."
    return f"Unerwarteter Fehler ({type(e).__name__}): {e}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResponseFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"


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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
            return json.dumps({
                "error": f"Marke '{params.trademark_number}' nicht gefunden. "
                         "Bitte Nummernformat prüfen (z.B. 'P-756123')."
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
            return json.dumps({
                "error": (
                    f"Patent '{params.patent_number}' nicht gefunden. "
                    "Bitte Format prüfen (z.B. 'CH700123' oder '700123')."
                )
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


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
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


@mcp.tool(
    name="swiss_ip_get_quota",
    annotations={
        "title": "IGE API-Kontingent prüfen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
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
    except Exception as e:
        return json.dumps({"error": _handle_error(e)})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
