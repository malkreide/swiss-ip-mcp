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
import os
import time
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import httpx
from mcp.server.caching import CacheHint
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from swiss_ip_mcp.logging_config import get_logger, setup_logging
from swiss_ip_mcp.telemetry import setup_telemetry, traced_tool

from . import __version__

# Wer fragt hier an? Ohne eigenen User-Agent geht der httpx-Default
# hinaus und der Betreiber der Datenquelle sieht bloss eine Bibliothek.
# Die Version stammt aus den Paket-Metadaten und kann nicht driften.
USER_AGENT = f"swiss-ip-mcp/{__version__} (+https://github.com/malkreide/swiss-ip-mcp)"
# ---------------------------------------------------------------------------
# Logging (structured JSON on stderr — OBS-003)
# ---------------------------------------------------------------------------
setup_logging()
logger = get_logger("swiss_ip_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IDP_TOKEN_URL = "https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token"
API_ENDPOINT = "https://www.swissreg.ch/public/api/v1"
CLIENT_ID = "datadelivery-api-client"

NS_CORE = "urn:ige:schema:xsd:datadeliverycore-1.0.0"
NS_COMMON = "urn:ige:schema:xsd:datadeliverycommon-1.0.0"
NS_TM = "urn:ige:schema:xsd:datadeliverytrademark-1.0.0"
NS_PAT = "urn:ige:schema:xsd:datadeliverypatent-1.0.0"
NS_SPC = "urn:ige:schema:xsd:datadeliveryspc-1.0.0"

DEFAULT_PAGE_SIZE = 10
REQUEST_TIMEOUT = 60.0

# Egress allow-list (SEC-021): the server only ever talks to these fixed IGE
# hosts. Enforced before every outgoing request as defense-in-depth — a
# code-layer guard against accidental or malicious egress to other hosts.
# Immutable on purpose (frozenset, not runtime-configurable).
ALLOWED_EGRESS_HOSTS = frozenset({"idp.ipi.ch", "www.swissreg.ch"})


def _assert_host_allowed(url: str) -> None:
    """Raise if `url`'s host is not on the egress allow-list (SEC-021)."""
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_EGRESS_HOSTS:
        raise ValueError(f"Egress zu nicht erlaubtem Host blockiert: {host!r}")


# Provenance attached to every tool response (CH-004 / SDK-002). All data is
# served by the IGE/IPI Swissreg Datadelivery API under its terms of use.
DATA_SOURCE = {
    "name": "Swissreg Datadelivery API (IGE/IPI)",
    "provider": "Swiss Federal Institute of Intellectual Property (IGE/IPI)",
    "url": "https://www.swissreg.ch/public/apidocs/",
    "license": "IGE/IPI Swissreg Datadelivery API Terms of Use",
    "license_url": ("https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api"),
}

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
        _client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    return _client


@asynccontextmanager
async def _lifespan(_server: MCPServer) -> AsyncIterator[dict]:
    """Server lifespan: own the pooled HTTP client for the whole process.

    Shared by all transports (stdio + Streamable HTTP / SSE), so there is no
    transport-dependent setup branch (ARCH-004).
    """
    client = _get_client()
    logger.info("lifespan_started")
    try:
        yield {"client": client}
    finally:
        global _client
        await client.aclose()
        _client = None
        logger.info("lifespan_stopped")


class _Credentials(BaseModel):
    """IGE credentials held as SecretStr so they never leak via repr/logs (ARCH-005)."""

    username: SecretStr
    password: SecretStr


def _load_credentials() -> _Credentials:
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
    return _Credentials(username=SecretStr(username), password=SecretStr(password))


async def _get_token(client: httpx.AsyncClient) -> str:
    """Obtain or refresh a Bearer token from the IGE IDP."""
    creds = _load_credentials()

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["token"]  # type: ignore[return-value]

    _assert_host_allowed(IDP_TOKEN_URL)
    resp = await client.post(
        IDP_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": creds.username.get_secret_value(),
            "password": creds.password.get_secret_value(),
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 300))
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expires_in
    logger.info("ige_token_refreshed", valid_for_s=expires_in)
    return token


async def _call_api(xml_body: str, ctx: Optional[Context] = None) -> ET.Element:
    """Post an XML request to the Swissreg API and return the root element.

    When a tool passes its `ctx`, progress is reported around the request so
    long-running calls (the API allows up to 60s) surface progress (SDK-003).
    """
    client = _get_client()
    token = await _get_token(client)
    logger.debug("swissreg_api_request", bytes=len(xml_body))
    _assert_host_allowed(API_ENDPOINT)
    if ctx is not None:
        await ctx.report_progress(progress=0.0, total=1.0, message="Abfrage an Swissreg…")
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
    if ctx is not None:
        await ctx.report_progress(progress=1.0, total=1.0)
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


def _parse_result_page(root: ET.Element) -> SearchEnvelope:
    """Extract items and pagination info into a typed envelope (SDK-002)."""
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

    count = len(items)
    # ARCH-003: match_type signals whether the search matched, so the LLM can
    # react instead of reading a bare empty list. Number lookups override it.
    return SearchEnvelope(
        source=_PROVENANCE,
        total=total,
        count=count,
        match_type="exact" if count else "none",
        results=items,
        next_page_token=next_token,
        suggestion=_NO_MATCH_SUGGESTION if count == 0 else None,
    )


def _handle_error(e: Exception) -> str:
    """Map an exception to a safe, user-facing message (OBS-002).

    Full exception detail — including upstream response bodies and exception
    reprs — is logged server-side only. The returned string never carries
    internals (stack traces, raw API bodies) to the client / LLM.
    """
    if isinstance(e, ValueError):
        # Raised by our own config check with a deliberate, safe help text
        # (missing IGE credentials) — no internals, keep it verbatim.
        logger.warning("config_error")
        return f"Konfigurationsfehler: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        logger.warning("api_http_error", status=status, exc_info=True)
        if status == 401:
            return "Fehler 401: Authentifizierung fehlgeschlagen. Bitte IGE_USERNAME und IGE_PASSWORD prüfen."
        if status == 403:
            return (
                "Fehler 403: Zugriff verweigert. Möglicherweise fehlt der API-Zugang. Bitte Nutzungsbedingungen prüfen."
            )
        if status == 429:
            return (
                "Fehler 429: Rate-Limit / Kontingent überschritten. "
                "Mit swiss_ip_get_quota das verbleibende Kontingent prüfen."
            )
        return f"API-Fehler {status}: Die Anfrage an die Swissreg-API ist fehlgeschlagen. Details stehen im Server-Log."
    if isinstance(e, httpx.TimeoutException):
        logger.warning("api_timeout")
        return "Fehler: Anfrage hat das Timeout überschritten. Bitte erneut versuchen."
    logger.error("unexpected_error", error_type=type(e).__name__, exc_info=True)
    return "Unerwarteter Fehler bei der Verarbeitung der Anfrage. Details stehen im Server-Log."


# ---------------------------------------------------------------------------
# Typed response models (SDK-002) — structured, validated tool returns
# ---------------------------------------------------------------------------

MatchType = Literal["exact", "none"]

_NO_MATCH_SUGGESTION = (
    "Keine Treffer. Suchbegriff mit Wildcard (*) erweitern, die Schreibweise prüfen oder den Begriff verkürzen."
)


class Provenance(BaseModel):
    """Data-source attribution attached to every response (CH-004)."""

    name: str
    provider: str
    url: str
    license: str
    license_url: str


_PROVENANCE = Provenance.model_validate(DATA_SOURCE)


class SearchEnvelope(BaseModel):
    """Consistent, typed envelope for search/list tools (SDK-002)."""

    source: Provenance = Field(default_factory=lambda: _PROVENANCE)
    total: Optional[str] = None
    count: int = 0
    match_type: MatchType = "none"
    results: list[dict[str, Any]] = Field(default_factory=list)
    next_page_token: Optional[str] = None
    suggestion: Optional[str] = None
    message: Optional[str] = None
    nice_class_searched: Optional[int] = None
    date_range: Optional[dict[str, str]] = None


class QuotaEnvelope(BaseModel):
    """Typed envelope for the quota tool (SDK-002)."""

    source: Provenance = Field(default_factory=lambda: _PROVENANCE)
    quota: dict[str, Any] = Field(default_factory=dict)


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


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def _resolve_transport() -> str:
    """Normalise MCP_TRANSPORT to one of: stdio, sse, streamable-http."""
    raw = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if raw in ("", "stdio"):
        return "stdio"
    if raw == "sse":
        return "sse"
    if raw in ("http", "streamable-http", "streamable_http"):
        return "streamable-http"
    raise SystemExit(f"Ungültiger MCP_TRANSPORT={raw!r}. Erlaubt: stdio, sse, streamable-http.")


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
# SEP-2549, Spec 2026-07-28: die auflistenden Methoden tragen `ttlMs` und
# `cacheScope`. Das SDK setzt beides auf «sofort veraltet, nie geteilt» — ein
# Server ohne `cache_hints` verhaelt sich also nicht neutral, sondern laesst
# jeden Client bei jeder Verbindung neu auflisten, fuer Listen, die beim Import
# feststehen und sich zur Laufzeit des Prozesses nicht aendern koennen.
#
# `public` folgt aus der Sache, nicht aus Bequemlichkeit: die 11 Tools werden
# per Dekorator beim Import registriert, es gibt keine Filterung nach Aufrufer.
# Sobald eine Liste vom Aufrufer abhaengt, muss der Scope im selben Commit auf
# `private` wechseln.
#
# `resources/read` und `prompts/get` stehen bewusst nicht dabei: das waere eine
# Zusicherung ueber den INHALT statt ueber das Verzeichnis.
LIST_CACHE_TTL_MS = 300_000

CACHE_HINTS = {
    "tools/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "resources/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "resources/templates/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "prompts/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "server/discover": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
}

mcp = MCPServer(
    "swiss_ip_mcp",
    cache_hints=CACHE_HINTS,
    instructions=(
        "Swiss IP MCP Server provides access to Swiss intellectual property "
        "data via the IGE/IPI Swissreg Datadelivery API. Covers trademarks "
        "(Marken), patents (Patente), patent publications, and supplementary "
        "protection certificates (SPC/ESZ). Requires IGE_USERNAME and "
        "IGE_PASSWORD environment variables (free after signing IGE usage terms)."
    ),
    lifespan=_lifespan,
    # Stateless HTTP removes per-session server state, so horizontally scaled
    # replicas need no session affinity (SCALE-002/003). Opt-in via env.
)

# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------


class TrademarkSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description=("Freitext-Suchbegriff. Wildcards (*) möglich. Beispiele: 'Zürich*', 'apple', 'Bank*'."),
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


class TrademarkOwnerSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    owner_name: str = Field(
        ...,
        description=("Name des Markeninhabers / Anmelders. Wildcards (*) möglich. Beispiel: 'Nestlé*', 'Google*'."),
        min_length=1,
        max_length=200,
    )
    page_size: int = Field(default=10, ge=1, le=50)
    page_token: Optional[str] = Field(default=None)


class TrademarkNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    trademark_number: str = Field(
        ...,
        description=("Schweizer Marken-Anmelde- oder Registernummer. Beispiele: 'P-756123', '756123'."),
        min_length=1,
        max_length=50,
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


class PatentNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    patent_number: str = Field(
        ...,
        description=("Schweizer Patentnummer. Beispiele: 'CH123456', '123456'."),
        min_length=1,
        max_length=50,
    )


class PatentApplicantInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    applicant_name: str = Field(
        ...,
        description=(
            "Name des Patentanmelders oder Erfinders. Wildcards (*) möglich. Beispiele: 'ABB*', 'ETH Zürich*'."
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
        description=("Art des Schutzrechts: 'trademark', 'patent', 'patent_publication' oder 'spc'."),
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
@traced_tool
async def swiss_ip_search_trademarks(params: TrademarkSearchInput, ctx: Optional[Context] = None) -> SearchEnvelope:
    """Durchsucht das Schweizer Markenregister nach Freitext.
    <use_case>Markenrecherche / Brand-Monitoring per Name, Wort oder Stichwort.</use_case>
    Findet Marken nach Name, Markenbegriff oder Stichwort. Wildcards (*) möglich.

    Args:
        params (TrademarkSearchInput): Enthält:
            - query (str): Suchbegriff, z.B. 'Zürich*', 'apple', 'Bank*'
            - page_size (int): Ergebnisse pro Seite (1–50, Standard 10)
            - page_token (str): Paginierungs-Token für Folgeseiten
            - sort_descending (bool): Neueste zuerst (Standard True)

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token
    """
    sort_dir = "Descending" if params.sort_descending else "Ascending"
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_trademark_search(query_xml, params.page_size, params.page_token, sort_dir=sort_dir)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_trademarks_by_owner(
    params: TrademarkOwnerSearchInput,
    ctx: Optional[Context] = None,
) -> SearchEnvelope:
    """Durchsucht Schweizer Marken gefiltert nach Inhaber / Anmelder.
    <use_case>Portfolio-Analyse: alle Marken eines Inhabers/Anmelders finden.</use_case>
    Nützlich für IP-Monitoring: alle Marken eines Unternehmens oder einer Person finden.

    Args:
        params (TrademarkOwnerSearchInput): Enthält:
            - owner_name (str): Inhabername, z.B. 'Nestlé*', 'Stadt Zürich*'
            - page_size (int): Ergebnisse pro Seite (1–50)
            - page_token (str): Paginierungs-Token

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token
    """
    # Trademark owner fields are searched via Any (the API's full-text field
    # covers holder/applicant names in the index).
    query_xml = f"<Any>{_esc(params.owner_name)}</Any>"
    xml_body = _build_trademark_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_get_trademark(params: TrademarkNumberInput, ctx: Optional[Context] = None) -> SearchEnvelope:
    """Ruft eine bestimmte Schweizer Marke anhand der Anmelde-/Registernummer ab.
    <use_case>Detail-Abruf einer Marke per Anmelde-/Registernummer.</use_case>
    <important_notes>Exakter Lookup; bei unbekannter Nummer match_type="none".</important_notes>
    Gibt detaillierten Datensatz inkl. Status, Waren-/Dienstleistungsklassen und Registrierungshistorie zurück.

    Args:
        params (TrademarkNumberInput): Enthält:
            - trademark_number (str): Schweizer Markennummer, z.B. 'P-756123'

    Returns:
        str: Ergebnis mit source, total, count, results (einzelner Eintrag), next_page_token
    """
    query_xml = f"<Id>{_esc(params.trademark_number)}</Id>"
    xml_body = _build_trademark_search(query_xml, page_size=1)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        if result.count == 0:
            # A specific number not existing is a valid empty result, not an
            # execution error — keep isError=false (OBS-001).
            result.suggestion = None
            result.message = (
                f"Marke '{params.trademark_number}' nicht gefunden. Bitte Nummernformat prüfen (z.B. 'P-756123')."
            )
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_trademarks_by_class(
    params: TrademarkClassInput,
    ctx: Optional[Context] = None,
) -> SearchEnvelope:
    """Durchsucht Schweizer Marken nach Nizza-Klassifikation.
    <use_case>Branchenanalyse: Marken einer Nizza-Klasse (1-45) finden.</use_case>
    Nützlich für Wettbewerbsanalysen innerhalb einer Branche.

    Args:
        params (TrademarkClassInput): Enthält:
            - nice_class (int): Nizza-Klasse 1–45
            - query (str): Optionaler zusätzlicher Textfilter
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token
    """
    # Combine class filter with optional text query
    class_query = f"<Any>Klasse {params.nice_class}</Any>"
    if params.query:
        query_xml = f"<And>{class_query}<Any>{_esc(params.query)}</Any></And>"
    else:
        query_xml = class_query

    xml_body = _build_trademark_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        result.nice_class_searched = params.nice_class
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_patents(params: PatentSearchInput, ctx: Optional[Context] = None) -> SearchEnvelope:
    """Durchsucht das Schweizer Patentregister nach Freitext.
    <use_case>Technologie-/Innovationsrecherche in Schweizer Patenten.</use_case>
    Gibt CH-Patenteinträge inkl. Titel, Anmelder, IPC-Klassifikation, Daten und Rechtsstatus zurück.

    Args:
        params (PatentSearchInput): Enthält:
            - query (str): Suchbegriff, z.B. 'solar energy*', 'Novartis'
            - page_size (int): Ergebnisse pro Seite (1–50)
            - page_token (str): Paginierungs-Token
            - sort_descending (bool): Neueste zuerst

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token
    """
    sort_dir = "Descending" if params.sort_descending else "Ascending"
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_patent_search(query_xml, params.page_size, params.page_token, sort_dir=sort_dir)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_get_patent(params: PatentNumberInput, ctx: Optional[Context] = None) -> SearchEnvelope:
    """Ruft ein bestimmtes Schweizer Patent anhand seiner Nummer ab.
    <use_case>Detail-Abruf eines Patents per Nummer.</use_case>
    <important_notes>Exakter Lookup; kein Fuzzy-Match.</important_notes>
    Gibt vollständigen Datensatz inkl. IPC-Codes, Anmelder, Erfinder und Status zurück.

    Args:
        params (PatentNumberInput): Enthält:
            - patent_number (str): Schweizer Patentnummer, z.B. 'CH123456'

    Returns:
        str: Ergebnis mit source, total, count, results (einzelner Eintrag), next_page_token
    """
    query_xml = f"<Id>{_esc(params.patent_number)}</Id>"
    xml_body = _build_patent_search(query_xml, page_size=1)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        if result.count == 0:
            # Valid empty result, not an execution error (OBS-001).
            result.suggestion = None
            result.message = (
                f"Patent '{params.patent_number}' nicht gefunden. Bitte Format prüfen (z.B. 'CH700123' oder '700123')."
            )
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_patents_by_applicant(
    params: PatentApplicantInput,
    ctx: Optional[Context] = None,
) -> SearchEnvelope:
    """Durchsucht Schweizer Patente nach Anmelder oder Erfinder.
    <use_case>Innovationsmonitoring: Patente eines Anmelders/Erfinders.</use_case>
    Nützlich für Wettbewerbsanalyse und Innovationsmonitoring.

    Args:
        params (PatentApplicantInput): Enthält:
            - applicant_name (str): Name, z.B. 'ABB*', 'ETH Zürich*', 'Roche*'
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token
    """
    query_xml = f"<Any>{_esc(params.applicant_name)}</Any>"
    xml_body = _build_patent_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_patent_publications(
    params: PatentSearchInput,
    ctx: Optional[Context] = None,
) -> SearchEnvelope:
    """Durchsucht Schweizer Patentpublikationen (offizielle Veröffentlichungen).
    <use_case>Stand-der-Technik-Recherche ueber Patentpublikationen.</use_case>
    Nützlich für Stand-der-Technik-Recherchen und Innovationsmonitoring.

    Args:
        params (PatentSearchInput): Enthält:
            - query (str): Suchbegriff
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token
    """
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_patent_pub_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_spc(params: SpcSearchInput, ctx: Optional[Context] = None) -> SearchEnvelope:
    """Durchsucht Schweizer Ergänzende Schutzzertifikate (ESZ / SPC).
    <use_case>Pharma/Pflanzenschutz: ESZ/SPC recherchieren.</use_case>
    ESZ verlängern den Patentschutz für Arzneimittel und Pflanzenschutzmittel.

    Args:
        params (SpcSearchInput): Enthält:
            - query (str): Suchbegriff, z.B. 'Novartis', 'ibuprofen*'
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token

    Returns:
        str: Ergebnis mit source, total, count, results (ESZ-Einträge), next_page_token
    """
    query_xml = f"<Any>{_esc(params.query)}</Any>"
    xml_body = _build_spc_search(query_xml, params.page_size, params.page_token)
    try:
        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_search_recent_filings(params: DateRangeInput, ctx: Optional[Context] = None) -> SearchEnvelope:
    """Durchsucht Schweizer IP-Eintragungen innerhalb eines Datumsbereichs.
    <use_case>Zeitraum-/Trendanalyse neuer IP-Eintragungen je Schutzrecht.</use_case>
    <important_notes>date_to ist exklusiv; ip_type aus 4 Werten.</important_notes>
    Unterstützt Marken, Patente, Patentpublikationen und ESZ.

    Args:
        params (DateRangeInput): Enthält:
            - ip_type (str): 'trademark', 'patent', 'patent_publication', 'spc'
            - date_from (str): Startdatum YYYY-MM-DD (inklusive)
            - date_to (str): Enddatum YYYY-MM-DD (exklusive)
            - page_size (int): Ergebnisse pro Seite
            - page_token (str): Paginierungs-Token

    Returns:
        str: Ergebnis mit source, total, count, results, next_page_token, date_range
    """
    query_xml = f'<LastUpdate from="{_esc(params.date_from)}" to="{_esc(params.date_to)}"/>'

    try:
        if params.ip_type == "trademark":
            xml_body = _build_trademark_search(query_xml, params.page_size, params.page_token)
        elif params.ip_type == "patent":
            xml_body = _build_patent_search(query_xml, params.page_size, params.page_token)
        elif params.ip_type == "patent_publication":
            xml_body = _build_patent_pub_search(query_xml, params.page_size, params.page_token)
        else:  # spc
            xml_body = _build_spc_search(query_xml, params.page_size, params.page_token)

        root = await _call_api(xml_body, ctx)
        result = _parse_result_page(root)
        result.date_range = {
            "from": params.date_from,
            "to": params.date_to,
            "ip_type": params.ip_type,
        }
        return result
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


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
@traced_tool
async def swiss_ip_get_quota(ctx: Optional[Context] = None) -> QuotaEnvelope:
    """Prüft das verbleibende Datentransfer-Kontingent der IGE Swissreg API.
    <use_case>Betriebsueberwachung: verbleibendes API-Kontingent pruefen.</use_case>
    Die API hat ein monatliches Kontingent. Damit lässt sich die Nutzung überwachen.

    Returns:
        str: JSON mit Kontingent-Details inkl. genutztem und verbleibendem Volumen
    """
    try:
        root = await _call_api(_quota_request(), ctx)
        quota_dict = _el_to_dict(root)
        if not isinstance(quota_dict, dict):
            quota_dict = {"value": quota_dict}
        return QuotaEnvelope(source=_PROVENANCE, quota=quota_dict)
    except Exception as e:
        raise ToolError(_handle_error(e)) from e


# ---------------------------------------------------------------------------
# Resources (ARCH-008) — read-only metadata under the swissip:// URI scheme
# ---------------------------------------------------------------------------

COVERED_DOMAINS = {
    "trademarks": "Schweizer Markenregister (Marken)",
    "patents": "Schweizer Patente",
    "patent_publications": "Offizielle Patentpublikationen",
    "spc": "Ergänzende Schutzzertifikate (ESZ / SPC)",
}


@mcp.resource("swissip://about", mime_type="application/json")
def about_resource() -> str:
    """Server- und Datenquellen-Metadaten (Provenance + abgedeckte Domänen)."""
    return json.dumps(
        {
            "server": "swiss-ip-mcp",
            "description": "MCP-Zugriff auf Schweizer IP-Daten via IGE/IPI Swissreg.",
            "source": DATA_SOURCE,
            "covered_domains": COVERED_DOMAINS,
            "read_only": True,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("swissip://domains", mime_type="application/json")
def domains_resource() -> str:
    """Liste der abgedeckten IP-Domänen dieses Servers."""
    return json.dumps({"covered_domains": COVERED_DOMAINS}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Prompts (ARCH-008) — curated workflow templates
# ---------------------------------------------------------------------------


@mcp.prompt(title="Markenverfügbarkeit prüfen")
def trademark_availability(name: str) -> str:
    """Prüft, ob ein Name als Schweizer Marke registriert ist."""
    return (
        f"Prüfe, ob '{name}' als Schweizer Marke registriert ist. Nutze "
        "swiss_ip_search_trademarks für eine Freitextsuche und bei Bedarf "
        "swiss_ip_search_trademarks_by_owner. Fasse Status, Inhaber und "
        "Nizza-Klassen der Treffer zusammen und bewerte die Verfügbarkeit."
    )


@mcp.prompt(title="Wettbewerber-IP-Report")
def competitor_ip_report(company: str) -> str:
    """Erstellt einen IP-Überblick (Marken + Patente) zu einem Unternehmen."""
    return (
        f"Erstelle einen IP-Überblick für '{company}'. Nutze "
        "swiss_ip_search_trademarks_by_owner und "
        "swiss_ip_search_patents_by_applicant (mit Wildcard '*'). Fasse die "
        "wichtigsten Marken und Patente sowie erkennbare Trends zusammen."
    )


@mcp.prompt(title="Neueste IP-Eintragungen")
def recent_ip_filings_report(ip_type: str, date_from: str, date_to: str) -> str:
    """Report über neue IP-Eintragungen in einem Zeitraum."""
    return (
        f"Liste die neuen {ip_type}-Eintragungen zwischen {date_from} und "
        f"{date_to} (date_to exklusiv) via swiss_ip_search_recent_filings und "
        "fasse Anzahl, auffällige Anmelder und Themen zusammen."
    )


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


async def _health(_request):
    """Liveness/readiness endpoint for container + load-balancer probes."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})


# Die Header, nach denen Spec 2026-07-28 eine Streamable-HTTP-Anfrage routet —
# in der Schreibweise des SDK (`mcp.shared.inbound`). Ein Browser darf einen
# nicht safelisteten Header gar nicht erst senden, wenn der Server ihn nicht in
# `Access-Control-Allow-Headers` nennt: ohne sie stirbt jede Cross-Origin-
# Anfrage am Preflight, vor dem ersten MCP-Byte. stdio- und Python-Clients
# kennen keinen Preflight und merken davon nichts — deshalb fiel es nicht auf.
#
# `Mcp-Param-*` fehlt bewusst: CORS kennt keinen Praefix-Wildcard, und kein
# Tool-Schema dieses Servers traegt eine `x-mcp-header`-Annotation.
CORS_ROUTING_HEADERS = ["Mcp-Method", "Mcp-Name", "Mcp-Protocol-Version"]


def _build_http_app(transport: str):
    """Build the Starlette app with a /health route and CORS configured.

    Factored out of `_run_http` so the wiring (health endpoint, CORS) is unit
    testable without binding a socket.
    """
    from starlette.middleware.cors import CORSMiddleware

    # mcp 2.x: host and transport_security are per-app kwargs; they were
    # constructor arguments (backed by settings) under 1.x.
    security = _transport_security()
    app = (
        mcp.sse_app(transport_security=security, host=_env_host())
        if transport == "sse"
        else mcp.streamable_http_app(
            transport_security=security,
            host=_env_host(),
            # mcp 2.x: stateless mode is a property of the app being built.
            stateless_http=_env_bool("MCP_STATELESS_HTTP"),
        )
    )

    # Health check for HEALTHCHECK / k8s probes / LB backend health (SCALE-002).
    app.add_route("/health", _health, methods=["GET"])

    # CORS: explicit origin allow-list (no wildcard in production), and the
    # Mcp-Session-Id header must be both accepted and exposed so browser
    # clients can read it from the response and echo it on follow-up requests.
    origins = _csv_env("MCP_ALLOWED_ORIGINS")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=bool(origins),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            *CORS_ROUTING_HEADERS,
            "Mcp-Session-Id",
            "Last-Event-ID",
        ],
        expose_headers=["Mcp-Session-Id"],
    )
    return app


def _run_http(transport: str) -> None:
    """Serve over Streamable HTTP or SSE with CORS configured (SDK-004).

    Builds the ASGI app from the MCPServer instance and runs it under uvicorn on
    the configured host/port, so binding is explicit and controllable (SEC-016).
    """
    import uvicorn

    host, port = _env_host(), _env_port()
    if host == "0.0.0.0" and not _in_container():  # noqa: S104 — intentional, gated
        logger.warning(
            "bind_public_without_container",
            host=host,
            hint="0.0.0.0 nur hinter Reverse-Proxy / im Container verwenden (SEC-016)",
        )

    app = _build_http_app(transport)
    logger.info(
        "http_server_start",
        transport=transport,
        host=host,
        port=port,
        stateless=_env_bool("MCP_STATELESS_HTTP"),
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    """Run the server. Transport is stdio by default; set MCP_TRANSPORT=sse or
    MCP_TRANSPORT=streamable-http for cloud deployments."""
    setup_telemetry()  # opt-in OpenTelemetry export (OBS-006); no-op when disabled
    transport = _resolve_transport()
    if transport == "stdio":
        mcp.run()
    else:
        _run_http(transport)


if __name__ == "__main__":
    main()
